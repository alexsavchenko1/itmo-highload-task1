#!/usr/bin/env bash
# Backwards-compatible stage 1 smoke check.
set -euo pipefail
base="${BASE:-http://127.0.0.1:8080}"
curl -fsS "$base/health"; printf '\n'
curl -fsS -X POST "$base/items" -H 'Content-Type: application/json' -d '{"name":"First item"}'
printf '\n'
