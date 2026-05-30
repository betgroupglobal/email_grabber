#!/bin/bash

# AutonomAI - Service Status Script
# This script checks the status and health of all AutonomAI platform services

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

# Service URLs (using parallel arrays for compatibility)
SERVICE_KEYS=("Dashboard" "Orchestrator" "Knowledge_Engine" "Realtime_Analyzer" "OpSec_Monitor" "Integration_Hub" "PostgreSQL" "Qdrant" "Redis")
SERVICE_URLS=("http://localhost:3000" "http://localhost:3001" "http://localhost:8000" "http://localhost:8001" "http://localhost:8002" "http://localhost:8500" "localhost:5432" "http://localhost:6333" "localhost:6379")
SERVICE_NAMES=("Dashboard" "Orchestrator" "Knowledge Engine" "Real-time Analyzer" "OpSec Monitor" "Integration Hub" "PostgreSQL" "Qdrant" "Redis")

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
        return 1
    fi
    return 0
}

# Function to check HTTP endpoint
check_http_endpoint() {
    local url=$1
    local service_name=$2
    
    if curl -s -f -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|404\|401"; then
        return 0
    else
        return 1
    fi
}

# Function to check TCP port
check_tcp_port() {
    local host=$1
    local port=$2
    local service_name=$3
    
    if nc -z -w 2 "$host" "$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to show Docker container status
show_docker_status() {
    print_header "Docker Container Status"
    
    if ! check_docker; then
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    else
        docker compose -f "$DOCKER_COMPOSE_FILE" ps
    fi
}

# Function to check service health
check_service_health() {
    print_header "Service Health Check"
    
    if ! check_docker; then
        return 1
    fi
    
    local all_healthy=true
    
    for i in "${!SERVICE_KEYS[@]}"; do
        local service_key="${SERVICE_KEYS[$i]}"
        local url="${SERVICE_URLS[$i]}"
        local display_name="${SERVICE_NAMES[$i]}"
        
        # Extract host and port for TCP check
        if [[ "$url" =~ ^http://([^:]+):([0-9]+)$ ]]; then
            local host="${BASH_REMATCH[1]}"
            local port="${BASH_REMATCH[2]}"
            
            if check_tcp_port "$host" "$port" "$display_name"; then
                print_success "$display_name is reachable at $url"
            else
                print_error "$display_name is NOT reachable at $url"
                all_healthy=false
            fi
        elif [[ "$url" =~ ^([^:]+):([0-9]+)$ ]]; then
            local host="${BASH_REMATCH[1]}"
            local port="${BASH_REMATCH[2]}"
            
            if check_tcp_port "$host" "$port" "$display_name"; then
                print_success "$display_name is reachable at $url"
            else
                print_error "$display_name is NOT reachable at $url"
                all_healthy=false
            fi
        fi
    done
    
    echo ""
    if [ "$all_healthy" = true ]; then
        print_success "All services are healthy!"
        return 0
    else
        print_error "Some services are not healthy"
        return 1
    fi
}

# Function to show detailed service information
show_detailed_info() {
    print_header "Detailed Service Information"
    
    if ! check_docker; then
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    
    print_info "Container Resource Usage:"
    echo ""
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        $(docker ps --format "{{.Names}}" --filter "name=attack-dataset") 2>/dev/null || \
        print_warning "Could not get container stats"
    
    echo ""
    print_info "Recent Container Logs (last 5 lines):"
    echo ""
    
    local services=("knowledge-engine" "orchestrator" "dashboard" "postgres" "qdrant" "redis")
    for service in "${services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "$service"; then
            echo -e "${BLUE}$service:${NC}"
            docker logs --tail 5 "$(docker ps --format "{{.Names}}" --filter "name=$service")" 2>/dev/null | tail -5
            echo ""
        fi
    done
}

# Function to show quick status summary
show_quick_status() {
    print_header "Quick Status Summary"
    
    if ! check_docker; then
        print_error "Docker is not running"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    
    # Count running containers
    local running_containers=$(docker ps --format "{{.Names}}" --filter "name=attack-dataset" | wc -l | tr -d ' ')
    local total_containers=$(docker ps -a --format "{{.Names}}" --filter "name=attack-dataset" | wc -l | tr -d ' ')
    
    print_info "Running Containers: $running_containers/$total_containers"
    
    if [ "$running_containers" -eq "$total_containers" ] && [ "$running_containers" -gt 0 ]; then
        print_success "All containers are running"
    elif [ "$running_containers" -gt 0 ]; then
        print_warning "Some containers are not running"
    else
        print_error "No containers are running"
    fi
    
    echo ""
    print_info "Service Endpoints:"
    for i in "${!SERVICE_KEYS[@]}"; do
        local display_name="${SERVICE_NAMES[$i]}"
        local url="${SERVICE_URLS[$i]}"
        echo "  • $display_name: $url"
    done
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTION]

Check the status and health of AutonomAI platform services.

OPTIONS:
    quick           Show quick status summary (default)
    docker          Show Docker container status
    health          Perform health check on all service endpoints
    detailed        Show detailed service information (resource usage, logs)
    help            Show this help message

EXAMPLES:
    $0               # Show quick status summary
    $0 docker        # Show Docker container status
    $0 health        # Check service health
    $0 detailed      # Show detailed information

EOF
}

# Main script logic
case "${1:-quick}" in
    quick)
        show_quick_status
        ;;
    docker)
        show_docker_status
        ;;
    health)
        check_service_health
        ;;
    detailed)
        show_detailed_info
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