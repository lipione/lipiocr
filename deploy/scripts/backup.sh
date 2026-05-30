#!/usr/bin/env sh
set -eu

BACKUP_ROOT="${1:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_ROOT/$STAMP"

mkdir -p "$TARGET"

if command -v docker >/dev/null 2>&1; then
  docker exec lipiocr-postgres pg_dump -U "${POSTGRES_USER:-lipiocr}" "${POSTGRES_DB:-lipiocr}" > "$TARGET/postgres.sql"
else
  echo "docker command unavailable; skipping postgres dump" >&2
fi

if [ -d storage/uploads ]; then
  tar -czf "$TARGET/uploads.tar.gz" storage/uploads
fi

echo "$TARGET" > "$BACKUP_ROOT/latest"
echo "Backup written to $TARGET"
