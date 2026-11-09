#!/usr/bin/env python3
"""
NEXORA AI Database Backup, Restore & Integrity Verification Tool.

Supports:
  - PostgreSQL logical snapshots via `pg_dump` / `pg_restore`
  - SQLite hot online snapshots via `sqlite3.Connection.backup()`
  - SHA-256 checksum manifests + retention pruning
  - `--verify-test` automated backup-and-restore validation cycle
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import urlparse


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_sqlite_path(db_url: str) -> str:
    cleaned = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    return os.path.abspath(cleaned)


def backup_sqlite(source_path: str, backup_dir: str) -> dict:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"SQLite source database not found: {source_path}")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_file = os.path.join(backup_dir, f"nexora_sqlite_{ts}.db")

    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(dest_file)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()

    check_conn = sqlite3.connect(dest_file)
    try:
        integrity = check_conn.execute("PRAGMA integrity_check;").fetchone()[0]
    finally:
        check_conn.close()
    if integrity != "ok":
        raise RuntimeError(f"SQLite backup integrity check failed: {integrity}")

    checksum = _sha256_file(dest_file)
    size_bytes = os.path.getsize(dest_file)
    manifest = {
        "engine": "sqlite",
        "source": source_path,
        "backup_file": dest_file,
        "sha256": checksum,
        "size_bytes": size_bytes,
        "integrity_check": integrity,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(dest_file + ".manifest.json", "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)
    return manifest


def restore_sqlite(backup_file: str, target_path: str) -> dict:
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    manifest_path = backup_file + ".manifest.json"
    actual_sha = _sha256_file(backup_file)
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as mf:
            expected_sha = json.load(mf).get("sha256")
        if expected_sha and actual_sha != expected_sha:
            raise RuntimeError("Backup SHA-256 checksum mismatch! Refusing corrupted restore.")

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    src = sqlite3.connect(backup_file)
    dst = sqlite3.connect(target_path)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()

    conn = sqlite3.connect(target_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        ]
    finally:
        conn.close()

    return {
        "restored_to": target_path,
        "sha256_verified": actual_sha,
        "integrity_check": integrity,
        "table_count": len(tables),
        "tables": tables,
    }


def backup_postgres(db_url: str, backup_dir: str) -> dict:
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_file = os.path.join(backup_dir, f"nexora_pg_{ts}.dump")

    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump binary not found on PATH.")

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    subprocess.run([pg_dump, "--format=custom", "--file", dest_file, sync_url], check=True)

    checksum = _sha256_file(dest_file)
    manifest = {
        "engine": "postgresql",
        "backup_file": dest_file,
        "sha256": checksum,
        "size_bytes": os.path.getsize(dest_file),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(dest_file + ".manifest.json", "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)
    return manifest


def restore_postgres(backup_file: str, db_url: str) -> dict:
    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        raise RuntimeError("pg_restore binary not found on PATH.")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    subprocess.run(
        [pg_restore, "--clean", "--if-exists", "--no-owner", "--dbname", sync_url, backup_file],
        check=True,
    )
    return {"restored_to": urlparse(sync_url).hostname or "postgresql", "backup_file": backup_file}


def prune_backups(backup_dir: str, keep: int = 14) -> int:
    if not os.path.isdir(backup_dir):
        return 0
    files = sorted(
        [
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.endswith(".db") or f.endswith(".dump")
        ],
        key=os.path.getmtime,
        reverse=True,
    )
    removed = 0
    for old_file in files[keep:]:
        os.remove(old_file)
        mf = old_file + ".manifest.json"
        if os.path.exists(mf):
            os.remove(mf)
        removed += 1
    return removed


def run_verify_test() -> dict:
    """Create temporary DB, populate test table, snapshot backup, restore to fresh target, and verify."""
    with tempfile.TemporaryDirectory(prefix="nexora_backup_verify_") as tmp:
        src_db = os.path.join(tmp, "source.db")
        restore_db = os.path.join(tmp, "restored.db")
        backup_dir = os.path.join(tmp, "backups")

        conn = sqlite3.connect(src_db)
        conn.execute("CREATE TABLE verify_records (id INTEGER PRIMARY KEY, label TEXT NOT NULL);")
        conn.execute("INSERT INTO verify_records (id, label) VALUES (1, 'nexora-backup-ok');")
        conn.commit()
        conn.close()

        b_info = backup_sqlite(src_db, backup_dir)
        r_info = restore_sqlite(b_info["backup_file"], restore_db)

        r_conn = sqlite3.connect(restore_db)
        row = r_conn.execute("SELECT id, label FROM verify_records WHERE id=1;").fetchone()
        r_conn.close()
        assert row == (1, "nexora-backup-ok"), f"Unexpected restored row: {row}"
        return {"backup": b_info, "restore": r_info, "verified_row": list(row), "status": "PASSED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXORA AI Database Backup & Restore CLI")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./nexora.db"))
    parser.add_argument("--backup-dir", default=os.environ.get("BACKUP_DIR", "./backups"))
    parser.add_argument("--backup", action="store_true", help="Run hot database backup")
    parser.add_argument("--restore", type=str, help="Restore database from backup file")
    parser.add_argument("--target-sqlite", type=str, help="Explicit SQLite restore destination path")
    parser.add_argument("--prune", type=int, default=0, help="Keep N most recent backups")
    parser.add_argument("--verify-test", action="store_true", help="Run isolated backup & restore verification test")
    args = parser.parse_args()

    if args.verify_test:
        res = run_verify_test()
        print(json.dumps(res, indent=2))
        return 0

    if args.backup:
        if "sqlite" in args.database_url:
            res = backup_sqlite(_resolve_sqlite_path(args.database_url), args.backup_dir)
        else:
            res = backup_postgres(args.database_url, args.backup_dir)
        if args.prune > 0:
            res["pruned_old_files"] = prune_backups(args.backup_dir, keep=args.prune)
        print(json.dumps(res, indent=2))
        return 0

    if args.restore:
        if "sqlite" in args.database_url or args.target_sqlite:
            target = args.target_sqlite or _resolve_sqlite_path(args.database_url)
            res = restore_sqlite(args.restore, target)
        else:
            res = restore_postgres(args.restore, args.database_url)
        print(json.dumps(res, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
