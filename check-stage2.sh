#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"
EXPECTED_POD="${EXPECTED_POD:-pod-1}"
EXPECTED_DC="${EXPECTED_DC:-dc-a}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_code() {
  local expected="$1"; shift
  local got
  got="$(curl -sS -o /dev/null -w '%{http_code}' "$@")" || fail "curl failed: $*"
  [[ "$got" == "$expected" ]] || fail "expected HTTP $expected, got $got: $*"
}

[[ "$(curl -fsS "$BASE/health")" == 'OK' ]] || fail "$BASE/health"
handlers="$(curl -fsS "$BASE/handlers")" || fail '/handlers unreachable'
for route in '/handlers' '/metrics' '/health' '/items' '/items/{id}'; do
  grep -Fq -- "\"route\":\"${route}\"" <<< "$handlers" || fail "missing route $route"
done
echo "OK: $BASE /health and /handlers"

created="$(curl -fsS -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -d '{"name":"First"}')" || fail 'POST /items'
id="$(printf '%s' "$created" | sed -nE 's/.*"id":([0-9]+).*/\1/p')"
[[ -n "$id" ]] || fail "POST did not return id: $created"
assert_code 200 "$BASE/items/$id"
assert_code 200 -X PUT "$BASE/items/$id" \
  -H 'Content-Type: application/json' -d '{"name":"Updated"}'
assert_code 404 "$BASE/items/987654321"
assert_code 400 -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -d '{"name":""}'
assert_code 500 -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -H 'X-Demo-Error: 500' \
  -d '{"name":"Synthetic Error"}'
echo "OK: CRUD and HTTP 400/404/500 on $BASE"

metrics="$(curl -fsS "$BASE/metrics")" || fail '/metrics unreachable'
for needle in 'app_http_requests_total' 'app_http_request_duration_seconds_bucket' \
  'route="/items/{id}"' 'status="404"' 'status="500"' \
  "pod=\"${EXPECTED_POD}\"" "dc=\"${EXPECTED_DC}\""; do
  grep -Fq -- "$needle" <<< "$metrics" || fail "missing metric: $needle"
done
echo "SUCCESS: stage 2 operational on $BASE ($EXPECTED_POD / $EXPECTED_DC)"
