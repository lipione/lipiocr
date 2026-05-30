#!/usr/bin/env sh
set -eu

BASE_URL="${1:-http://localhost:8020}"

curl -fsS "$BASE_URL/health" >/dev/null
curl -fsS "$BASE_URL/api/integrations/manifest" >/dev/null

echo "LipiOCR health check passed for $BASE_URL"
