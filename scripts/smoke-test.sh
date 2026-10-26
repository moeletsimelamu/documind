#!/usr/bin/env bash
# Smoke test for a running DocuMind (e.g. the container image in CI).
# Usage: scripts/smoke-test.sh http://127.0.0.1:8000
# Needs curl and jq. Exits non-zero on the first failed check.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"

pass() { printf '  ok  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; exit 1; }

for _ in $(seq 1 30); do
  curl -sf "$BASE/api/ready" >/dev/null && break
  sleep 1
done
[ "$(curl -s "$BASE/api/ready" | jq -r .status)" = "ready" ] || fail "server ready"
pass "server ready"

curl -s "$BASE/" | grep -q "<dm-root>" || fail "app shell served at /"
curl -s "$BASE/documents/anything" | grep -q "<dm-root>" || fail "client routes served"
pass "app shell and client routes served"

[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/docs")" = "404" ] || fail "API docs off"
pass "Swagger UI disabled"

[ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: attacker.example' "$BASE/api/health")" = "400" ] \
  || fail "foreign host refused"
pass "foreign Host header refused"

id="$(printf 'Smoke test\n\nThe container smoke test checks the quarterly warehouse audit.\n' \
  | curl -sf -F "file=@-;filename=smoke-test.txt" "$BASE/api/documents" | jq -r .id)"
[ -n "$id" ] && [ "$id" != "null" ] || fail "upload accepted"
pass "upload accepted"

status=processing
for _ in $(seq 1 60); do
  status="$(curl -s "$BASE/api/documents/$id" | jq -r .status)"
  [ "$status" != "processing" ] && break
  sleep 1
done
[ "$status" = "ready" ] || fail "document processed (status: $status)"
pass "document processed in an isolated worker"

[ "$(curl -s "$BASE/api/search?q=warehouse%20audit" | jq -r .total_passages)" -ge 1 ] || fail "search"
pass "search finds the passage"

mode="$(curl -s -X POST "$BASE/api/ask" -H 'Content-Type: application/json' \
  -d '{"question": "What does the smoke test check?"}' | jq -r .mode)"
[ "$mode" = "retrieval_only" ] || fail "ask (mode: $mode)"
pass "ask answers with passages (AI answers off)"

[ "$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/documents/$id")" = "204" ] \
  || fail "delete"
[ "$(curl -s "$BASE/api/search?q=warehouse" | jq -r .total_passages)" = "0" ] || fail "deleted from index"
pass "delete removes the document and its index entries"

echo "Smoke test passed."
