"""Phase 10: versioned scientific memory with contradictions and rollback."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC,datetime
from hashlib import sha256
import json
@dataclass(frozen=True)
class MemoryVersion:
    key:str; version:int; value:dict; status:str; evidence:tuple[str,...]; created_at:datetime; digest:str; supersedes:int|None
class MemoryError(ValueError): pass
class ResearchMemory:
    def __init__(self): self._items:dict[str,list[MemoryVersion]]={}
    def put(self,key:str,value:dict,*,evidence:tuple[str,...],status:str="active")->MemoryVersion:
        if not key or len(key)>200 or not evidence: raise MemoryError("key and evidence are required")
        versions=self._items.setdefault(key,[]); previous=versions[-1] if versions else None
        payload=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        digest=sha256(payload.encode()).hexdigest(); item=MemoryVersion(key,len(versions)+1,value,status,tuple(evidence),datetime.now(UTC),digest,previous.version if previous else None)
        versions.append(item); return item
    def history(self,key:str)->tuple[MemoryVersion,...]: return tuple(self._items.get(key,()))
    def contradict(self,key:str,*,evidence:tuple[str,...],reason:str)->MemoryVersion:
        if not reason or not evidence: raise MemoryError("contradiction requires reason and evidence")
        current=self.current(key)
        return self.put(key,{"contradicts":current.digest,"reason":reason},evidence=evidence,status="disputed")
    def rollback(self,key:str,version:int)->MemoryVersion:
        versions=self._items.get(key,[])
        if version<1 or version>len(versions): raise MemoryError("unknown memory version")
        target=versions[version-1]
        return self.put(key,target.value,evidence=target.evidence,status="rollback")
    def current(self,key:str)->MemoryVersion:
        versions=self._items.get(key,[])
        if not versions: raise MemoryError("unknown memory key")
        return versions[-1]
