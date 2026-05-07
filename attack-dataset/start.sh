#!/usr/bin/env bash
# ── OpsecAI — local dev startup script ───────────────────────────────────────
# Starts all services in separate background processes.
# Requirements: python3, pip, go, node/npm, docker (for postgres + qdrant)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
  echo ""
  echo "[start] Stopping all services…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

log() { echo -e "\033[36m[start]\033[0m $*"; }

# ── 1. Infrastructure (docker) ────────────────────────────────────────────────
log "Starting PostgreSQL + Qdrant via Docker Compose…"
docker compose -f "$ROOT/docker-compose.yml" up -d postgres qdrant
sleep 3

# ── 2. Knowledge Engine ───────────────────────────────────────────────────────
log "Installing Knowledge Engine deps…"
pip install -q -r "$ROOT/backend/knowledge_engine/requirements.txt"

log "Running ingestor (skips if data already exists)…"
cd "$ROOT/backend/knowledge_engine" && python ingestor.py &
INGEST_PID=$!
wait $INGEST_PID

log "Starting Knowledge Engine API on :8000…"
cd "$ROOT/backend/knowledge_engine" && uvicorn api:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)

# ── 3. OpSec Monitor ─────────────────────────────────────────────────────────
log "Installing OpSec Monitor deps…"
pip install -q -r "$ROOT/backend/opsec_monitor/requirements.txt"

log "Starting OpSec Monitor on :8002…"
cd "$ROOT/backend/opsec_monitor" && uvicorn monitor:app --host 0.0.0.0 --port 8002 &
PIDS+=($!)

# ── 4. Real-time Analyzer (Go) ────────────────────────────────────────────────
log "Building Real-time Analyzer…"
cd "$ROOT/backend/realtime_analyzer" && go build -o /tmp/opsec-analyzer . 
log "Starting Real-time Analyzer on :8001…"
ANALYZER_ADDR=":8001" \
KNOWLEDGE_ENGINE_URL="http://localhost:8000" \
  /tmp/opsec-analyzer &
PIDS+=($!)

# ── 5. Orchestrator (Node.js) ─────────────────────────────────────────────────
log "Starting Orchestrator on :3001…"
cd "$ROOT/backend/orchestrator" && \
  PORT=3001 \
  KNOWLEDGE_ENGINE_URL="http://localhost:8000" \
  ANALYZER_URL="http://localhost:8001" \
  OPSEC_URL="http://localhost:8002" \
  node index.js &
PIDS+=($!)

# ── 6. Dashboard (React dev server) ──────────────────────────────────────────
log "Starting Dashboard dev server on :3000…"
cd "$ROOT/frontend/dashboard" && \
  REACT_APP_ORCHESTRATOR_URL="http://localhost:3001" \
  REACT_APP_WS_URL="ws://localhost:3001" \
  npm start &
PIDS+=($!)

log ""
log "All services started. Open http://localhost:3000 in your browser."
log "Press Ctrl+C to stop."
wait
