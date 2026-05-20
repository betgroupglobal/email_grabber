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
[Knowledge Engine :8010]    (Python / FastAPI)
   │  semantic search (Qdrant) + structured query (PostgreSQL)
   │  attack vector builder + MITRE mapping
   ▼
[OpSec Monitor :8002]       (Python / FastAPI)
   │  rule-based OpSec findings + evasion hints
   ▼
[Integration Hub :8500]     (Python / FastAPI) ← NEW
   │  plugin system for external tools & APIs
   │  local binary + remote API execution
   │  OpSec assessment integration
   ▼
[Orchestrator :3001]        (Node.js / WebSocket)
   │  pipeline coordinator, engagement store
   ▼
[Dashboard :3100]           (React / MUI)
```

## Services & Ports

| Service            | Port | Stack         |
|--------------------|------|---------------|
| Knowledge Engine   | 8010 | Python/FastAPI|
| Real-time Analyzer | 8001 | Go            |
| OpSec Monitor      | 8002 | Python/FastAPI|
| Orchestrator       | 3001 | Node.js       |
| Dashboard          | 3100 | React         |
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

### Knowledge Engine (:8010)
- `POST /search`          — semantic search (requires service auth header)
- `POST /attack-vector`   — build attack chains (requires service auth header)
- `GET  /mitre/{id}`      — attacks by MITRE technique
- `GET  /categories`      — category breakdown
- `GET  /opsec/{id}`      — OpSec note for attack
- `GET  /ai/status`       — OpenRouter AI provider status

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

## Week 1 Critical Fixes (Completed)
✅ **Service-to-Service Authentication**
- Added API keys for all services (orchestrator, analyzer, monitor, knowledge-engine)
- Updated auth middleware to support service API key verification
- All inter-service calls now include service auth headers
- Verified with `/attack-vector` endpoint test

✅ **Nmap Configuration**
- Installed nmap binary via Homebrew (`/opt/homebrew/bin/nmap`)
- Configured NMAP_BIN environment variable
- Knowledge Engine URL corrected to port 8010

✅ **OpenRouter AI Integration**
- Replaced Anthropic API with OpenRouter for AI summaries
- Added OPENROUTER_API_KEY and OPENROUTER_MODEL to environment
- Updated Knowledge Engine (claude_analyst.py) to use OpenRouter
- Updated Orchestrator (index.js) to use OpenRouter
- Verified: AI summaries now generate successfully

## Current Issues
⚠️ **Nmap Timeout**: Analyzer scans fail with "context canceled" errors when calling nmap from Go service. Standalone nmap works fine.
⚠️ **OpSec Monitor**: Service appears unavailable during engagement pipeline (monitoring not functional)

## Verification Commands
```bash
# Test service authentication
curl -H "X-Service-API-Key: $SERVICE_API_KEY_ORCHESTRATOR" http://localhost:8010/attack-vector -X POST -H "Content-Type: application/json" -d '{"target":"127.0.0.1","ip":"127.0.0.1","os":"unknown"}'

# Check OpenRouter AI status
curl http://localhost:8010/ai/status

# Test nmap standalone
/opt/homebrew/bin/nmap -sV 127.0.0.1

# Run full engagement
curl -X POST http://localhost:3001/engage -H "Content-Type: application/json" -d '{"target":"127.0.0.1","aggression_level":1}'
```

## Integration System
**NEW:** Comprehensive plugin architecture for external tool and API integrations.

### Integration Hub (:8500)
- Plugin system supporting local binary execution and remote API integrations
- Security tool integrations (C2 frameworks, exploitation tools, scanners)
- OpSec assessment integration (optional per integration)
- Integration marketplace with community contribution workflow
- Python and JavaScript SDKs for plugin development

### Available Integrations

#### AI Services
- **jailbreak_ai** — Complete AI-powered red team automation
  - **Chat Completions**: Standard OpenAI-compatible chat API
  - **Scan Analysis**: AI analysis of nmap/scan results to identify vulnerabilities
  - **Attack Planning**: Generate comprehensive, phased penetration test plans
  - **Test Initiation**: Orchestrate actual offensive tests via plugin delegation
  - **Red Team Automation**: Full autonomous multi-phase penetration testing
    - Autonomous reconnaissance, initial access, privilege escalation, lateral movement
    - AI-driven decision making for attack vector selection
    - Adaptive planning based on real-time findings
    - Full MITRE ATT&CK coverage
    - Comprehensive automated reporting
  - **Enhanced Automation (NEW!)**: Advanced automation capabilities
    - Multi-target operations with parallel execution
    - Continuous monitoring with change detection
    - Adaptive replanning for failed steps
    - Intelligent timing and evasion
    - State persistence and resume
    - Enhanced operation control (pause/resume/abort)
  - Endpoint: `POST /integrations/execute`
  - Config: `JAILBREAK_API_KEY` in `.env`
  - Location: `backend/integrations/integrations/jailbreak_ai/`
  - Supports streaming and non-streaming responses
  - Built-in OpSec assessment with usage tracking
  - **Files**: `plugin.py`, `redteam_automation.py`, `README.md`, `ENHANCED_AUTOMATION.md`

#### Security Tools
- **nmap** — Network scanner with XML parsing
  - Local binary execution
  - Config: `NMAP_BIN` in `.env`

### Documentation
- [INTEGRATIONS_BLUEPRINT.md](../architecture/INTEGRATIONS_BLUEPRINT.md) — Comprehensive integration system blueprint
- [INTEGRATION_ARCHITECTURE.md](../integrations/INTEGRATION_ARCHITECTURE.md) — Technical implementation details
- [jailbreak_ai.md](../integrations/jailbreak_ai.md) — Jailbreak AI usage guide

### Implementation Status
- **Phase 1**: Core plugin system (Week 1-2) — In Progress
  - ✅ Plugin base classes and interfaces
  - ✅ Configuration management system
  - ✅ Plugin loader and registry
  - ✅ Jailbreak AI integration (example remote API)
  - ✅ Nmap integration (example local binary)
  - ✅ Red Team Automation with AI-driven scan analysis
  - ⏳ Execution engine with Docker sandboxing
- **Phase 2**: Security tool integrations (Week 3-4) — Planned
- **Phase 3**: SDK & marketplace (Week 5-6) — Planned
- **Phase 4**: Advanced features (Week 7-8) — Planned

### Recent Integration Fixes (2026-05-17)
- **Fixed API Signature Mismatch**: Updated Integration Hub `execute` endpoint to build proper `ExecutionContext` objects instead of passing individual parameters to `PluginManager.execute()`
- **Fixed Plugin Manager Delegation**: Added plugin manager reference to execution context metadata, enabling red team automation to delegate scans to other plugins (nmap, etc.)
- **Fixed aiohttp Import**: Moved `aiohttp` import to module level in `plugin.py` to resolve import errors during AI analysis
- **Configured Jailbreak AI API Key**: Added `JAILBREAK_API_KEY` to docker-compose.yml environment variables for integration hub service
- **Fixed Scan Delegation**: Updated `redteam_automation.py` `_execute_scan()` method to use plugin manager directly instead of calling back to jailbreak plugin
- **Verified End-to-End Functionality**: Successfully tested red team automation with actual nmap scans and AI analysis against localhost target

See [INTEGRATIONS_BLUEPRINT.md](../architecture/INTEGRATIONS_BLUEPRINT.md) for complete integration roadmap and implementation details.

### Jailbreak AI Quick Start

#### Basic Chat
```bash
# Set API key in .env
JAILBREAK_API_KEY=jb-sk-af505e19...

# Execute via Integration Hub
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "test",
    "target": "chat",
    "parameters": {
      "messages": [{"role": "user", "content": "Hello!"}]
    }
  }'
```

#### Red Team Automation (Full Autonomous Pentest)
```bash
# Start complete autonomous red team operation
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "redteam_001",
    "target": "192.168.1.10",
    "parameters": {
      "operation": "redteam_automation",
      "redteam_config": {
        "target": "192.168.1.10",
        "aggression_level": 5,
        "phases": ["reconnaissance", "initial_access", "privilege_escalation", "impact", "reporting"]
      }
    },
    "timeout": 28800
  }'
```

### Enhanced Automation API Endpoints

The Integration Hub provides dedicated REST API endpoints for enhanced automation features. These offer a simplified interface compared to the generic `/integrations/execute` endpoint.

**Base URL:** `http://localhost:8500/api/v1/automation`

#### Multi-Target Operations
```bash
curl -X POST http://localhost:8500/api/v1/automation/multi-target \
  -H "Content-Type: application/json" \
  -d '{
    "engagement_id": "multi_001",
    "targets": ["192.168.1.10", "192.168.1.11"],
    "aggression_level": 5,
    "parallel": true
  }'
```

#### Continuous Monitoring
```bash
curl -X POST http://localhost:8500/api/v1/automation/monitoring/start \
  -H "Content-Type: application/json" \
  -d '{
    "engagement_id": "monitor_001",
    "targets": ["192.168.1.10"],
    "interval": 300
  }'
```

#### Adaptive Replanning
```bash
curl -X POST http://localhost:8500/api/v1/automation/replanning \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "redteam_001",
    "failed_step": {"step": "exploit", "error": "timeout"},
    "context": {"engagement_id": "eng_001"}
  }'
```

#### Operation Control
```bash
# Pause, resume, or abort operations
curl -X POST http://localhost:8500/api/v1/automation/operation/control \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "redteam_001",
    "action": "pause"
  }'
```

See [ENHANCED_AUTOMATION.md](../integrations/ENHANCED_AUTOMATION.md) for complete API documentation.

## Enhancement Roadmap
See [MAJOR_ENHANCEMENT_PLAN.md](../architecture/MAJOR_ENHANCEMENT_PLAN.md) for the comprehensive 16-week enhancement roadmap including:
- Phase 1 (Completed): Authentication, persistence, error handling, logging, health checks, config validation, graceful shutdown
- Phase 2 (Weeks 2-4): Performance & scalability (Redis caching, connection pooling, async tasks, load balancing)
- Phase 3 (Weeks 5-8): Advanced features (ML attack chains, AI assistant, integrations)
- Phase 4 (Weeks 9-12): User experience (team collaboration, mobile PWA, preferences)
- Phase 5 (Weeks 13-16): Production readiness (secrets management, monitoring, CI/CD, security)

## ML Model Integration

### Overview
The Knowledge Engine includes a trained ML model for attack pattern classification with 81.22% accuracy across 63 attack categories. The model is integrated into the engagement workflow to enhance attack vector generation.

### ML Service Details
- **Model**: Text classification (TF-IDF + Multinomial Naive Bayes)
- **Training Data**: 13,974 attack records from Attack_Dataset.csv
- **Accuracy**: 81.22%
- **Classes**: 63 unique attack categories
- **Location**: `backend/knowledge_engine/ml_service.py`
- **Model File**: `backend/knowledge_engine/models/attack_classifier.pkl`

### ML API Endpoints
The Knowledge Engine provides ML endpoints at `/ml/*` (port 8000):
- `GET /ml/status` - Check ML service status
- `GET /ml/models` - List available models
- `GET /ml/models/{target_name}` - Get model info
- `POST /ml/predict` - Single prediction
- `POST /ml/batch-predict` - Batch predictions

### Integration Strategy

#### Primary Integration: Attack Vector Building
**Location**: `backend/knowledge_engine/attack_chainer.py` → `AttackChainer.build_chains()`

**Current Flow**:
1. Build search queries from target context (services, OS, description)
2. Perform semantic search via Qdrant vector database
3. Classify candidates by attack phase (reconnaissance, initial_access, etc.)
4. Build chains by sampling from phase buckets

**Enhanced Flow with ML**:
1. Build search queries from target context
2. Perform semantic search via Qdrant vector database
3. **NEW**: Use ML batch prediction to classify all candidates by category
4. **NEW**: Re-rank candidates using combined score (semantic + ML confidence)
5. Classify candidates by attack phase
6. **NEW**: Use ML category predictions to weight attack selection per phase
7. Build chains by sampling from phase buckets with ML-enhanced ranking

**Implementation Details**:
- Import `MLService` in `attack_chainer.py`
- Initialize ML service in `AttackChainer.__init__()`
- Use batch prediction API for efficiency (all candidates in one call)
- Combine semantic search score (0-1) with ML confidence score (0-1)
- Apply weighted combination: `combined_score = 0.6 * semantic_score + 0.4 * ml_confidence`

#### Secondary Integration: OpSec Risk Prediction
**Location**: Could be added to OpSec Monitor or Knowledge Engine

**Purpose**: Use ML to predict OpSec risk levels for individual attack steps

**Implementation**:
- Train separate ML model for OpSec risk classification (low/medium/high/critical)
- Integrate predictions into OpSec assessment workflow
- Combine ML predictions with rule-based findings for enhanced risk scoring

### Benefits
1. **Improved Accuracy**: ML classification enhances semantic search with pattern recognition
2. **Better Chain Selection**: ML confidence scores help select more relevant attacks per phase
3. **Faster Convergence**: Re-ranking reduces need for multiple search iterations
4. **Scalability**: Batch processing enables efficient handling of large candidate sets
5. **Explainability**: ML predictions provide category labels for attack chain reasoning

### Testing
```bash
# Test ML service status
curl http://localhost:8000/ml/status

# Test single prediction
curl -X POST http://localhost:8000/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "SQL injection attack on web application"}'

# Test batch prediction
curl -X POST http://localhost:8000/ml/batch-predict \
  -H "Content-Type: application/json" \
  -d '{"texts": ["SQL injection", "XSS attack", "reconnaissance scanning"]}'
```

### Future Enhancements
- Train specialized models for specific attack phases
- Integrate ML predictions into AI summary generation for better context
- Add ML-based anomaly detection for zero-day attack patterns
- Implement continuous learning from engagement feedback

## Threat Emulation Service

### Overview
The Threat Emulation Service combines ML classification with jailbreak.ai automation to enable sophisticated threat actor emulation for authorized security testing. This service uses ML-predicted attack patterns to inform jailbreak.ai's attack planning, creating realistic threat simulations.

### Architecture
```
[Target Context]
   │
   ▼
[ML Classification] → Attack Category Prediction
   │
   ▼
[Threat Actor Matching] → Profile Selection (APT, Ransomware, etc.)
   │
   ▼
[Attack Planning] → MITRE Tactics + Tool Recommendations
   │
   ▼
[Jailbreak.ai Integration] → Automated Red Team Execution
   │
   ▼
[Threat Emulation Report]
```

### Threat Actor Profiles
Pre-configured threat actor profiles including:
- **APT28 (Fancy Bear)** - Russian state-sponsored actor, high stealth
- **Conti Ransomware Group** - Ransomware operator, high aggression
- **Lazarus Group** - North Korean state-sponsored, financial targeting
- **Anonymous (Hacktivist)** - Decentralized collective, lower stealth

Each profile includes:
- Typical attack categories
- Aggression/stealth/persistence levels
- Common tools and MITRE tactics
- Behavioral characteristics

### API Endpoints
**Base URL:** `http://localhost:8000/threat-emulation`

#### List Threat Actors
```bash
curl http://localhost:8000/threat-emulation/actors
```

#### Generate Emulation Plan
```bash
curl -X POST http://localhost:8000/threat-emulation/generate-plan \
  -H "Content-Type: application/json" \
  -d '{
    "target": "192.168.1.100",
    "target_description": "Corporate network with Windows servers",
    "threat_actor_id": "apt28"
  }'
```

#### Classify Target Context
```bash
curl -X POST http://localhost:8000/threat-emulation/classify-context \
  -H "Content-Type: application/json" \
  -d '{"target_description": "Healthcare system with patient records"}'
```

### Integration with Jailbreak.ai
The emulation plan generates a jailbreak.ai-compatible payload including:
- Operation type: `redteam_automation`
- Target-specific configuration
- ML-informed attack phases
- Tool recommendations
- Stealth preferences

**Example Payload Structure:**
```json
{
  "operation": "redteam_automation",
  "redteam_config": {
    "target": "192.168.1.100",
    "aggression_level": 7,
    "phases": ["Initial Access", "Execution", "Persistence"],
    "threat_actor_profile": "APT28 (Fancy Bear)",
    "ml_category": "Network Security",
    "ml_confidence": 0.85
  },
  "context": {
    "recommended_tools": ["Cobalt Strike", "Mimikatz", "PowerShell"],
    "attack_phases": [...],
    "stealth_preference": true
  }
}
```

### ML-Informed Features
1. **Target Classification**: ML predicts likely attack categories based on target description
2. **Threat Actor Matching**: System matches ML predictions to appropriate threat actor profiles
3. **Tool Recommendations**: Suggests tools based on threat actor profile and ML classification
4. **Attack Phase Planning**: Generates MITRE-aligned attack phases with ML insights
5. **Stealth Adaptation**: Adjusts stealth level based on threat actor characteristics

### Benefits for Authorized Testing
- **Realistic Threat Simulation**: Emulates actual threat actor behaviors
- **ML-Enhanced Accuracy**: Uses ML classification to improve attack pattern selection
- **Comprehensive Coverage**: Covers multiple threat actor types and TTPs
- **Tool Integration**: Recommends appropriate tools for each scenario
- **Automated Execution**: Ready for integration with jailbreak.ai automation

### Use Cases
- **Red Team Exercises**: Simulate specific threat actor campaigns
- **Security Testing**: Test defenses against realistic attack patterns
- **Training**: Educate teams on threat actor TTPs
- **Assessment**: Evaluate security posture against specific threats

### Dashboard Integration
The Threat Emulation Service is fully integrated into the OpsecAI dashboard at http://localhost:3100:

**UI Features:**
- **Target Configuration Panel**: Input target information and descriptions
- **ML Classification Button**: Real-time ML analysis of target context
- **Threat Actor Selection**: Choose specific actors or auto-select based on ML
- **Threat Actor Gallery**: View available profiles with aggression/stealth levels
- **Emulation Plan Display**: Comprehensive plan visualization with:
  - Threat actor profile summary
  - ML analysis results with confidence scores
  - Attack phases with MITRE tactics and techniques
  - Recommended security tools
  - Jailbreak.ai payload with copy-to-clipboard functionality

**Navigation:**
Access via "Threat Emulation" menu item in the dashboard sidebar.

**API Integration:**
The UI communicates directly with the Knowledge Engine threat emulation endpoints:
- `GET /threat-emulation/actors` - Load threat actor profiles
- `POST /threat-emulation/classify-context` - ML classification
- `POST /threat-emulation/generate-plan` - Generate emulation plans

## Application Status
- **Dashboard**: Running on http://localhost:3100
- **Phase 1 Status**: ✅ Complete (all critical enhancements implemented)
- **Week 1 Critical Fixes**: ✅ Complete (service auth, nmap, OpenRouter)
- **ML Integration**: ✅ Complete - ML service deployed, integrated into attack_chainer.py, tested and working
- **Threat Emulation**: ✅ Complete - ML + jailbreak.ai integration with full UI dashboard implementation
- **Next Priority**: Fix nmap timeout and OpSec monitor availability issues
