#!/bin/bash

# FinTech Fraud Detection - Rollback Script
# Usage: ./rollback.sh [dev|staging|prod] [revision_number]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="eu-west-1"
CLUSTER_NAME="fintech-fraud-detection-cluster"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        log_error "aws cli is not installed"
        exit 1
    fi
    
    log_info "All prerequisites are met"
}

update_kubeconfig() {
    log_info "Updating kubeconfig for cluster: $CLUSTER_NAME"
    aws eks update-kubeconfig \
        --region $REGION \
        --name $CLUSTER_NAME
}

get_rollout_history() {
    local env=$1
    local namespace=$env
    
    log_info "Rollout history for $env environment:"
    helm history fintech-app -n $namespace
}

confirm_rollback() {
    local env=$1
    local revision=$2
    
    log_warn "You are about to rollback $env to revision $revision"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
}

perform_rollback() {
    local env=$1
    local namespace=$env
    local revision=$2
    
    log_info "Rolling back to revision $revision..."
    
    helm rollback fintech-app $revision -n $namespace
    
    if [ $? -eq 0 ]; then
        log_info "Rollback completed successfully"
    else
        log_error "Rollback failed"
        exit 1
    fi
}

wait_for_rollout() {
    local env=$1
    local namespace=$env
    
    log_info "Waiting for rollout to complete..."
    
    kubectl rollout status deployment/fintech-app-api -n $namespace --timeout=5m
    kubectl rollout status deployment/fintech-app-workers -n $namespace --timeout=5m
    
    log_info "Rollout completed successfully"
}

verify_rollback() {
    local env=$1
    local namespace=$env
    
    log_info "Verifying rollback..."
    
    # Check pod status
    kubectl get pods -n $namespace -l app=fintech-app
    
    # Get the service endpoint
    local service_endpoint=$(kubectl get svc fintech-app -n $namespace -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    if [ -z "$service_endpoint" ]; then
        log_warn "Could not get load balancer endpoint, using port-forward instead"
        kubectl port-forward -n $namespace svc/fintech-app 8000:8000 &
        local pf_pid=$!
        sleep 5
        service_endpoint="localhost:8000"
    fi
    
    # Test health endpoint
    log_info "Testing health endpoint..."
    if curl -f http://$service_endpoint/health > /dev/null 2>&1; then
        log_info "✅ Health check passed - Rollback verified"
    else
        log_error "❌ Health check failed - Rollback may not be working"
        [ -n "$pf_pid" ] && kill $pf_pid
        exit 1
    fi
    
    [ -n "$pf_pid" ] && kill $pf_pid
}

print_rollback_info() {
    local env=$1
    local namespace=$env
    
    log_info "Rollback Information:"
    echo ""
    echo "Environment:        $env"
    echo "Namespace:          $namespace"
    echo "Cluster:            $CLUSTER_NAME"
    echo "Region:             $REGION"
    echo ""
    
    log_info "Current Deployment:"
    kubectl get all -n $namespace
}

main() {
    local env=${1:-dev}
    local revision=${2}
    
    if [ "$env" != "dev" ] && [ "$env" != "staging" ] && [ "$env" != "prod" ]; then
        log_error "Invalid environment: $env"
        echo "Usage: $0 [dev|staging|prod] [revision_number]"
        exit 1
    fi
    
    check_prerequisites
    update_kubeconfig
    
    if [ -z "$revision" ]; then
        log_info "No revision specified, showing rollout history"
        get_rollout_history $env
        echo ""
        echo "Usage: $0 $env <revision_number>"
        exit 0
    fi
    
    log_info "Starting rollback for $env environment to revision $revision"
    
    confirm_rollback $env $revision
    perform_rollback $env $revision
    wait_for_rollout $env
    verify_rollback $env
    print_rollback_info $env
    
    log_info "✅ Rollback completed successfully"
}

main "$@"