#!/usr/bin/env bash
set -euo pipefail
# Placeholder: replace sqlite copy with pg_dump when DATABASE_URL points to PostgreSQL.
DB_PATH="${1:-./agri_marketplace.db}"
BACKUP_DIR="${2:-./backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp "$DB_PATH" "$BACKUP_DIR/agri_marketplace_$TIMESTAMP.db"
echo "Backup written to $BACKUP_DIR/agri_marketplace_$TIMESTAMP.db"
