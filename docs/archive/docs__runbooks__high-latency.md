# ⏱️ High Latency Runbook

## Overview

This runbook covers investigating and resolving high latency issues in DriftGuard services.

## Severity: P2 (High)

## Alert Thresholds

| Percentile | Warning | Critical |
|------------|---------|----------|
| P95 | > 500ms | > 2s |
| P99 | > 1s | > 5s |

## Step 1: Identify Latency Source (5 min)

### Check Overall Latency

```bash
# P95 latency by service
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~"driftguard.*"}[5m])) by (le, service))' \
  | jq '.data.result[] | {service: .metric.service, p95: .value[1]}'

# Slowest endpoints
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=topk(10, histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path)))' \
  | jq '.data.result'
```

### Check Distributed Tracing

```bash
# Open Jaeger UI
kubectl port-forward svc/jaeger-query 16686:16686 -n monitoring

# Then open http://localhost:16686
# Filter by service: driftguard-controller
# Sort by duration
```

## Step 2: Check Dependencies

### Database Latency

```bash
# Check slow queries
kubectl exec -it postgres-0 -n driftguard-prod -- psql -U postgres -c "
SELECT 
  query,
  calls,
  mean_time,
  total_time
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;"

# Check connection pool
kubectl exec -it postgres-0 -n driftguard-prod -- psql -U postgres -c "
SELECT count(*) as connections, 
       state 
FROM pg_stat_activity 
WHERE datname='driftguard' 
GROUP BY state;"
```

### Redis Latency

```bash
# Check Redis latency
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli --latency

# Check slow log
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli slowlog get 10

# Check memory
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli info memory
```

### Qdrant Latency

```bash
# Check Qdrant metrics
curl -s http://qdrant:6333/metrics | grep -E "qdrant_.*_seconds"

# Check collection stats
curl -s http://qdrant:6333/collections/documents | jq '.result.points_count, .result.segments_count'
```

### External API Latency (OpenRouter)

```bash
# Check OpenRouter response times
kubectl logs -l app=driftguard-query -n driftguard-prod --tail=500 \
  | grep -i "openrouter" | grep -oP 'duration["\s:]+\K[0-9.]+' | tail -20
```

## Step 3: Check Resources

### CPU Throttling

```bash
# Check CPU throttling
kubectl top pods -n driftguard-prod

# Check if hitting CPU limits
kubectl get pods -n driftguard-prod -o jsonpath='{range .items[*]}{.metadata.name}{" CPU Limit: "}{.spec.containers[0].resources.limits.cpu}{"\n"}{end}'
```

### Memory Pressure

```bash
# Check memory usage
kubectl top pods -n driftguard-prod

# Check for GC pressure in logs
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=200 | grep -i "gc\|memory"
```

### Network Issues

```bash
# Check network latency between pods
kubectl run debug-pod --rm -i --restart=Never \
  --image=curlimages/curl:latest \
  -n driftguard-prod \
  -- curl -o /dev/null -s -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  http://driftguard-query:8002/health
```

## Step 4: Remediation

### If Database is Slow

```bash
# Add missing indexes (work with DBA)
# Increase connection pool
# Consider read replicas

# Temporarily increase resources
kubectl set resources deployment/postgres -n driftguard-prod \
  --limits=cpu=4000m,memory=8Gi \
  --requests=cpu=2000m,memory=4Gi
```

### If Redis is Slow

```bash
# Check and clear if memory is high
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli memory doctor

# Consider increasing memory limit
kubectl set resources statefulset/redis -n driftguard-prod \
  --limits=memory=4Gi
```

### If External API is Slow

```bash
# Increase timeout (temporary)
# Enable request caching
# Consider fallback model
```

### If CPU Throttled

```bash
# Increase CPU limits
kubectl set resources deployment/driftguard-controller -n driftguard-prod \
  --limits=cpu=2000m

# Or scale out
kubectl scale deployment/driftguard-controller -n driftguard-prod --replicas=5
```

### If High Traffic

```bash
# Scale up
kubectl scale deployment/driftguard-controller -n driftguard-prod --replicas=10

# Enable rate limiting (if not already)
# Check HPA status
kubectl get hpa -n driftguard-prod
```

## Step 5: Verify Resolution

```bash
# Monitor latency improvement
watch -n 10 'curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode "query=histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=\"driftguard-controller\"}[1m])) by (le))" \
  | jq ".data.result[0].value[1]"'
```

## Step 6: Long-term Fixes

After immediate resolution, consider:

1. **Query Optimization**
   - Review slow queries
   - Add appropriate indexes
   - Optimize N+1 queries

2. **Caching**
   - Add Redis caching for frequent queries
   - Implement response caching
   - Use CDN for static assets

3. **Architecture**
   - Consider read replicas
   - Implement async processing
   - Add request queuing

4. **Monitoring**
   - Add more granular latency metrics
   - Set up alerting on specific endpoints
   - Implement SLO tracking

## Escalation

If latency doesn't improve after 30 minutes:
1. Consider traffic shedding (rate limiting)
2. Enable maintenance mode for non-critical features
3. Escalate to engineering lead
