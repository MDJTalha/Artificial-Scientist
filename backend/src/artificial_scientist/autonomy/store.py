"""SQLite persistence for bounded autonomy state and scientific memory."""
from __future__ import annotations
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

class AutonomyStore:
    """Small transactional journal; no scientific history is overwritten or deleted."""
    def __init__(self,database_path:str|Path):
        self.path=Path(database_path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self)->sqlite3.Connection:
        c=sqlite3.connect(str(self.path),timeout=10); c.row_factory=sqlite3.Row; c.execute("PRAGMA busy_timeout=10000"); return c
    def _init(self)->None:
        with closing(self._connect()) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS autonomy_workflows(
              workflow_id TEXT PRIMARY KEY, state TEXT NOT NULL, consequential INTEGER NOT NULL,
              approval_token_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS autonomy_transitions(
              event_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, from_state TEXT NOT NULL,
              to_state TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS autonomy_checkpoints(
              checkpoint_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, digest TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS autonomy_memory(
              memory_id TEXT PRIMARY KEY, key_name TEXT NOT NULL, version INTEGER NOT NULL,
              status TEXT NOT NULL, value_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
              digest TEXT NOT NULL, supersedes_version INTEGER, created_at TEXT NOT NULL,
              UNIQUE(key_name,version)
            );
            CREATE INDEX IF NOT EXISTS idx_autonomy_memory_key ON autonomy_memory(key_name,version);
            """)
    def save_workflow(self,workflow_id:str,state:str,consequential:bool,approval_token_hash:str|None)->None:
        now=datetime.now(UTC).isoformat()
        with closing(self._connect()) as c:
            c.execute("INSERT INTO autonomy_workflows(workflow_id,state,consequential,approval_token_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",(workflow_id,state,int(consequential),approval_token_hash,now,now)); c.commit()
    def transition(self,workflow_id:str,from_state:str,to_state:str,actor:str,reason:str)->None:
        now=datetime.now(UTC).isoformat()
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE autonomy_workflows SET state=?,updated_at=? WHERE workflow_id=? AND state=?",(to_state,now,workflow_id,from_state))
            if c.total_changes!=1: c.rollback(); raise ValueError("workflow state changed concurrently")
            c.execute("INSERT INTO autonomy_transitions VALUES(?,?,?,?,?,?,?)",(str(uuid4()),workflow_id,from_state,to_state,actor,reason,now)); c.commit()
    def checkpoint(self,workflow_id:str,digest:str)->None:
        with closing(self._connect()) as c:
            c.execute("INSERT INTO autonomy_checkpoints VALUES(?,?,?,?)",(str(uuid4()),workflow_id,digest,datetime.now(UTC).isoformat())); c.commit()
    def workflow(self,workflow_id:str):
        with closing(self._connect()) as c:
            row=c.execute("SELECT * FROM autonomy_workflows WHERE workflow_id=?",(workflow_id,)).fetchone()
        if row is None: raise KeyError(workflow_id)
        return dict(row)
    def transitions(self,workflow_id:str):
        with closing(self._connect()) as c:
            rows=c.execute("SELECT * FROM autonomy_transitions WHERE workflow_id=? ORDER BY occurred_at,event_id",(workflow_id,)).fetchall()
        return [dict(r) for r in rows]
    def memory_put(self,key:str,value:dict,status:str,evidence:tuple[str,...],digest:str,supersedes_version:int|None):
        now=datetime.now(UTC).isoformat()
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT COALESCE(MAX(version),0) FROM autonomy_memory WHERE key_name=?",(key,)).fetchone()
            version=int(row[0])+1
            c.execute("INSERT INTO autonomy_memory VALUES(?,?,?,?,?,?,?,?,?)",(str(uuid4()),key,version,status,json.dumps(value,sort_keys=True),json.dumps(evidence),digest,supersedes_version,now)); c.commit()
        return version
    def memory_history(self,key:str):
        with closing(self._connect()) as c:
            rows=c.execute("SELECT * FROM autonomy_memory WHERE key_name=? ORDER BY version",(key,)).fetchall()
        return [dict(r) for r in rows]
