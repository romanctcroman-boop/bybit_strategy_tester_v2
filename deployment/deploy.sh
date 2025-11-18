#!/bin/bash

# Production deployment script for MCP Server
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Validate environment variables
validate_environment() {
    log "Validating environment variables..."
    
    required_vars=("DB_PASSWORD" "REDIS_PASSWORD" "GRAFANA_PASSWORD")
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done
    
    # Validate .env file exists
    if [[ ! -f ".env" ]]; then
        warn ".env file not found, creating from template"
        cp .env.example .env 2>/dev/null || warn "No .env.example found"
    fi
}

# Check system dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    local deps=("docker" "docker-compose")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error "$dep is not installed"
        fi
    done
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    # Wait for PostgreSQL to be ready
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker-compose exec -T postgres pg_isready -U mcp_user; then
            break
        fi
        log "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    if [[ $attempt -gt $max_attempts ]]; then
        error "Database is not ready after $max_attempts attempts"
    fi
    
    # Run Alembic migrations
    if docker-compose exec -T mcp-server alembic upgrade head; then
        log "Database migrations completed successfully"
    else
        error "Database migrations failed"
    fi
}

# Perform health check
perform_health_check() {
    log "Performing health check..."
    
    local max_attempts=20
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            log "Health check passed"
            return 0
        fi
        log "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 5
        ((attempt++))
    done
    
    error "Health check failed after $max_attempts attempts"
}

# Backup existing deployment
backup_existing() {
    if docker-compose ps | grep -q "Up"; then
        log "Backing up existing deployment..."
        docker-compose exec -T postgres pg_dump -U mcp_user mcp_db > "backup_$(date +%Y%m%d_%H%M%S).sql" || warn "Database backup failed"
    fi
}

# Main deployment function
deploy() {
    log "Starting MCP Server deployment..."
    
    validate_environment
    check_dependencies
    backup_existing
    
    # Build and start services
    log "Building and starting services..."
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    
    # Wait for services to start
    sleep 10
    
    run_migrations
    perform_health_check
    
    log "Deployment completed successfully!"
    log "Services:"
    log "  MCP Server: http://localhost:8000"
    log "  Prometheus: http://localhost:9090"
    log "  Grafana:    http://localhost:3000 (admin:${GRAFANA_PASSWORD})"
}

# Rollback function
rollback() {
    log "Initiating rollback..."
    docker-compose down
    # Additional rollback logic can be added here
    log "Rollback completed"
}

# Parse command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    health)
        perform_health_check
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|health}"
        exit 1
        ;;
esac