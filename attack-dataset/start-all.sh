#!/bin/bash

# AutonomAI - Start All Services Script
# This script starts all services for the AutonomAI platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "docker-compose is not installed. Please install docker-compose and try again."
        exit 1
    fi
    print_success "docker-compose is available"
}

# Function to start infrastructure services
start_infrastructure() {
    print_header "Starting Infrastructure Services"
    
    cd "$SCRIPT_DIR"
    
    print_info "Starting PostgreSQL, Qdrant, and Redis..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d postgres qdrant redis
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" up -d postgres qdrant redis
    fi
    
    print_success "Infrastructure services started"
    
    # Wait for services to be healthy
    print_info "Waiting for services to be healthy..."
    sleep 10
}

# Function to start backend services
start_backend_services() {
    print_header "Starting Backend Services"
    
    cd "$SCRIPT_DIR"
    
    print_info "Starting Knowledge Engine, OpSec Monitor, Real-time Analyzer, Orchestrator, and Integration Hub..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d knowledge-engine opsec-monitor realtime-analyzer orchestrator integration-hub
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" up -d knowledge-engine opsec-monitor realtime-analyzer orchestrator integration-hub
    fi
    
    print_success "Backend services started"
    
    # Wait for services to be ready
    print_info "Waiting for backend services to be ready..."
    sleep 15
}

# Function to start frontend
start_frontend() {
    print_header "Starting Frontend Dashboard"
    
    cd "$SCRIPT_DIR"
    
    print_info "Starting Dashboard..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d dashboard
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" up -d dashboard
    fi
    
    print_success "Frontend dashboard started"
}

# Function to start all services
start_all() {
    print_header "Starting All AutonomAI Services"
    
    check_docker
    check_docker_compose
    
    start_infrastructure
    start_backend_services
    start_frontend
    
    print_header "All Services Started Successfully"
    print_info "Service URLs:"
    echo "  • Dashboard:           http://localhost:3000"
    echo "  • Orchestrator:        http://localhost:3001"
    echo "  • Knowledge Engine:    http://localhost:8000"
    echo "  • Real-time Analyzer:  http://localhost:8001"
    echo "  • OpSec Monitor:       http://localhost:8002"
    echo "  • Integration Hub:     http://localhost:8500"
    echo "  • PostgreSQL:          localhost:5432"
    echo "  • Qdrant:              http://localhost:6333"
    echo "  • Redis:               localhost:6379"
    echo ""
    print_info "To view logs, run: ./logs.sh"
    print_info "To stop services, run: ./stop-all.sh"
}

# Function to start only infrastructure
start_infrastructure_only() {
    print_header "Starting Infrastructure Only"
    check_docker
    check_docker_compose
    start_infrastructure
    print_success "Infrastructure services started"
}

# Function to start only backend
start_backend_only() {
    print_header "Starting Backend Services Only"
    check_docker
    check_docker_compose
    start_backend_services
    print_success "Backend services started"
}

# Function to start only frontend
start_frontend_only() {
    print_header "Starting Frontend Only"
    check_docker
    check_docker_compose
    start_frontend
    print_success "Frontend started"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTION]

Start all services for the AutonomAI platform.

OPTIONS:
    all             Start all services (infrastructure + backend + frontend)
    infra           Start only infrastructure services (postgres, qdrant, redis)
    backend         Start only backend services
    frontend        Start only frontend dashboard
    help            Show this help message

EXAMPLES:
    $0 all           # Start all services
    $0 infra         # Start only infrastructure
    $0 backend       # Start only backend services
    $0 frontend      # Start only frontend

EOF
}

# Main script logic
case "${1:-all}" in
    all)
        start_all
        ;;
    infra)
        start_infrastructure_only
        ;;
    backend)
        start_backend_only
        ;;
    frontend)
        start_frontend_only
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Invalid option: $1"
        show_usage
        exit 1
        ;;
esac