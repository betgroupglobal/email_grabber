#!/bin/bash

# OpsecAI - Stop All Services Script
# This script stops all services for the OpsecAI platform

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
        print_error "Docker is not running."
        exit 1
    fi
}

# Function to stop all services
stop_all() {
    print_header "Stopping All OpsecAI Services"
    
    check_docker
    
    cd "$SCRIPT_DIR"
    
    print_info "Stopping all services..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" down
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" down
    fi
    
    print_success "All services stopped"
}

# Function to stop all services and remove volumes
stop_all_with_volumes() {
    print_header "Stopping All Services and Removing Volumes"
    
    check_docker
    
    cd "$SCRIPT_DIR"
    
    print_warning "This will delete all data in PostgreSQL, Qdrant, and Redis!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping services and removing volumes..."
        if command -v docker-compose &> /dev/null; then
            docker-compose -f "$DOCKER_COMPOSE_FILE" down -v
        else
            docker compose -f "$DOCKER_COMPOSE_FILE" down -v
        fi
        print_success "All services stopped and volumes removed"
    else
        print_info "Operation cancelled"
    fi
}

# Function to stop specific service
stop_service() {
    local service_name=$1
    print_header "Stopping Service: $service_name"
    
    check_docker
    
    cd "$SCRIPT_DIR"
    
    print_info "Stopping $service_name..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" stop "$service_name"
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" stop "$service_name"
    fi
    
    print_success "$service_name stopped"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTION]

Stop all services for the OpsecAI platform.

OPTIONS:
    all             Stop all services (default)
    volumes         Stop all services and remove volumes (deletes data)
    <service>       Stop specific service (e.g., knowledge-engine, dashboard)
    help            Show this help message

AVAILABLE SERVICES:
    knowledge-engine, opsec-monitor, realtime-analyzer, orchestrator, 
    integration-hub, dashboard, postgres, qdrant, redis

EXAMPLES:
    $0 all           # Stop all services
    $0 volumes       # Stop all services and delete data
    $0 dashboard     # Stop only dashboard
    $0 knowledge-engine  # Stop only knowledge engine

EOF
}

# Main script logic
case "${1:-all}" in
    all)
        stop_all
        ;;
    volumes)
        stop_all_with_volumes
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        # Check if it's a valid service name
        if [[ "$1" =~ ^(knowledge-engine|opsec-monitor|realtime-analyzer|orchestrator|integration-hub|dashboard|postgres|qdrant|redis)$ ]]; then
            stop_service "$1"
        else
            print_error "Invalid option: $1"
            show_usage
            exit 1
        fi
        ;;
esac