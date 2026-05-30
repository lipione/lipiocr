#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-infra/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

required="
LIPIOCR_API_AUTH_ENABLED
LIPIOCR_API_KEYS
LIPIOCR_PREVIEW_TOKEN_SECRET
POSTGRES_PASSWORD
MINIO_ROOT_PASSWORD
NEXT_PUBLIC_API_BASE_URL
"

for key in $required; do
  if ! grep -Eq "^${key}=.+" "$ENV_FILE"; then
    echo "Missing required setting: $key" >&2
    exit 1
  fi
done

if grep -Eq "(change-me|replace-with|demo-key)" "$ENV_FILE"; then
  echo "Env file still contains placeholder secrets" >&2
  exit 1
fi

echo "LipiOCR env validation passed"
