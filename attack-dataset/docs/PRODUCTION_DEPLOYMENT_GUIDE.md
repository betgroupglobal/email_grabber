# OpsecAI Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the OpsecAI platform in a high-performance, production-ready environment using Docker containers.

## Architecture

### Infrastructure Components

- **PostgreSQL**: Primary database for engagement data and user management
- **Qdrant**: Vector database for ML model embeddings and similarity search
- **Redis**: Caching layer and session management
- **Nginx**: Reverse proxy, SSL termination, and load balancing
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Visualization dashboards and alerting
- **cAdvisor**: Container performance monitoring

### Application Services

- **Knowledge Engine**: Attack dataset processing and ML model serving
- **Orchestrator**: Attack chain execution and workflow management
- **Integration Hub**: Third-party tool integration and plugin system
- **Dashboard**: Next.js frontend application

## Prerequisites

### System Requirements

- **CPU**: 8+ cores recommended
- **Memory**: 32GB+ RAM recommended
- **Storage**: 500GB+ SSD storage
- **Network**: 1Gbps+ network connection
- **OS**: Linux (Ubuntu 22.04+ recommended) or macOS with Docker Desktop

### Software Requirements

- Docker Engine 24.0+
- Docker Compose 2.20+
- OpenSSL (for SSL certificate generation)
- Git

### Domain Requirements

- Registered domain name
- DNS configuration pointing to your server
- SSL certificates (Let's Encrypt recommended)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-org/attack-dataset.git
cd attack-dataset
```

### 2. Configure Environment Variables

```bash
cp .env.production .env
# Edit .env with your production values
```

**Critical Security Settings:**
- Generate strong passwords for database and services
- Update all API keys with secure values
- Configure proper domain names
- Set up SSL certificate paths

### 3. Generate SSL Certificates

**Option A: Let's Encrypt (Recommended)**
```bash
# Install certbot
sudo apt-get install certbot

# Generate certificates
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates to project
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem config/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem config/nginx/ssl/key.pem
```

**Option B: Self-Signed (Development Only)**
```bash
# The deployment script will generate self-signed certificates automatically
./scripts/deploy-production.sh deploy
```

### 4. Configure Nginx

Edit `config/nginx/conf.d/default.conf`:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

### 5. Deploy Using Script

```bash
chmod +x scripts/deploy-production.sh
./scripts/deploy-production.sh deploy
```

## Manual Deployment

### 1. Start Infrastructure Services

```bash
docker-compose -f docker-compose.prod.yml --env-file .env up -d postgres qdrant redis
```

### 2. Start Application Services

```bash
docker-compose -f docker-compose.prod.yml --env-file .env up -d knowledge-engine orchestrator integration-hub
```

### 3. Start Frontend and Proxy

```bash
docker-compose -f docker-compose.prod.yml --env-file .env up -d dashboard nginx
```

### 4. Start Monitoring Stack

```bash
docker-compose -f docker-compose.prod.yml --env-file .env up -d prometheus grafana cadvisor
```

## Configuration

### Database Optimization

Edit `config/postgres/postgresql.conf`:
```ini
# Memory Settings
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Connection Settings
max_connections = 200
work_mem = 32MB

# Query Optimization
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Redis Configuration

Edit `config/redis/redis.conf`:
```ini
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

### Resource Limits

Adjust in `docker-compose.prod.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
    reservations:
      cpus: '1.0'
      memory: 2G
```

## Monitoring

### Access Grafana

- URL: https://yourdomain.com:3001
- Default credentials: admin / (set in .env)
- Pre-configured dashboards for all services

### Key Metrics to Monitor

1. **System Resources**
   - CPU utilization
   - Memory usage
   - Disk I/O
   - Network traffic

2. **Application Performance**
   - Request latency
   - Error rates
   - Throughput
   - Database query performance

3. **Business Metrics**
   - Active engagements
   - Attack chain executions
   - Scan success rates
   - API response times

### Alerting

Configure alerts in `config/monitoring/alerts.yml`:
- Service downtime
- High error rates
- Performance degradation
- Resource exhaustion

## Scaling

### Horizontal Scaling

Increase replicas in `docker-compose.prod.yml`:
```yaml
deploy:
  replicas: 4
```

### Vertical Scaling

Increase resource limits:
```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 16G
```

### Database Scaling

1. **Read Replicas**: Configure PostgreSQL read replicas
2. **Connection Pooling**: Use PgBouncer for connection management
3. **Partitioning**: Implement table partitioning for large datasets

## Backup and Recovery

### Automated Backups

Add to crontab:
```bash
0 2 * * * /opt/opsec-platform/scripts/deploy-production.sh backup
```

### Manual Backup

```bash
./scripts/deploy-production.sh backup
```

### Database Restore

```bash
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U opsec_prod_user attack_db_prod < backup_file.sql
```

## Security

### Network Security

1. **Firewall Configuration**
```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

2. **Docker Network Isolation**
```bash
# Services communicate only within Docker network
# No ports exposed to host except through Nginx
```

### Application Security

1. **Environment Variables**: Store secrets in .env file, never commit to Git
2. **API Keys**: Rotate keys regularly, use different keys for each environment
3. **Rate Limiting**: Configure Nginx rate limits in nginx.conf
4. **CORS**: Configure proper CORS policies in application code

### SSL/TLS

1. **Certificate Renewal**: Set up automatic Let's Encrypt renewal
2. **Strong Ciphers**: Use only TLS 1.2+ with strong cipher suites
3. **HSTS**: Enable HTTP Strict Transport Security
4. **Certificate Rotation**: Implement certificate rotation process

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs <service_name>

# Check resource usage
docker stats

# Check disk space
df -h
```

### Performance Issues

```bash
# Check container metrics
docker stats

# View Grafana dashboards
# Check Prometheus metrics

# Analyze slow queries
docker-compose exec postgres psql -U opsec_prod_user -d attack_db_prod -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

### Database Connection Issues

```bash
# Check connection pool
docker-compose exec postgres psql -U opsec_prod_user -d attack_db_prod -c "SELECT count(*) FROM pg_stat_activity;"

# Check for long-running queries
docker-compose exec postgres psql -U opsec_prod_user -d attack_db_prod -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

## Maintenance

### Regular Tasks

1. **Daily**
   - Monitor system health
   - Check error logs
   - Review backup status

2. **Weekly**
   - Review performance metrics
   - Update security patches
   - Clean up old logs

3. **Monthly**
   - Review and update SSL certificates
   - Audit user access
   - Performance tuning
   - Capacity planning

### Updates

**Application Updates:**
```bash
git pull origin main
docker-compose -f docker-compose.prod.yml --env-file .env pull
docker-compose -f docker-compose.prod.yml --env-file .env up -d
```

**Docker Updates:**
```bash
# Update Docker images
docker-compose -f docker-compose.prod.yml --env-file .env build --no-cache
docker-compose -f docker-compose.prod.yml --env-file .env up -d
```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/production-deploy.yml`) provides:

1. **Automated Testing**: Runs tests on every push
2. **Security Scanning**: Trivy vulnerability scanning
3. **Image Building**: Multi-stage Docker builds
4. **Automated Deployment**: Deploys to production on main branch
5. **Rollback**: Automatic rollback on deployment failure
6. **Notifications**: Slack notifications for deployment status

### Required GitHub Secrets

- `SSH_PRIVATE_KEY`: SSH key for server access
- `DEPLOY_HOST`: Production server hostname
- `DEPLOY_USER`: SSH user for deployment
- `SLACK_WEBHOOK`: Slack webhook for notifications

## Performance Optimization

### Application Level

1. **Enable Compression**: Gzip enabled in Nginx
2. **CDN Integration**: Use CDN for static assets
3. **Database Indexing**: Ensure proper indexes on frequently queried columns
4. **Caching Strategy**: Redis caching for expensive operations
5. **Connection Pooling**: Optimize database connection pools

### Infrastructure Level

1. **SSD Storage**: Use SSDs for database and cache
2. **Resource Allocation**: Allocate sufficient CPU and memory
3. **Network Optimization**: Use dedicated network for container communication
4. **Load Balancing**: Distribute traffic across multiple instances

## Support

For issues and questions:
- Check logs: `./scripts/deploy-production.sh logs <service>`
- Review monitoring: Access Grafana dashboards
- Check documentation: Review inline code comments
- Contact support: Create GitHub issue with detailed information

## Appendix

### Port Reference

- 80: HTTP (redirected to HTTPS)
- 443: HTTPS
- 3000: Dashboard (internal)
- 3001: Orchestrator (internal)
- 8000: Knowledge Engine (internal)
- 8001: Real-time Analyzer (internal)
- 8002: OpSec Monitor (internal)
- 8500: Integration Hub (internal)
- 5432: PostgreSQL (internal)
- 6379: Redis (internal)
- 6333: Qdrant (internal)
- 9090: Prometheus (internal)
- 3001: Grafana (external)

### Service Dependencies

```
Dashboard → Orchestrator → Knowledge Engine
                ↓
         Integration Hub → Redis
                ↓
         OpSec Monitor
                ↓
         PostgreSQL, Qdrant
```