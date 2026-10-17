#!/usr/bin/env bash
# Live smoke checks for the hosted demo. Read-only requests only.
# Usage: smoke.sh <api-origin> <web-origin>
# Optional: ADMIN_API_KEY in the environment adds the signed-in admin check.
set -u

API="${1:?api origin, e.g. https://sportapp-api-ftsf.onrender.com}"
WEB="${2:?web origin, e.g. https://sportapp-web-7v3r.onrender.com}"
API="${API%/}"; WEB="${WEB%/}"
HEAVY="/nba/model/ranking"
PUBLIC="/tennis/predictions/today"
FAILS=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s  (%s)\n' "$1" "$2"; FAILS=$((FAILS + 1)); }
header() { grep -i "^$1:" | head -1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//'; }

# A unique forwarded client per run, so earlier runs never share a rate-limit bucket.
CLIENT="198.51.100.$((RANDOM % 250 + 1))"
OTHER="203.0.113.$((RANDOM % 250 + 1))"

health_headers=$(curl -s -m 90 -D - -o /tmp/smoke_health.$$ "$API/health")
health_body=$(cat /tmp/smoke_health.$$ 2>/dev/null); rm -f /tmp/smoke_health.$$
if grep -q '"env":"production"' <<<"$health_body"; then pass "health is production"; else fail "health is production" "$health_body"; fi
for h in strict-transport-security x-content-type-options x-frame-options referrer-policy; do
  v=$(header "$h" <<<"$health_headers")
  if [ -n "$v" ]; then pass "header $h"; else fail "header $h" "missing"; fi
done

preflight() {
  curl -s -m 30 -D - -o /dev/null -X OPTIONS "$API$PUBLIC" \
    -H "Origin: $1" -H "Access-Control-Request-Method: GET" | header access-control-allow-origin
}
allowed=$(preflight "$WEB")
if [ "$allowed" = "$WEB" ]; then pass "CORS allows the web origin"; else fail "CORS allows the web origin" "got '$allowed'"; fi
foreign=$(preflight "https://example.com")
if [ -z "$foreign" ]; then pass "CORS refuses example.com"; else fail "CORS refuses example.com" "got '$foreign'"; fi

code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$API/admin/session")
if [ "$code" = "401" ]; then pass "admin session 401 without key"; else fail "admin session 401 without key" "$code"; fi
if [ -n "${ADMIN_API_KEY:-}" ]; then
  code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' -H "X-API-Key: $ADMIN_API_KEY" "$API/admin/session")
  if [ "$code" = "200" ]; then pass "admin session 200 with key"; else fail "admin session 200 with key" "$code"; fi
fi

codes=""; retry=""
for i in $(seq 1 11); do
  out=$(curl -s -m 120 -D - -o /dev/null -w '%{http_code}' -H "X-Forwarded-For: $CLIENT" "$API$HEAVY")
  codes="$codes ${out: -3}"
  [ "$i" = 11 ] && retry=$(header retry-after <<<"$out")
done
last=${codes: -3}
if [ "$last" = "429" ] && [ -n "$retry" ]; then pass "11th heavy request is 429 (Retry-After $retry)"; else fail "11th heavy request is 429" "codes:$codes retry-after:'$retry'"; fi
code=$(curl -s -m 120 -o /dev/null -w '%{http_code}' -H "X-Forwarded-For: $OTHER" "$API$HEAVY")
if [ "$code" = "200" ]; then pass "another client is not limited"; else fail "another client is not limited" "$code"; fi

web_headers=$(curl -s -m 60 -D - -o /dev/null "$WEB/")
web_code=$(head -1 <<<"$web_headers" | awk '{print $2}')
if [ "$web_code" = "200" ]; then pass "web root 200"; else fail "web root 200" "$web_code"; fi
for h in x-content-type-options x-frame-options referrer-policy; do
  v=$(header "$h" <<<"$web_headers")
  if [ -n "$v" ]; then pass "web header $h"; else fail "web header $h" "missing"; fi
done

echo
if [ "$FAILS" -eq 0 ]; then echo "All checks passed."; else echo "$FAILS check(s) failed."; fi
exit "$FAILS"
