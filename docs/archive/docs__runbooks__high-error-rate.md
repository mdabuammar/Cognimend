# 🔴 High Error Rate Runbook

## Overview

This runbook covers investigating and resolving high error rates in DriftGuard services.

## Severity: P2 (High) → P1 if > 10%

## Alert Thresholds

| Level | Error Rate | Response Time |
|-------|-----------|---------------|
| Warning | > 5% | 30 min |
| Critical | > 10% | 15 min |

## Step 1: Assess Impact (5 min)

### Check Current Error Rate

```bash
# Overall error rate
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_requests_total{job=~"driftguard.*",status=~"5.."}[5m])) / sum(rate(http_requests_total{job=~"driftguard.*"}[5m]))' \
  | jq '.data.result[0].value[1]'

# Error rate by service
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_requests_total{job=~"driftguard.*",status=~"5.."}[5m])) by (service) / sum(rate(http_requests_total{job=~"driftguard.*"}[5m])) by (service)' \
  | jq '.data.result'

# Error rate by endpoint
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=topk(5, sum(rate(http_requests_total{status=~"5.."}[5m])) by (path))' \
  | jq '.data.result'
```

### Check Error Types

```bash
# Error status breakdown
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=200 \
  | grep -E '"status":\s*(4|5)[0-9]{2}' \
  | jq -r '.status' \
  | sort | uniq -c | sort -rn
```

## Step 2: Identify Root Cause

### Check Logs for Patterns

```bash
# Controller errors
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=500 \
  | grep -i "error\|exception\|failed" | tail -50

# Query service errors
kubectl logs -l app=driftguard-query -n driftguard-prod --tail=500 \
  | grep -i "error\|exception\|failed" | tail -50

# Upload service errors
kubectl logs -l app=driftguard-upload -n driftguard-prod --tail=500 \
  | grep -i "error\|exception\|failed" | tail -50
```

### Common Error Patterns

| Pattern | Likely Cause | Solution |
|---------|-------------|----------|
| `ConnectionError` | Database/Redis down | Check infrastructure |
| `TimeoutError` | Slow dependency | Check latency |
| `RateLimitError` | Rate limit exceeded | Check rate limiter |
| `AuthenticationError` | Auth service issue | Check auth config |
| `ValidationError` | Bad request data | Check request patterns |
| `OutOfMemoryError` | Memory exhaustion | Scale or restart pods |

## Step 3: Check Dependencies

### Database

```bash
# Check PostgreSQL
kubectl get pods -n driftguard-prod -l app=postgres
kubectl exec -it postgres-0 -n driftguard-prod -- pg_isready

# Check connection count
kubectl exec -it postgres-0 -n driftguard-prod -- psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='driftguard';"

# Check for long-running queries
kubectl exec -it postgres-0 -n driftguard-prod -- psql -U postgres -c \
  "SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
   FROM pg_stat_activity 
   WHERE state != 'idle' AND now() - pg_stat_activity.query_start > interval '30 seconds';"
```

### Redis

```bash
# Check Redis
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli ping

# Check memory usage
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli info memory | grep used_memory_human
```

### Qdrant

```bash
# Check Qdrant health
curl -s http://qdrant:6333/health

# Check collection info
curl -s http://qdrant:6333/collections/documents | jq .
```

### External APIs (OpenRouter)

```bash
# Check OpenRouter status
curl -s https://openrouter.ai/api/v1/models -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq .error

# Check for rate limiting
kubectl logs -l app=driftguard-query -n driftguard-prod --tail=200 \
  | grep -i "rate limit\|429"
```

## Step 4: Remediation

### If Database Issue

```bash
# Restart database pods
kubectl rollout restart statefulset/postgres -n driftguard-prod

# If connection pool exhausted, restart services
kubectl rollout restart deployment/driftguard-controller -n driftguard-prod
kubectl rollout restart deployment/driftguard-query -n driftguard-prod
```

### If Memory Issue

```bash
# Check memory usage
kubectl top pods -n driftguard-prod

# Restart high-memory pods
kubectl delete pod <pod-name> -n driftguard-prod
```

### If External API Issue

```bash
# Check circuit breaker status
curl -s http://driftguard-controller:8005/health | jq '.components.openrouter'

# If circuit breaker open, wait for reset or manually reset
# (depends on implementation)
```

### If Recent Deployment

Consider rollback:
```bash
# Check recent deployments
kubectl rollout history deployment/driftguard-controller -n driftguard-prod

# Rollback if needed
# See rollback.md runbook
```

## Step 5: Verify Resolution

```bash
# Monitor error rate
watch -n 5 'curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode "query=sum(rate(http_requests_total{status=~\"5..\"}[1m])) / sum(rate(http_requests_total[1m]))" \
  | jq ".data.result[0].value[1]"'

# Should see error rate decreasing
```

## Step 6: Post-Incident

1. **Document** the incident in JIRA
2. **Update** status page when resolved
3. **Notify** team in #driftguard-incidents
4. **Schedule** post-mortem if P1

## Escalation

If error rate doesn't decrease after 30 minutes:
1. Page engineering lead
2. Consider traffic shifting or maintenance mode
3. Declare major incident if affecting users significantly
