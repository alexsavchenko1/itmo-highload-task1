#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
assert_code() {
  local expected="$1"; shift
  local result
  result="$(curl -sS -o /dev/null -w '%{http_code}' "$@")"
  [[ "$result" == "$expected" ]] || fail "expected $expected, got $result: curl $*"
}
health="$(curl -fsS "$BASE/health")" || fail '/health not reachable'
[[ "$health" == 'OK' ]] || fail '/health does not return OK'
echo 'OK: /health'

handlers="$(curl -fsS "$BASE/handlers")" || fail '/handlers not reachable'
for route in '/handlers' '/metrics' '/health' '/items' '/items/{id}'; do
  grep -Fq -- "\"route\":\"${route}\"" <<< "$handlers" || fail "missing route $route"
done
echo 'OK: /handlers lists real MVC routes'

assert_code 201 -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -d '{"name":"First"}'
assert_code 200 "$BASE/items/1"
assert_code 200 -X PUT "$BASE/items/1" \
  -H 'Content-Type: application/json' -d '{"name":"Updated"}'
assert_code 404 "$BASE/items/987654321"
assert_code 400 -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -d '{"name":""}'
assert_code 500 -X POST "$BASE/items" \
  -H 'Content-Type: application/json' -H 'X-Demo-Error: 500' \
  -d '{"name":"Synthetic Error"}'
echo 'OK: CRUD, validation, 404 and synthetic 500'

metrics="$(curl -fsS "$BASE/metrics")" || fail '/metrics not reachable'
for needle in 'app_http_requests_total' 'app_http_request_duration_seconds_bucket' \
  'route="/items/{id}"' 'status="404"' 'status="500"' \
  'pod="pod-local-1"' 'dc="local"'; do
  grep -Fq -- "$needle" <<< "$metrics" || fail "/metrics does not contain $needle"
done
echo 'OK: Prometheus counter, histogram and normalized labels'
echo 'SUCCESS: TASK1 stages 1 and 2 are operational'
