# OpsecAI Service Management Scripts

This directory contains scripts to manage all OpsecAI platform services easily.

## Available Scripts

### 🚀 `start-all.sh` - Start Services
Start all or specific services for the OpsecAI platform.

```bash
# Start all services (infrastructure + backend + frontend)
./start-all.sh

# Start only infrastructure services (postgres, qdrant, redis)
./start-all.sh infra

# Start only backend services
./start-all.sh backend

# Start only frontend dashboard
./start-all.sh frontend
```

### 🛑 `stop-all.sh` - Stop Services
Stop all or specific services.

```bash
# Stop all services
./stop-all.sh

# Stop all services and remove volumes (deletes data)
./stop-all.sh volumes

# Stop specific service
./stop-all.sh knowledge-engine
./stop-all.sh dashboard
```

### 📊 `status.sh` - Check Status
Check the status and health of services.

```bash
# Show quick status summary
./status.sh

# Show Docker container status
./status.sh docker

# Perform health check on all service endpoints
./status.sh health

# Show detailed service information (resource usage, logs)
./status.sh detailed
```

### 📋 `logs.sh` - View Logs
View logs from services.

```bash
# Follow logs from all services
./logs.sh

# Follow logs from specific service
./logs.sh knowledge-engine
./logs.sh orchestrator

# Follow infrastructure logs
./logs.sh infra

# Follow backend service logs
./logs.sh backend

# Show service status
./logs.sh status
```

## Services Overview

### Infrastructure Services
- **PostgreSQL** (port 5432) - Primary database
- **Qdrant** (ports 6333, 6334) - Vector database for semantic search
- **Redis** (port 6379) - Cache and message broker

### Backend Services
- **Knowledge Engine** (port 8000) - Core API for attack knowledge and semantic search
- **OpSec Monitor** (port 8002) - Operational security monitoring
- **Real-time Analyzer** (port 8001) - Real-time attack analysis
- **Orchestrator** (port 3001) - Service orchestration and coordination
- **Integration Hub** (port 8500) - Third-party integrations

### Frontend Services
- **Dashboard** (port 3000) - Web UI for the platform

## Service URLs

Once services are started, you can access them at:

- **Dashboard**: http://localhost:3000
- **Orchestrator**: http://localhost:3001
- **Knowledge Engine API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Real-time Analyzer**: http://localhost:8001
- **OpSec Monitor**: http://localhost:8002
- **Integration Hub**: http://localhost:8500
- **PostgreSQL**: localhost:5432
- **Qdrant**: http://localhost:6333
- **Redis**: localhost:6379

## Common Workflows

### Development Setup
```bash
# Start infrastructure only for local development
./start-all.sh infra

# Then start backend services individually as needed
./start-all.sh backend
```

### Full Platform Start
```bash
# Start everything at once
./start-all.sh all

# Check if everything is running
./status.sh health

# View logs if needed
./logs.sh
```

### Clean Restart
```bash
# Stop everything and remove data
./stop-all.sh volumes

# Start fresh
./start-all.sh all
```

### Troubleshooting
```bash
# Check service status
./status.sh docker

# Check service health
./status.sh health

# View logs for problematic service
./logs.sh knowledge-engine

# Get detailed information
./status.sh detailed
```

## Requirements

- Docker
- Docker Compose (or Docker Compose plugin)
- Make sure ports 3000, 3001, 5432, 6333, 6334, 6379, 8000, 8001, 8002, 8500 are available

## Notes

- Scripts use colored output for better readability
- All scripts include error handling
- Logs are shown with `tail=100` by default
- Use `Ctrl+C` to stop following logs
- The scripts automatically detect whether to use `docker-compose` or `docker compose`

## Troubleshooting

### Port Conflicts
If you encounter port conflicts, you can modify the ports in `docker-compose.yml` or stop the conflicting services.

### Docker Not Running
Make sure Docker is running before using these scripts. The scripts will check and notify you if Docker is not available.

### Permission Issues
If you get permission errors, make sure the scripts are executable:
```bash
chmod +x *.sh
```

### Services Not Starting
Check the logs with `./logs.sh` to see error messages. Common issues:
- Database connection problems
- Missing environment variables
- Port conflicts
- Insufficient resources