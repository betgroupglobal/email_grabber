# OpsecAI — Project Reference

## What This Is
A live AI-powered pentesting assistant that:
1. Scans a target with Nmap
2. Semantically searches 14k+ attack patterns from `Attack_Dataset.csv`
3. Builds ranked multi-stage attack chains mapped to MITRE ATT&CK
4. Assesses every chain for OpSec risks and evasion recommendations
5. Streams everything to a real-time React dashboard

## Architecture

```
[Target]
   │
   ▼
[Real-time Analyzer :8001]  (Go)
   │  nmap scan + fingerprint
   ▼
[Knowledge Engine :8000]    (Python / FastAPI)
   │  semantic search (Qdrant) + structured query (PostgreSQL)
   │  attack vector builder + MITRE mapping
   ▼
[OpSec Monitor :8002]       (Python / FastAPI)
   │  rule-based OpSec findings + evasion hints
   ▼
[Orchestrator :3001]        (Node.js / WebSocket)
   │  pipeline coordinator, engagement store
   ▼
[Dashboard :3000]           (React / MUI)
```

## Services & Ports

| Service            | Port | Stack         |
|--------------------|------|---------------|
| Knowledge Engine   | 8000 | Python/FastAPI|
| Real-time Analyzer | 8001 | Go            |
| OpSec Monitor      | 8002 | Python/FastAPI|
| Orchestrator       | 3001 | Node.js       |
| Dashboard          | 3000 | React         |
| PostgreSQL         | 5432 | Docker        |
| Qdrant             | 6333 | Docker        |

## Quick Start

### Option A — Docker Compose (recommended)
```bash
cp .env.example .env
docker compose up --build
# Open http://localhost:3000
```

### Option B — Local dev
```bash
cp .env.example .env
./start.sh
```

## Key Commands

### Knowledge Engine
```bash
cd backend/knowledge_engine
pip install -r requirements.txt
python ingestor.py            # import dataset → PostgreSQL + Qdrant
python ingestor.py --force    # re-ingest even if data exists
uvicorn api:app --reload      # start API server
```

### Real-time Analyzer
```bash
cd backend/realtime_analyzer
go run .
# POST /scan {"target":"192.168.1.10"}
# GET  /sessions/{id}/stream   (SSE)
```

### OpSec Monitor
```bash
cd backend/opsec_monitor
uvicorn monitor:app --port 8002 --reload
# POST /assess       {"attack_steps":"...", "tools_used":"..."}
# POST /assess/chain {"steps": [...]}
```

### Orchestrator
```bash
cd backend/orchestrator
node index.js
# POST /engage {"target":"192.168.1.10"}
# WS   ws://localhost:3001?engagement=<id>
```

### Dashboard
```bash
cd frontend/dashboard
npm start
```

## API Reference

### Knowledge Engine (:8000)
- `POST /search`          — semantic search
- `POST /attack-vector`   — build attack chains
- `GET  /mitre/{id}`      — attacks by MITRE technique
- `GET  /categories`      — category breakdown
- `GET  /opsec/{id}`      — OpSec note for attack

### Orchestrator (:3001) — main entry point
- `POST /engage`          — start full engagement pipeline
- `GET  /engagements`     — list all engagements
- `GET  /engagements/:id` — get engagement details
- `POST /search`          — proxy to knowledge engine
- `POST /opsec/assess`    — assess single attack
- `POST /opsec/chain`     — assess full chain
- `WS   /?engagement=id`  — real-time updates

## Environment Variables
See `.env.example` for full list.

## Dataset
`Attack_Dataset.csv` — 14,133 attack records with:
- title, category, attack_type
- scenario_description, attack_steps, tools_used
- target_type, vulnerability
- mitre_technique, impact, detection_method, solution, tags, source
