# FinTech Fraud Detection - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [AWS Setup](#aws-setup)
3. [Terraform Deployment](#terraform-deployment)
4. [Kubernetes Setup](#kubernetes-setup)
5. [Helm Deployment](#helm-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools
- AWS CLI v2.x
- Terraform v1.0+
- kubectl v1.24+
- Helm v3.10+
- Docker (for local testing)
- Git

### AWS Account Requirements
- AWS Account with permissions to create VPC, RDS, ElastiCache, EKS
- IAM user with appropriate permissions
- Minimum $100 AWS credits (free tier)

### Installation

```bash
# macOS
brew install awscli terraform kubectl helm docker

# Linux
sudo apt-get install awscli terraform kubectl helm docker.io

# Verify installations
aws --version
terraform --version
kubectl version --client
helm version
```

---

## AWS Setup

### 1. Configure AWS Credentials

```bash
aws configure
```

Enter your AWS Access Key ID, Secret Access Key, region (eu-west-1), and output format (json).

### 2. Verify Configuration

```bash
aws sts get-caller-identity
```

You should see your AWS account information.

### 3. Create S3 Bucket for Terraform State (Optional but Recommended)

```bash
aws s3 mb s3://fintech-terraform-state-$(date +%s) \
  --region eu-west-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket fintech-terraform-state-xxxxx \
  --versioning-configuration Status=Enabled
```

---

## Terraform Deployment

### 1. Initialize Terraform

```bash
cd terraform/aws

terraform init

# If using remote state
# terraform init -backend-config="bucket=fintech-terraform-state-xxxxx"
```

### 2. Review the Plan

```bash
terraform plan -out=tfplan

# Review the output carefully
# Should show: VPC, RDS, ElastiCache, EKS, ECR, ALB
```

### 3. Apply Terraform

```bash
# This will take 15-20 minutes
terraform apply tfplan

# Save the outputs
terraform output > outputs.json
```

### 4. Verify Infrastructure

```bash
# Verify VPC was created
aws ec2 describe-vpcs --region eu-west-1

# Verify RDS was created
aws rds describe-db-instances --region eu-west-1

# Verify ElastiCache was created
aws elasticache describe-cache-clusters --region eu-west-1

# Verify EKS was created
aws eks describe-cluster --name fintech-fraud-detection-cluster --region eu-west-1
```

---

## Kubernetes Setup

### 1. Update kubeconfig

```bash
aws eks update-kubeconfig \
  --region eu-west-1 \
  --name fintech-fraud-detection-cluster

# Verify connection
kubectl get nodes
```

You should see 3 nodes in the output.

### 2. Install AWS Load Balancer Controller

```bash
# Add the EKS repository
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install the ALB controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=fintech-fraud-detection-cluster \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller
```

### 3. Install Metrics Server

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### 4. Verify Cluster Health

```bash
kubectl get nodes -o wide
kubectl get pods --all-namespaces
kubectl get storageclasses
```

---

## Helm Deployment

### 1. Create Namespaces

```bash
kubectl create namespace dev
kubectl create namespace staging
kubectl create namespace production
kubectl create namespace monitoring
```

### 2. Create Docker Registry Secret

```bash
# Get ECR login token
aws ecr get-authorization-token --region eu-west-1 \
  --query authorizationData[0].authorizationToken \
  --output text | base64 -d

# Create secret for dev
kubectl create secret docker-registry ecr-secret \
  --docker-server=ACCOUNT_ID.dkr.ecr.eu-west-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-authorization-token --region eu-west-1 --query 'authorizationData[0].authorizationToken' --output text | base64 -d | cut -d: -f2) \
  --docker-email=user@example.com \
  -n dev

# Repeat for staging and production
```

### 3. Deploy Dev Environment

```bash
cd kubernetes/helm/fintech-app

helm install fintech-app . \
  --namespace dev \
  --values values.yaml \
  --wait \
  --timeout 5m
```

### 4. Deploy Staging Environment

```bash
helm install fintech-app . \
  --namespace staging \
  --values values.yaml \
  --values values-staging.yaml \
  --wait \
  --timeout 5m
```

### 5. Verify Deployments

```bash
# Check all namespaces
kubectl get all -n dev
kubectl get all -n staging

# Check services
kubectl get svc -n dev
kubectl get svc -n staging

# Check ingress
kubectl get ingress -n dev
kubectl get ingress -n staging
```

---

## CI/CD Pipeline

### 1. Configure GitHub Secrets

In GitHub Repository → Settings → Secrets and variables → Actions:
AWS_ROLE_TO_ASSUME = arn:aws:iam::ACCOUNT_ID:role/github-actions-role
SLACK_WEBHOOK = https://hooks.slack.com/services/T.../B.../K...

### 2. Create AWS IAM Role for GitHub Actions

```bash
# This is optional for development, required for production
# See: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
```

### 3. Push to GitHub

```bash
git add .
git commit -m "feat: Phase 6 deployment infrastructure"
git push origin main
```

The CI/CD pipeline will automatically:
1. Run tests
2. Build Docker images
3. Push to ECR
4. Deploy to dev (automatic)

### 4. Deploy to Production

```bash
# Manually trigger in GitHub Actions
# Go to Actions → Deploy to Production → Run workflow
# Enter version tag (e.g., v1.0.0)
```

---

## Monitoring

### 1. Install Prometheus

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f monitoring/prometheus/prometheus-values.yaml \
  --wait
```

### 2. Access Prometheus

```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Access at http://localhost:9090
```

### 3. Access Grafana

```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:3000

# Access at http://localhost:3000
# Default credentials: admin/prom-operator
```

### 4. Import Dashboards

- Go to Grafana → Dashboards → Import
- Import from `monitoring/grafana/grafana-dashboards.yaml`

---

## Troubleshooting

### EKS Cluster Issues

```bash
# Check cluster status
aws eks describe-cluster --name fintech-fraud-detection-cluster --region eu-west-1 | grep status

# Check node status
kubectl get nodes -o wide
kubectl describe node <node-name>

# Check pod logs
kubectl logs -f deployment/fintech-app-api -n dev
```

### Database Connection Issues

```bash
# Get RDS endpoint
aws rds describe-db-instances --region eu-west-1 \
  --query 'DBInstances[0].Endpoint.Address'

# Test connection
psql -h <rds-endpoint> -U postgres -d fintech_db

# Check security group
aws ec2 describe-security-groups --region eu-west-1 \
  --filters "Name=group-name,Values=fintech-fraud-detection-rds-sg"
```

### Redis Connection Issues

```bash
# Get Redis endpoint
aws elasticache describe-cache-clusters --region eu-west-1 \
  --show-cache-node-info

# Test connection
redis-cli -h <redis-endpoint> -p 6379 ping
```

### Load Balancer Issues

```bash
# Check ALB status
aws elbv2 describe-load-balancers --region eu-west-1

# Check target groups
aws elbv2 describe-target-groups --region eu-west-1

# Check targets
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --region eu-west-1
```

### Pod Crashing

```bash
# Check pod status
kubectl describe pod <pod-name> -n dev

# Check logs
kubectl logs <pod-name> -n dev
kubectl logs <pod-name> -n dev --previous

# Check events
kubectl get events -n dev --sort-by='.lastTimestamp'
```

---

## Cleanup

### Delete Everything

```bash
# Delete Kubernetes resources
kubectl delete namespace dev staging production monitoring

# Destroy Terraform
cd terraform/aws
terraform destroy

# Delete S3 bucket (if created)
aws s3 rm s3://fintech-terraform-state-xxxxx --recursive
aws s3 rb s3://fintech-terraform-state-xxxxx
```

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review AWS CloudWatch logs
3. Check Kubernetes events: `kubectl get events -n <namespace>`
4. Review application logs: `kubectl logs -f deployment/<name> -n <namespace>`

---

## Next Steps

1. ✅ Deploy infrastructure (Terraform)
2. ✅ Set up Kubernetes (EKS + Helm)
3. ✅ Configure CI/CD (GitHub Actions)
4. ✅ Enable Monitoring (Prometheus + Grafana)
5. 🔄 Load test the system
6. 🔄 Set up alerting
7. 🔄 Plan disaster recovery