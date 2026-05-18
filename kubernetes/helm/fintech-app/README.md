# Fintech Fraud Detection - Helm Chart

## Installation

### Dev Environment
```bash
helm install fintech-app . \
  --namespace dev \
  --create-namespace \
  -f values.yaml
```

### Staging Environment
```bash
helm install fintech-app . \
  --namespace staging \
  --create-namespace \
  -f values.yaml \
  -f values-staging.yaml
```

### Production Environment
```bash
helm install fintech-app . \
  --namespace production \
  --create-namespace \
  -f values.yaml \
  -f values-prod.yaml \
  --set secrets.MISTRAL_API_KEY=$MISTRAL_KEY \
  --set secrets.DB_PASSWORD=$DB_PASSWORD \
  --set secrets.REDIS_AUTH_TOKEN=$REDIS_TOKEN
```

## Upgrade

```bash
helm upgrade fintech-app . -f values.yaml -f values-prod.yaml
```

## Rollback

```bash
helm rollback fintech-app 1  # Rollback to previous release
```

## Configuration

### Environment Variables

| Variable | Dev | Staging | Prod |
|----------|-----|---------|------|
| ENVIRONMENT | dev | staging | prod |
| LOG_LEVEL | INFO | DEBUG | WARNING |
| API Replicas | 3 | 2 | 5 |
| Workers Replicas | 2 | 2 | 4 |
| Auto-scaling Max | 10 | 8 | 20 |

### Secrets

Use AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name fintech/mistral-api-key \
  --secret-string $MISTRAL_KEY
```

## Monitoring

- Prometheus: `kubectl port-forward svc/prometheus 9090:9090`
- Grafana: `kubectl port-forward svc/grafana 3000:3000`

## Troubleshooting

```bash
# Check deployment status
kubectl get deployments -n production
kubectl describe deployment fintech-app-api -n production

# Check logs
kubectl logs -f deployment/fintech-app-api -n production

# Check events
kubectl get events -n production --sort-by='.lastTimestamp'
```
