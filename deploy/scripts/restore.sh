#!/usr/bin/env sh
set -eu

BACKUP_DIR="${1:-}"

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
  echo "Usage: deploy/scripts/restore.sh /path/to/backup" >&2
  exit 1
fi

if [ -f "$BACKUP_DIR/postgres.sql" ]; then
  docker exec -i lipiocr-postgres psql -U "${POSTGRES_USER:-lipiocr}" "${POSTGRES_DB:-lipiocr}" < "$BACKUP_DIR/postgres.sql"
fi

if [ -f "$BACKUP_DIR/uploads.tar.gz" ]; then
  tar -xzf "$BACKUP_DIR/uploads.tar.gz"
fi

echo "Restore completed from $BACKUP_DIR"
