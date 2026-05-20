#!/usr/bin/env bash
# Smoke-test MITRE endpoints: expect HTTP 200 with source field (heuristic or AI).
set -euo pipefail

ORCH="${ORCHESTRATOR_URL:-http://localhost:3001}"
TARGET="${MITRE_TEST_TARGET:-192.168.1.10}"

echo "Orchestrator: $ORCH"
echo "=== POST /mitre/suggest ==="
SUGGEST=$(curl -sS -w "\n%{http_code}" -X POST "$ORCH/mitre/suggest" \
  -H "Content-Type: application/json" \
  -d "{\"target\":\"$TARGET\",\"aggression_level\":5}")
SUGGEST_BODY=$(echo "$SUGGEST" | sed '$d')
SUGGEST_CODE=$(echo "$SUGGEST" | tail -n1)
echo "HTTP $SUGGEST_CODE"
echo "$SUGGEST_BODY" | head -c 400
echo ""

if [[ "$SUGGEST_CODE" != "200" ]]; then
  echo "FAIL: expected 200 from /mitre/suggest (got $SUGGEST_CODE). Rebuild orchestrator: docker compose build orchestrator && docker compose up -d orchestrator"
  exit 1
fi

if ! echo "$SUGGEST_BODY" | grep -q '"source"'; then
  echo "WARN: response missing source field"
fi

echo "=== POST /mitre/analyze ==="
ANALYZE=$(curl -sS -w "\n%{http_code}" -X POST "$ORCH/mitre/analyze" \
  -H "Content-Type: application/json" \
  -d '{"attack_description":"nmap port scan and ssh credential testing against linux host"}')
ANALYZE_BODY=$(echo "$ANALYZE" | sed '$d')
ANALYZE_CODE=$(echo "$ANALYZE" | tail -n1)
echo "HTTP $ANALYZE_CODE"
echo "$ANALYZE_BODY" | head -c 400
echo ""

if [[ "$ANALYZE_CODE" != "200" ]]; then
  echo "FAIL: expected 200 from /mitre/analyze (got $ANALYZE_CODE)"
  exit 1
fi

echo "OK: MITRE endpoints returned 200 with fallback or AI mapping"
