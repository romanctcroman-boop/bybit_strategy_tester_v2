#!/bin/bash
# Production Deployment Script for Bybit Strategy Tester
# Usage: ./deploy.sh [environment] [action]
# Example: ./deploy.sh production start

set -e

ENVIRONMENT=${1:-production}
ACTION=${2:-start}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# ============================================
# Pre-flight Checks
# ============================================
preflight_checks() {
    log_info "Running pre-flight checks..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        return 1
    fi
    log_success "Docker found: $(docker --version)"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        return 1
    fi
    log_success "Docker Compose found: $(docker-compose --version)"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        return 1
    fi
    log_success "Python found: $(python3 --version)"
    
    # Check .env file
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        log_error ".env.production file not found"
        return 1
    fi
    log_success ".env.production file found"
    
    log_success "All pre-flight checks passed!"
    return 0
}

# ============================================
# Deploy Monitoring Stack
# ============================================
deploy_monitoring() {
    log_info "Deploying monitoring stack..."
    
    cd "$PROJECT_ROOT/deployment"
    
    # Create config directories if they don't exist
    mkdir -p config/grafana/provisioning/dashboards
    mkdir -p config/grafana/provisioning/datasources
    
    # Start monitoring services
    docker-compose -f docker-compose-monitoring.yml up -d
    
    log_success "Monitoring stack deployed"
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check if services are up
    if docker ps | grep -q "elasticsearch-prod"; then
        log_success "Elasticsearch is running"
    else
        log_warning "Elasticsearch may not be running"
    fi
    
    if docker ps | grep -q "prometheus-prod"; then
        log_success "Prometheus is running"
    else
        log_warning "Prometheus may not be running"
    fi
    
    if docker ps | grep -q "grafana-prod"; then
        log_success "Grafana is running"
    else
        log_warning "Grafana may not be running"
    fi
}

# ============================================
# Deploy Application
# ============================================
deploy_application() {
    log_info "Deploying application..."
    
    cd "$PROJECT_ROOT"
    
    # Copy production env
    cp .env.production .env
    log_success "Environment file configured"
    
    # Create necessary directories
    mkdir -p logs data
    
    # Run database migrations
    log_info "Running database migrations..."
    python3 -m alembic upgrade head || log_warning "Migration may have failed"
    
    # Install/update Python dependencies
    log_info "Installing Python dependencies..."
    pip install -r requirements-dev.txt || log_warning "Some dependencies may have failed"
    
    log_success "Application deployed"
}

# ============================================
# Health Check
# ============================================
health_check() {
    log_info "Performing health checks..."
    
    local failed=0
    
    # Check API
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        log_success "API health check passed"
    else
        log_error "API health check failed"
        failed=$((failed + 1))
    fi
    
    # Check Redis
    if docker exec redis-prod redis-cli ping > /dev/null 2>&1; then
        log_success "Redis health check passed"
    else
        log_warning "Redis health check failed"
        failed=$((failed + 1))
    fi
    
    # Check Elasticsearch
    if curl -s http://localhost:9200/ > /dev/null 2>&1; then
        log_success "Elasticsearch health check passed"
    else
        log_warning "Elasticsearch health check failed"
        failed=$((failed + 1))
    fi
    
    # Check Prometheus
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus health check passed"
    else
        log_warning "Prometheus health check failed"
        failed=$((failed + 1))
    fi
    
    # Check Grafana
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        log_success "Grafana health check passed"
    else
        log_warning "Grafana health check failed"
        failed=$((failed + 1))
    fi
    
    return $failed
}

# ============================================
# Status
# ============================================
show_status() {
    log_info "System Status"
    
    echo ""
    echo "Docker Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "Services URLs:"
    echo "  API:        http://localhost:8000"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3000 (admin/changeme)"
    echo "  Kibana:     http://localhost:5601"
    echo "  Alertmanager: http://localhost:9093"
    
    echo ""
    echo "Database:"
    echo "  SQLite: $PROJECT_ROOT/data.sqlite3"
    echo "  Redis:  localhost:6379"
}

# ============================================
# Start Services
# ============================================
start_services() {
    log_info "Starting services..."
    
    # Start API in background
    cd "$PROJECT_ROOT"
    
    log_info "Starting Uvicorn API..."
    nohup python3 -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > .api.pid
    log_success "API started (PID: $API_PID)"
    
    # Start AI Agent Service
    log_info "Starting AI Agent Service..."
    nohup python3 -m backend.agents.agent_background_service > logs/ai_agent.log 2>&1 &
    AGENT_PID=$!
    echo $AGENT_PID > .agent.pid
    log_success "AI Agent Service started (PID: $AGENT_PID)"
    
    sleep 5
    health_check
}

# ============================================
# Stop Services
# ============================================
stop_services() {
    log_info "Stopping services..."
    
    # Stop API
    if [ -f "$PROJECT_ROOT/.api.pid" ]; then
        API_PID=$(cat "$PROJECT_ROOT/.api.pid")
        kill $API_PID 2>/dev/null || true
        rm "$PROJECT_ROOT/.api.pid"
        log_success "API stopped"
    fi
    
    # Stop AI Agent Service
    if [ -f "$PROJECT_ROOT/.agent.pid" ]; then
        AGENT_PID=$(cat "$PROJECT_ROOT/.agent.pid")
        kill $AGENT_PID 2>/dev/null || true
        rm "$PROJECT_ROOT/.agent.pid"
        log_success "AI Agent Service stopped"
    fi
    
    log_info "Stopping monitoring stack..."
    cd "$PROJECT_ROOT/deployment"
    docker-compose -f docker-compose-monitoring.yml down
    log_success "Monitoring stack stopped"
}

# ============================================
# Main
# ============================================
main() {
    log_info "Bybit Strategy Tester Production Deployment"
    echo "Environment: $ENVIRONMENT"
    echo "Action: $ACTION"
    echo ""
    
    case $ACTION in
        preflight)
            preflight_checks
            ;;
        deploy)
            preflight_checks && deploy_monitoring && deploy_application && health_check
            ;;
        start)
            start_services && show_status
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status && health_check
            ;;
        restart)
            stop_services && sleep 5 && start_services && show_status
            ;;
        *)
            echo "Usage: $0 [environment] [action]"
            echo "Actions: preflight, deploy, start, stop, status, restart"
            exit 1
            ;;
    esac
}

main "$@"

