"""Create and verify a SQLite backup without modifying the source database."""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
from pathlib import Path

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _integrity(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    if not row or row[0] != "ok":
        raise RuntimeError(f"SQLite integrity_check failed for {path}")

def backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    before = digest(source)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    _integrity(target)
    if digest(source) != before:
        raise RuntimeError("Source database changed during backup.")
    print(f"source_sha256={before}")
    print(f"backup_sha256={digest(target)}")
    print("backup_integrity=ok")

def restore(backup_path: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing target: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup_path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    _integrity(target)
    print(f"backup_sha256={digest(backup_path)}")
    print(f"restored_sha256={digest(target)}")
    print("restore_integrity=ok")

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p_backup = sub.add_parser("backup")
    p_backup.add_argument("source", type=Path)
    p_backup.add_argument("target", type=Path)
    p_restore = sub.add_parser("restore")
    p_restore.add_argument("backup", type=Path)
    p_restore.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.mode == "backup":
        backup(args.source, args.target)
    else:
        restore(args.backup, args.target)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
