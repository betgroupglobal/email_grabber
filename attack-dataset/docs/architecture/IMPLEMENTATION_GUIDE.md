# OpsecAI - Quick Start Implementation Guide

**Version:** 1.0  
**Last Updated:** 2026-05-11  
**Purpose:** Quick reference for immediate implementation tasks

---

## 🚨 Immediate Priority (Week 1)

### Task 1: Service-to-Service Authentication Integration
**Status:** ⚠️ BLOCKER - Services returning 401 errors  
**Effort:** 2-3 days  
**Priority:** P0 - CRITICAL

**Problem:**
- Orchestrator gets 401 Unauthorized when calling Knowledge Engine
- No service authentication headers in inter-service calls
- Authentication middleware exists but not integrated across services

**Solution Steps:**

1. **Generate Service API Keys** (30 min)
   ```bash
   # In Python shell
   from backend.shared.auth import generate_api_key
   orchestrator_key = generate_api_key("orchestrator")
   analyzer_key = generate_api_key("analyzer")
   monitor_key = generate_api_key("monitor")
   ```

2. **Update Environment Variables** (15 min)
   ```bash
   # Add to .env
   ORCHESTRATOR_API_KEY=your_generated_key
   ANALYZER_API_KEY=your_generated_key
   MONITOR_API_KEY=your_generated_key
   ```

3. **Update Orchestrator** (2 hours)
   ```javascript
   // backend/orchestrator/index.js
   const API_KEY = process.env.ORCHESTRATOR_API_KEY;
   
   // Add to all Knowledge Engine calls
   headers: {
     'Authorization': `Bearer ${API_KEY}`,
     'X-Service-Auth': 'true'
   }
   ```

4. **Update Knowledge Engine** (1 hour)
   ```python
   # backend/knowledge_engine/api.py
   from backend.shared.middleware import auth_middleware
   
   # Add service auth bypass for authenticated services
   @app.middleware("http")
   async def verify_service_auth(request, call_next):
       if request.headers.get("X-Service-Auth") == "true":
           # Verify service API key
           key = request.headers.get("Authorization")
           if verify_service_api_key(key):
               return await call_next(request)
   ```

5. **Update Go Analyzer** (1 hour)
   ```go
   // backend/realtime_analyzer/api/server.go
   // Add service auth headers to all service calls
   req.Header.Set("Authorization", "Bearer "+apiKey)
   req.Header.Set("X-Service-Auth", "true")
   ```

6. **Test Integration** (1 hour)
   - Start all services
   - Test orchestrator → knowledge engine calls
   - Test analyzer → knowledge engine calls
   - Test monitor → knowledge engine calls
   - Verify 401 errors are resolved

**Files to Modify:**
- `backend/orchestrator/index.js`
- `backend/knowledge_engine/api.py`
- `backend/shared/auth.py` (add service key verification)
- `backend/realtime_analyzer/api/server.go`

---

### Task 2: Nmap Binary Configuration
**Status:** ⚠️ BLOCKER - Analyzer cannot find nmap  
**Effort:** 1 day  
**Priority:** P0 - CRITICAL

**Problem:**
- Real-time Analyzer cannot find nmap binary in PATH
- Scanning functionality is broken

**Solution Steps:**

1. **Install Nmap** (15 min)
   ```bash
   # macOS
   brew install nmap
   
   # Ubuntu/Debian
   sudo apt-get install nmap
   
   # Docker
   # Add to Dockerfile:
   RUN apt-get update && apt-get install -y nmap
   ```

2. **Configure Nmap Path** (30 min)
   ```bash
   # Add to .env
   NMAP_PATH=/usr/local/bin/nmap  # or where nmap is installed
   ```

3. **Update Go Analyzer** (1 hour)
   ```go
   // backend/realtime_analyzer/config/config.go
   NmapPath string = os.Getenv("NMAP_PATH")
   
   // backend/realtime_analyzer/scanner/scanner.go
   cmd := exec.Command(config.NmapPath, "-sV", target)
   ```

4. **Add Fallback** (30 min)
   ```go
   // Try to find nmap in PATH if not configured
   if config.NmapPath == "" {
       path, err := exec.LookPath("nmap")
       if err != nil {
           return fmt.Errorf("nmap not found in PATH")
       }
       config.NmapPath = path
   }
   ```

5. **Test Scanning** (1 hour)
   - Start analyzer service
   - Test scan against localhost
   - Verify nmap output is parsed correctly
   - Test error handling when nmap is unavailable

**Files to Modify:**
- `.env`
- `backend/realtime_analyzer/config/config.go`
- `backend/realtime_analyzer/scanner/scanner.go`
- `docker-compose.yml` (if using Docker)

---

## 📊 Verification Checklist

### After Task 1 (Service Auth)
- [ ] All services start without errors
- [ ] Orchestrator can call Knowledge Engine without 401
- [ ] Analyzer can call Knowledge Engine without 401
- [ ] Monitor can call Knowledge Engine without 401
- [ ] WebSocket connections work properly
- [ ] Dashboard shows live updates

### After Task 2 (Nmap)
- [ ] Nmap is installed and accessible
- [ ] Analyzer can find nmap binary
- [ ] Scanning works against test targets
- [ ] Scan results are parsed correctly
- [ ] Error handling works when nmap is unavailable

### Full Integration Test
- [ ] Start full engagement pipeline from dashboard
- [ ] Target is scanned successfully
- [ ] Attack chains are generated
- [ ] OpSec assessment completes
- [ ] Results stream to dashboard in real-time
- [ ] Engagement is persisted to database

---

## 🎯 Week 2-4: Phase 2 Quick Reference

### Redis Caching (4 days)
```bash
# Add to docker-compose.yml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"

# Add to requirements.txt
redis[hiredis]==5.0.0
```

### Connection Pooling (3 days)
```python
# backend/shared/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

### Async Task Queue (5 days)
```bash
# Add to docker-compose.yml
celery:
  build: ./backend/celery
  depends_on:
    - redis
    - postgresql
```

### Load Balancing (7 days)
```nginx
# Add nginx to docker-compose.yml
upstream knowledge_engine {
    least_conn;
    server knowledge_engine_1:8000;
    server knowledge_engine_2:8000;
}
```

---

## 📝 Common Commands

### Test Service Auth
```bash
# Test orchestrator auth
curl -H "Authorization: Bearer $ORCHESTRATOR_API_KEY" \
     -H "X-Service-Auth: true" \
     http://localhost:8010/search
```

### Test Nmap
```bash
# Test nmap installation
nmap --version

# Test analyzer scan
curl -X POST http://localhost:8001/scan \
  -H "Content-Type: application/json" \
  -d '{"target":"127.0.0.1"}'
```

### Check Service Health
```bash
# Knowledge Engine
curl http://localhost:8010/health

# Orchestrator
curl http://localhost:3001/health

# Analyzer
curl http://localhost:8001/health
```

---

## 🔧 Troubleshooting

### 401 Errors
```bash
# Check if API keys are set
echo $ORCHESTRATOR_API_KEY

# Check service logs
docker logs orchestrator
docker logs knowledge_engine

# Test auth endpoint
curl -X POST http://localhost:8010/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Nmap Not Found
```bash
# Find nmap location
which nmap

# Test nmap directly
nmap -sV 127.0.0.1

# Check analyzer logs
docker logs analyzer
```

### Service Connection Issues
```bash
# Check if services are running
docker ps

# Check service logs
docker logs orchestrator
docker logs knowledge_engine

# Test service connectivity
curl http://localhost:8010/health
curl http://localhost:3001/health
```

---

## 📞 Support

For detailed information, see:
- `MAJOR_ENHANCEMENT_PLAN.md` - Full 16-week roadmap
- `AGENTS.md` - Project architecture and API reference
- Backend service READMEs in `backend/*/README.md`

---

**Next Steps:**
1. Complete Week 1 tasks (service auth + nmap)
2. Run full integration test
3. Begin Phase 2 implementation (Week 2)
4. Track progress using MAJOR_ENHANCEMENT_PLAN.md