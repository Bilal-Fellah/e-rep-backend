#!/usr/bin/env bash
#
# Pre-deploy smoke test for the comment-sentiment endpoints.
#
# IMPORTANT: run this against a server backed by **PostgreSQL** (local dev with
# your real .env, or staging). The TESTING=sqlite config will NOT catch
# Postgres-only issues such as the uuid/varchar join type mismatch.
#
# Usage:
#   BASE_URL=http://localhost:5000 ENTITY_ID=92 ./scripts/smoke_sentiment.sh
#   BASE_URL=https://api.brendex.net ./scripts/smoke_sentiment.sh
#
# Optional: TOKEN=<jwt> to exercise the authenticated/premium paths.

set -u

BASE_URL="${BASE_URL:-http://localhost:5000}"
ENTITY_ID="${ENTITY_ID:-92}"
AUTH=()
[ -n "${TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer ${TOKEN}")

fail=0

check() {
  local name="$1" url="$2"
  # Capture body + HTTP status separately.
  local body status
  body="$(curl -s -w $'\n%{http_code}' "${AUTH[@]}" "$url")"
  status="$(printf '%s' "$body" | tail -n1)"
  body="$(printf '%s' "$body" | sed '$d')"

  if [ "$status" = "200" ] && printf '%s' "$body" | grep -q '"success": *true'; then
    echo "PASS  $name  ($status)"
  else
    echo "FAIL  $name  ($status)"
    echo "      $body" | head -c 300
    echo
    fail=1
  fi
}

echo "Smoke-testing sentiment endpoints against $BASE_URL"
check "entity sentiment (30d)"   "$BASE_URL/api/data/get_entity_comment_sentiment?entity_id=$ENTITY_ID&period=30d"
check "entity sentiment (all)"   "$BASE_URL/api/data/get_entity_comment_sentiment?entity_id=$ENTITY_ID&period=all"
check "sentiment ranking (30d)"  "$BASE_URL/api/data/get_sentiment_ranking?period=30d"
check "sentiment ranking (all)"  "$BASE_URL/api/data/get_sentiment_ranking?period=all"

if [ "$fail" = "0" ]; then
  echo "All sentiment smoke checks passed."
else
  echo "Some sentiment smoke checks FAILED — do not deploy."
  exit 1
fi
