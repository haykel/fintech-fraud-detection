#!/bin/bash

# FinTech Fraud Detection - Deployment Script
# Usage: ./deploy.sh [dev|staging|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="eu-west-1"
CLUSTER_NAME="fintech-fraud-detection-cluster"
CHART_PATH="kubernetes/helm/fintech-app"
IMAGE_TAG="${CI_COMMIT_SHA:=$(git rev-parse --short HEAD)}"

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
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if helm is installed
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    # Check if aws cli is installed
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
    
    log_info "Kubeconfig updated successfully"
}

validate_helm_chart() {
    log_info "Validating Helm chart..."
    
    helm lint $CHART_PATH
    
    if [ $? -eq 0 ]; then
        log_info "Helm chart validation passed"
    else
        log_error "Helm chart validation failed"
        exit 1
    fi
}

get_values_file() {
    local env=$1
    
    case $env in
        dev)
            echo "$CHART_PATH/values.yaml"
            ;;
        staging)
            echo "$CHART_PATH/values.yaml -f $CHART_PATH/values-staging.yaml"
            ;;
        prod)
            echo "$CHART_PATH/values.yaml -f $CHART_PATH/values-prod.yaml"
            ;;
        *)
            log_error "Unknown environment: $env"
            exit 1
            ;;
    esac
}

deploy_environment() {
    local env=$1
    local namespace=$env
    local values_files=$(get_values_file $env)
    
    log_info "Deploying to $env environment..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace $namespace --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy with Helm
    helm upgrade --install fintech-app $CHART_PATH \
        --namespace $namespace \
        --values $values_files \
        --set image.tag=$IMAGE_TAG \
        --wait \
        --timeout 5m
    
    if [ $? -eq 0 ]; then
        log_info "Deployment to $env completed successfully"
    else
        log_error "Deployment to $env failed"
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

run_smoke_tests() {
    local env=$1
    local namespace=$env
    
    log_info "Running smoke tests..."
    
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
    log_info "Testing /health endpoint..."
    if curl -f http://$service_endpoint/health > /dev/null 2>&1; then
        log_info "✅ Health check passed"
    else
        log_error "❌ Health check failed"
        [ -n "$pf_pid" ] && kill $pf_pid
        exit 1
    fi
    
    # Test API endpoint
    log_info "Testing /api/transactions endpoint..."
    if curl -f http://$service_endpoint/api/transactions -X OPTIONS > /dev/null 2>&1; then
        log_info "✅ API endpoint check passed"
    else
        log_error "❌ API endpoint check failed"
        [ -n "$pf_pid" ] && kill $pf_pid
        exit 1
    fi
    
    [ -n "$pf_pid" ] && kill $pf_pid
    
    log_info "All smoke tests passed"
}

print_deployment_info() {
    local env=$1
    local namespace=$env
    
    log_info "Deployment Information:"
    echo ""
    echo "Environment:        $env"
    echo "Namespace:          $namespace"
    echo "Cluster:            $CLUSTER_NAME"
    echo "Region:             $REGION"
    echo "Image Tag:          $IMAGE_TAG"
    echo ""
    
    log_info "Deployment Details:"
    kubectl get all -n $namespace
    
    echo ""
    log_info "Service Information:"
    kubectl get svc fintech-app -n $namespace
}

rollback_deployment() {
    local env=$1
    local namespace=$env
    
    log_warn "Rolling back deployment..."
    
    helm rollback fintech-app -n $namespace
    kubectl rollout status deployment/fintech-app-api -n $namespace --timeout=5m
    
    log_info "Rollback completed"
}

main() {
    local env=${1:-dev}
    
    if [ "$env" != "dev" ] && [ "$env" != "staging" ] && [ "$env" != "prod" ]; then
        log_error "Invalid environment: $env"
        echo "Usage: $0 [dev|staging|prod]"
        exit 1
    fi
    
    log_info "Starting deployment to $env environment"
    log_info "Image tag: $IMAGE_TAG"
    
    check_prerequisites
    update_kubeconfig
    validate_helm_chart
    deploy_environment $env
    wait_for_rollout $env
    run_smoke_tests $env
    print_deployment_info $env
    
    log_info "✅ Deployment completed successfully"
}

# Trap errors and rollback if needed
trap 'log_error "Deployment failed"; exit 1' ERR

# Run main function
main "$@"