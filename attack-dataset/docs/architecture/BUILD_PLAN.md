# OpsecAI Build Plan

**Comprehensive build and deployment guide for OpsecAI services**

---

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Development Build](#development-build)
- [Docker Build](#docker-build)
- [Production Build](#production-build)
- [Testing & Validation](#testing--validation)
- [CI/CD Pipeline](#cicd-pipeline)
- [Dependency Management](#dependency-management)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Build Reference](#build-reference)

---

## Overview

OpsecAI is a multi-service application with the following components:

| Service | Language | Port | Purpose |
|---------|----------|------|---------|
| Knowledge Engine | Python/FastAPI | 8010 | Semantic search & attack chain building |
| Real-time Analyzer | Go | 8001 | Nmap scanning & fingerprinting |
| OpSec Monitor | Python/FastAPI | 8002 | Real-time OpSec risk assessment |
| Orchestrator | Node.js | 3001 | Pipeline coordination & WebSocket server |
| Integration Hub | Python/FastAPI | 8500 | External tool & API integrations |
| Dashboard | React | 3100 | Real-time visualization UI |
| PostgreSQL | - | 5432 | Structured data storage |
| Qdrant | - | 6333 | Vector database for semantic search |
| Redis | - | 6379 | Caching & task queue |

### Build Strategies

- **Development**: Local services with hot reload
- **Docker**: Containerized services for consistent environments
- **Production**: Optimized containers with security hardening

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Build Pipeline                        │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Development  │    │    Docker     │    │  Production  │
│     Local     │    │  Compose      │    │  Deployed     │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Build Artifacts│
                    │  - Docker images│
                    │  - Binaries     │
                    │  - Bundles      │
                    └─────────────────┘
```

---

## Prerequisites

### System Requirements

**Development Environment:**
- CPU: 4 cores minimum, 8 cores recommended
- RAM: 8GB minimum, 16GB recommended
- Disk: 20GB free space

**Production Environment:**
- CPU: 8 cores minimum
- RAM: 16GB minimum
- Disk: 50GB SSD

### Software Requirements

**Core Dependencies:**
```bash
# Python 3.11+
python3 --version  # >= 3.11

# Go 1.22+
go version  # >= 1.22

# Node.js 20+
node --version  # >= 20
npm --version  # >= 9

# Docker & Docker Compose
docker --version  # >= 24.0
docker compose version  # >= 2.20

# Git
git --version  # >= 2.30
```

**Platform-Specific:**

**macOS:**
```bash
# Install via Homebrew
brew install python3 go node docker docker-compose

# Nmap for analyzer
brew install nmap

# PostgreSQL client (optional)
brew install postgresql
```

**Ubuntu/Debian:**
```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip golang nodejs npm docker.io docker-compose nmap

# Add user to docker group
sudo usermod -aG docker $USER
```

**Windows (WSL2):**
```bash
# Install WSL2 with Ubuntu
# Then follow Ubuntu instructions above
```

### Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd attack-dataset

# Create environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

---

## Development Build

### Quick Start

```bash
# Start all services in development mode
./start.sh
```

This script:
1. Starts PostgreSQL and Qdrant via Docker
2. Installs Python dependencies
3. Runs dataset ingestion
4. Starts all backend services
5. Starts React dashboard with hot reload

### Manual Development Build

**1. Infrastructure (Docker):**
```bash
# Start only infrastructure services
docker compose up -d postgres qdrant redis

# Verify services are healthy
docker compose ps
```

**2. Knowledge Engine:**
```bash
cd backend/knowledge_engine

# Install dependencies
pip install -r requirements.txt

# Run ingestion (first time only)
python ingestor.py

# Start API server with hot reload
uvicorn api:app --host 0.0.0.0 --port 8010 --reload
```

**3. OpSec Monitor:**
```bash
cd backend/opsec_monitor

# Install dependencies
pip install -r requirements.txt

# Start with hot reload
uvicorn monitor:app --host 0.0.0.0 --port 8002 --reload
```

**4. Real-time Analyzer:**
```bash
cd backend/realtime_analyzer

# Build Go binary
go build -o /tmp/opsec-analyzer .

# Run with environment variables
ANALYZER_ADDR=:8001 \
KNOWLEDGE_ENGINE_URL=http://localhost:8010 \
SERVICE_API_KEY_ANALYZER=$SERVICE_API_KEY_ANALYZER \
/tmp/opsec-analyzer
```

**5. Orchestrator:**
```bash
cd backend/orchestrator

# Install dependencies
npm install

# Start with environment variables
PORT=3001 \
KNOWLEDGE_ENGINE_URL=http://localhost:8010 \
ANALYZER_URL=http://localhost:8001 \
OPSEC_URL=http://localhost:8002 \
node index.js
```

**6. Integration Hub:**
```bash
cd backend/integrations

# Install dependencies
pip install -r requirements.txt

# Start with hot reload
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

**7. Dashboard:**
```bash
cd frontend/dashboard

# Install dependencies
npm install

# Start development server
npm start
```

### Development Features

- **Hot Reload**: Automatic restart on code changes
- **Debug Logging**: Verbose output for troubleshooting
- **Source Maps**: Full stack traces for debugging
- **Live Reload**: Browser auto-refresh for frontend

---

## Docker Build

### Quick Start

```bash
# Build and start all services
docker compose up --build

# Start in detached mode
docker compose up --build -d

# View logs
docker compose logs -f
```

### Docker Build Commands

**Build All Services:**
```bash
docker compose build
```

**Build Specific Service:**
```bash
docker compose build knowledge-engine
docker compose build realtime-analyzer
docker compose build orchestrator
docker compose build dashboard
```

**Rebuild Without Cache:**
```bash
docker compose build --no-cache
```

**Multi-Platform Build:**
```bash
# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 \
  -t opsecai/knowledge-engine:latest \
  backend/knowledge_engine
```

### Docker Service Management

**Start Services:**
```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d postgres qdrant knowledge-engine
```

**Stop Services:**
```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Stop but keep volumes
docker compose down --remove-orphans
```

**Restart Services:**
```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart knowledge-engine
```

**View Logs:**
```bash
# All logs
docker compose logs

# Specific service logs
docker compose logs knowledge-engine

# Follow logs
docker compose logs -f knowledge-engine
```

**Service Status:**
```bash
docker compose ps
```

### Docker Optimization

**Layer Caching:**
```dockerfile
# Good: Order commands by change frequency
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Bad: Copies everything before installing deps
COPY . .
RUN pip install -r requirements.txt
```

**Multi-Stage Builds:**
```dockerfile
# Example from realtime_analyzer/Dockerfile
FROM golang:1.22-alpine AS builder
RUN CGO_ENABLED=0 go build -o /analyzer .

FROM alpine:3.19
COPY --from=builder /analyzer /usr/local/bin/analyzer
```

**Image Size Reduction:**
```bash
# Scan for vulnerabilities
docker scan opsecai/knowledge-engine:latest

# Remove unused dependencies
docker image prune -a

# Use .dockerignore to exclude unnecessary files
```

---

## Production Build

### Production Configuration

**Environment Variables:**
```bash
# .env.production
POSTGRES_USER=opsec_prod
POSTGRES_PASSWORD=<strong-random-password>
POSTGRES_DB=attack_db_prod

SERVICE_API_KEY_ORCHESTRATOR=<strong-random-key>
SERVICE_API_KEY_ANALYZER=<strong-random-key>
SERVICE_API_KEY_MONITOR=<strong-random-key>
SERVICE_API_KEY_KNOWLEDGE=<strong-random-key>

OPENROUTER_API_KEY=<production-api-key>
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Security settings
DEBUG=false
LOG_LEVEL=INFO
```

**Docker Compose Production:**
```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_prod_data:/var/lib/postgresql/data
    restart: unless-stopped

  # Add similar production configs for other services
```

### Production Build Process

**1. Build Production Images:**
```bash
# Build with production tag
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Tag images for registry
docker tag opsecai/knowledge-engine:latest registry.example.com/opsecai/knowledge-engine:v1.0.0
```

**2. Push to Registry:**
```bash
# Login to registry
docker login registry.example.com

# Push images
docker push registry.example.com/opsecai/knowledge-engine:v1.0.0
```

**3. Deploy Production:**
```bash
# Deploy with production compose file
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use Kubernetes
kubectl apply -f k8s/production/
```

### Production Hardening

**Security:**
```bash
# Run as non-root user
USER 1000:1000

# Read-only filesystem
READONLY_ROOT_FILESYSTEM=true

# Drop capabilities
CAP_DROP=ALL
CAP_ADD=NET_BIND_SERVICE
```

**Resource Limits:**
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 1G
```

**Health Checks:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Testing & Validation

### Unit Tests

**Python Services:**
```bash
cd backend/knowledge_engine
pip install pytest pytest-cov
pytest tests/ --cov=.
```

**Go Service:**
```bash
cd backend/realtime_analyzer
go test ./...
go test -cover ./...
```

**Node.js Service:**
```bash
cd backend/orchestrator
npm test
```

**React Dashboard:**
```bash
cd frontend/dashboard
npm test
```

### Integration Tests

**Service Health:**
```bash
# Test all services are running
curl http://localhost:8010/health  # Knowledge Engine
curl http://localhost:8001/health  # Real-time Analyzer
curl http://localhost:8002/health  # OpSec Monitor
curl http://localhost:3001/health  # Orchestrator
curl http://localhost:8500/health  # Integration Hub
```

**API Endpoints:**
```bash
# Test Knowledge Engine
curl -X POST http://localhost:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query":"sql injection"}'

# Test Orchestrator
curl -X POST http://localhost:3001/engage \
  -H "Content-Type: application/json" \
  -d '{"target":"127.0.0.1","aggression_level":1}'
```

### Load Testing

**Simple Load Test:**
```bash
# Install Apache Bench
ab -n 1000 -c 10 http://localhost:8010/search
```

**Locust:**
```python
# locustfile.py
from locust import HttpUser, task

class KnowledgeEngineUser(HttpUser):
    @task
    def search(self):
        self.client.post("/search", json={"query": "test"})
```

```bash
locust -f locustfile.py --host=http://localhost:8010
```

### Smoke Tests

**Post-Deployment Validation:**
```bash
#!/bin/bash
# smoke_test.sh

echo "Running smoke tests..."

# Test infrastructure
docker compose ps postgres | grep -q "healthy"
docker compose ps qdrant | grep -q "healthy"

# Test services
curl -f http://localhost:8010/health || exit 1
curl -f http://localhost:8001/health || exit 1
curl -f http://localhost:8002/health || exit 1
curl -f http://localhost:3001/health || exit 1

# Test basic functionality
curl -X POST http://localhost:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' || exit 1

echo "Smoke tests passed!"
```

---

## CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: '1.22'
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Run tests
        run: |
          cd backend/knowledge_engine && pip install -r requirements.txt && pytest
          cd backend/realtime_analyzer && go test ./...
          cd frontend/dashboard && npm test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: docker compose build
      
      - name: Push to registry
        run: |
          echo ${{ secrets.REGISTRY_PASSWORD }} | docker login -u ${{ secrets.REGISTRY_USER }} --password-stdin
          docker push opsecai/knowledge-engine:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # Deployment commands
          kubectl apply -f k8s/production/
```

### GitLab CI Example

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  script:
    - cd backend/knowledge_engine && pip install -r requirements.txt && pytest
    - cd backend/realtime_analyzer && go test ./...
    - cd frontend/dashboard && npm test

build:
  stage: build
  script:
    - docker compose build
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker push $CI_REGISTRY_IMAGE:latest

deploy:
  stage: deploy
  only:
    - main
  script:
    - kubectl apply -f k8s/production/
```

---

## Dependency Management

### Python Dependencies

**Requirements Management:**
```bash
# Generate requirements.txt
pip freeze > requirements.txt

# Use pip-tools for better dependency management
pip install pip-tools
pip-compile requirements.in
pip-sync requirements.txt

# Security scanning
pip install safety
safety check
```

**requirements.txt Structure:**
```
# Core dependencies
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3

# Database
psycopg2-binary==2.9.9
qdrant-client==1.7.0

# AI/ML
openai==1.10.0
sentence-transformers==2.3.1
```

### Go Dependencies

**Dependency Management:**
```bash
# Initialize module
go mod init opsecai/analyzer

# Add dependency
go get github.com/gin-gonic/gin

# Tidy dependencies
go mod tidy

# Vendor dependencies (if needed)
go mod vendor

# Security scanning
go install golang.org/x/vuln/cmd/govulncheck@latest
govulncheck ./...
```

### Node.js Dependencies

**Package Management:**
```bash
# Install dependencies
npm install

# Audit for vulnerabilities
npm audit
npm audit fix

# Use npm ci for reproducible builds
npm ci

# Update dependencies
npm update
```

**package.json Best Practices:**
```json
{
  "scripts": {
    "start": "node index.js",
    "test": "jest",
    "lint": "eslint .",
    "build": "webpack --mode production"
  },
  "engines": {
    "node": ">=20.0.0",
    "npm": ">=9.0.0"
  }
}
```

---

## Performance Optimization

### Build Performance

**Docker Build Cache:**
```bash
# Use BuildKit for better caching
export DOCKER_BUILDKIT=1

# Parallel builds
docker compose build --parallel

# Use build cache mounts
docker build --mount type=cache,target=/root/.cache/go-build .
```

**Dependency Caching:**
```yaml
# GitHub Actions cache
- name: Cache Python dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### Runtime Performance

**Go Optimization:**
```bash
# Build with optimizations
go build -ldflags="-s -w" -o analyzer .

# Build for specific architecture
GOARCH=amd64 GOOS=linux go build -o analyzer .
```

**React Optimization:**
```bash
# Production build
npm run build

# Analyze bundle size
npm run build -- --profile
npx webpack-bundle-analyzer build/static/js/*.js
```

**Python Optimization:**
```bash
# Use uvicorn with multiple workers
uvicorn api:app --host 0.0.0.0 --port 8010 --workers 4

# Use gunicorn for production
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Troubleshooting

### Common Issues

**1. Port Already in Use**
```bash
# Find process using port
lsof -i :8010

# Kill process
kill -9 <PID>

# Or change port in .env
API_PORT=8011
```

**2. Docker Build Fails**
```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker compose build --no-cache

# Check Docker logs
docker compose logs knowledge-engine
```

**3. Python Import Errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python path
python -c "import sys; print(sys.path)"

# Use virtual environment
python -m venv venv
source venv/bin/activate
```

**4. Go Module Issues**
```bash
# Clear module cache
go clean -modcache

# Re-download dependencies
go mod download

# Update go.sum
go mod tidy
```

**5. Node.js npm Issues**
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Use different registry
npm install --registry=https://registry.npmjs.org
```

### Debug Mode

**Enable Debug Logging:**
```bash
# Python
export DEBUG=1
uvicorn api:app --log-level debug

# Go
export DEBUG=true
go run .

# Node.js
export DEBUG=*
node index.js
```

**Verbose Docker Build:**
```bash
docker compose build --progress=plain
DOCKER_BUILDKIT=0 docker compose build
```

### Health Check Issues

**Service Not Starting:**
```bash
# Check service logs
docker compose logs knowledge-engine

# Check service dependencies
docker compose ps

# Manual service start
docker compose up knowledge-engine
```

**Database Connection Issues:**
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Test database connection
psql -h localhost -U opsec -d attack_db

# Check database logs
docker compose logs postgres
```

---

## Build Reference

### Service-Specific Commands

**Knowledge Engine:**
```bash
# Development
cd backend/knowledge_engine
uvicorn api:app --reload --port 8010

# Docker
docker compose up knowledge-engine

# Production
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8010
```

**Real-time Analyzer:**
```bash
# Development
cd backend/realtime_analyzer
go run .

# Build
go build -o analyzer .

# Docker
docker compose up realtime-analyzer
```

**OpSec Monitor:**
```bash
# Development
cd backend/opsec_monitor
uvicorn monitor:app --reload --port 8002

# Docker
docker compose up opsec-monitor
```

**Orchestrator:**
```bash
# Development
cd backend/orchestrator
node index.js

# Docker
docker compose up orchestrator
```

**Integration Hub:**
```bash
# Development
cd backend/integrations
uvicorn main:app --reload --port 8500

# Docker
docker compose up integration-hub
```

**Dashboard:**
```bash
# Development
cd frontend/dashboard
npm start

# Production build
npm run build

# Docker
docker compose up dashboard
```

### Quick Reference Cards

**Development Quick Start:**
```bash
./start.sh
```

**Docker Quick Start:**
```bash
docker compose up --build
```

**Stop All Services:**
```bash
docker compose down
```

**View Logs:**
```bash
docker compose logs -f
```

**Rebuild Service:**
```bash
docker compose build <service>
docker compose up -d <service>
```

---

## Appendix A: Build Scripts

### Automated Build Script

```bash
#!/bin/bash
# build.sh - Automated build script

set -e

BUILD_TYPE=${1:-development}

echo "Building OpsecAI ($BUILD_TYPE)..."

case $BUILD_TYPE in
  development)
    ./start.sh
    ;;
  docker)
    docker compose up --build
    ;;
  production)
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
    ;;
  *)
    echo "Usage: ./build.sh [development|docker|production]"
    exit 1
    ;;
esac
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

SERVICES=(
  "http://localhost:8010/health"
  "http://localhost:8001/health"
  "http://localhost:8002/health"
  "http://localhost:3001/health"
  "http://localhost:8500/health"
)

for service in "${SERVICES[@]}"; do
  if curl -f -s "$service" > /dev/null; then
    echo "✓ $service"
  else
    echo "✗ $service"
    exit 1
  fi
done

echo "All services healthy!"
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-15 | OpsecAI Team | Initial release |

**Next Review Date:** 2026-08-15

---

## Additional Resources

- [AGENTS.md](../guides/AGENTS.md) - Project reference and architecture
- [INTEGRATIONS_BLUEPRINT.md](INTEGRATIONS_BLUEPRINT.md) - Integration system documentation
- [MAJOR_ENHANCEMENT_PLAN.md](MAJOR_ENHANCEMENT_PLAN.md) - Enhancement roadmap

**For build issues or questions, contact the DevOps team.**
