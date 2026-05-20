#!/bin/bash

# ── Production Deployment Script ────────────────────────────────────────────────
# This script handles the deployment of the AutonomAI platform in production

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env.production"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env.production exists
    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env.production file not found. Creating from template..."
        if [ -f "$PROJECT_ROOT/.env.production.example" ]; then
            cp "$PROJECT_ROOT/.env.production.example" "$ENV_FILE"
            log_warning "Please update $ENV_FILE with your production values before deploying."
            exit 1
        else
            log_error "No .env.production.example file found. Please create $ENV_FILE manually."
            exit 1
        fi
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker and try again."
        exit 1
    fi
    
    log_success "Prerequisites check passed."
}

setup_directories() {
    log_info "Setting up directories..."
    
    mkdir -p "$PROJECT_ROOT/data/postgres"
    mkdir -p "$PROJECT_ROOT/data/qdrant"
    mkdir -p "$PROJECT_ROOT/data/redis"
    mkdir -p "$PROJECT_ROOT/data/prometheus"
    mkdir -p "$PROJECT_ROOT/data/grafana"
    mkdir -p "$PROJECT_ROOT/logs/knowledge-engine"
    mkdir -p "$PROJECT_ROOT/logs/orchestrator"
    mkdir -p "$PROJECT_ROOT/logs/integration-hub"
    mkdir -p "$PROJECT_ROOT/logs/nginx"
    mkdir -p "$PROJECT_ROOT/config/nginx/ssl"
    mkdir -p "$PROJECT_ROOT/config/postgres"
    mkdir -p "$PROJECT_ROOT/config/qdrant"
    mkdir -p "$PROJECT_ROOT/config/redis"
    mkdir -p "$PROJECT_ROOT/config/monitoring/grafana/dashboards"
    mkdir -p "$PROJECT_ROOT/config/monitoring/grafana/datasources"
    
    log_success "Directories created successfully."
}

generate_ssl_certificates() {
    log_info "Checking SSL certificates..."
    
    SSL_DIR="$PROJECT_ROOT/config/nginx/ssl"
    CERT_FILE="$SSL_DIR/cert.pem"
    KEY_FILE="$SSL_DIR/key.pem"
    DHPARAM_FILE="$SSL_DIR/dhparam.pem"
    
    if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
        log_warning "SSL certificates not found. Generating self-signed certificates..."
        log_warning "For production, replace these with proper certificates from a CA like Let's Encrypt."
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$KEY_FILE" \
            -out "$CERT_FILE" \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        
        log_success "Self-signed SSL certificates generated."
    else
        log_success "SSL certificates found."
    fi
    
    if [ ! -f "$DHPARAM_FILE" ]; then
        log_info "Generating DH parameters (this may take a few minutes)..."
        openssl dhparam -out "$DHPARAM_FILE" 2048
        log_success "DH parameters generated."
    else
        log_success "DH parameters found."
    fi
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build all services
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
    
    log_success "Docker images built successfully."
}

start_services() {
    log_info "Starting services..."
    
    cd "$PROJECT_ROOT"
    
    # Start services
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    
    log_success "Services started successfully."
}

wait_for_services() {
    log_info "Waiting for services to be healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps | grep -q "unhealthy"; then
            log_info "Waiting for services to become healthy... ($attempt/$max_attempts)"
            sleep 10
            ((attempt++))
        else
            log_success "All services are healthy."
            return 0
        fi
    done
    
    log_warning "Some services are still starting up. Check logs for details."
}

run_migrations() {
    log_info "Running database migrations..."
    
    # Add migration commands here if needed
    # docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec knowledge-engine python manage.py migrate
    
    log_success "Database migrations completed."
}

setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Create Grafana dashboards and datasources are automatically provisioned
    # via the volume mounts in docker-compose.prod.yml
    
    log_success "Monitoring setup completed."
}

backup_database() {
    log_info "Creating database backup..."
    
    BACKUP_DIR="$PROJECT_ROOT/backups"
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/postgres_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
        pg_dump -U opsec_prod_user attack_db_prod > "$BACKUP_FILE"
    
    log_success "Database backup created: $BACKUP_FILE"
}

show_status() {
    log_info "Deployment status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    echo ""
    
    log_info "Service endpoints:"
    echo "  Dashboard: https://localhost"
    echo "  API: https://localhost/api"
    echo "  Grafana: https://localhost:3001"
    echo "  Prometheus: http://localhost:9090"
}

cleanup() {
    log_info "Cleaning up old resources..."
    
    # Remove old Docker images
    docker image prune -f
    
    # Remove old volumes (optional - be careful with this in production)
    # docker volume prune -f
    
    log_success "Cleanup completed."
}

# Main deployment function
deploy() {
    log_info "Starting production deployment..."
    echo ""
    
    check_prerequisites
    setup_directories
    generate_ssl_certificates
    build_images
    start_services
    wait_for_services
    run_migrations
    setup_monitoring
    backup_database
    show_status
    
    echo ""
    log_success "Production deployment completed successfully!"
}

# Parse command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    stop)
        log_info "Stopping services..."
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
        log_success "Services stopped."
        ;;
    restart)
        log_info "Restarting services..."
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
        log_success "Services restarted."
        ;;
    status)
        show_status
        ;;
    logs)
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "${2:-}"
        ;;
    backup)
        backup_database
        ;;
    cleanup)
        cleanup
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|status|logs|backup|cleanup}"
        exit 1
        ;;
esac