"""Backup SQLite (file copy) or PostgreSQL (pg_dump).

Usage:
  DATABASE_URL=... BACKUP_DIR=./backups python scripts/backup_database.py

Requires `pg_dump` on PATH for PostgreSQL URLs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agri_marketplace.db")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_sqlite(url: str) -> Path:
    raw = url.replace("sqlite:///", "", 1)
    db_path = Path(raw)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    if not db_path.exists():
        raise SystemExit(f"SQLite database not found: {db_path}")
    backup_path = BACKUP_DIR / f"{db_path.stem}_{_timestamp()}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def backup_postgres(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgres", "postgresql+psycopg", "postgresql+psycopg2"):
        raise SystemExit(f"Unsupported PostgreSQL URL scheme: {parsed.scheme}")

    stem = (parsed.path or "/postgres").strip("/").split("/")[-1] or "postgres"
    backup_path = BACKUP_DIR / f"{stem}_{_timestamp()}.sql"

    # Strip SQLAlchemy driver prefix for libpq / pg_dump
    if url.startswith("postgresql+") or url.startswith("postgres+"):
        scheme, rest = url.split("://", 1)
        base_scheme = "postgresql" if "postgresql" in scheme else "postgres"
        url = f"{base_scheme}://{rest}"

    try:
        subprocess.run(
            ["pg_dump", "--no-owner", "--dbname", url, "-f", str(backup_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise SystemExit(
            "pg_dump not found. Install PostgreSQL client tools or use a managed backup."
        ) from None
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"pg_dump failed: {exc.stderr or exc.stdout or exc}") from exc

    return backup_path


def main() -> None:
    url = DATABASE_URL.strip()
    if url.startswith("sqlite:"):
        out = backup_sqlite(url)
    elif url.startswith(("postgres://", "postgresql://")) or "postgresql+" in url.split("://", 1)[0]:
        out = backup_postgres(url)
    else:
        raise SystemExit(f"Unsupported DATABASE_URL for backup: {url[:40]}...")

    print(f"Backup written to {out.resolve()}")


if __name__ == "__main__":
    main()
