# Troubleshooting Guide

> Common issues, diagnostic procedures, and solutions for the Cognimend RAG System.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Service Issues](#service-issues)
- [Database Issues](#database-issues)
- [Vector Store Issues](#vector-store-issues)
- [LLM/API Issues](#llmapi-issues)
- [Kubernetes Issues](#kubernetes-issues)
- [Performance Issues](#performance-issues)
- [Authentication Issues](#authentication-issues)
- [Network Issues](#network-issues)
- [Monitoring Issues](#monitoring-issues)

---

## Quick Diagnostics

### System Health Check Script

```bash
#!/bin/bash
# Run comprehensive health check

echo "🔍 Cognimend System Health Check"
echo "================================"

# Check all pods
echo -e "\n📦 Pod Status:"
kubectl get pods -n cognimend -o wide

# Check services
echo -e "\n🌐 Service Status:"
kubectl get svc -n cognimend

# Check recent events
echo -e "\n📋 Recent Events:"
kubectl get events -n cognimend --sort-by='.lastTimestamp' | tail -20

# Check resource usage
echo -e "\n📊 Resource Usage:"
kubectl top pods -n cognimend

# Check HPA status
echo -e "\n⚖️ HPA Status:"
kubectl get hpa -n cognimend
```

### Service Health Endpoints

| Service | Health Endpoint | Expected Response |
|---------|----------------|-------------------|
| Upload | `GET /health` | `{"status": "healthy"}` |
| Query | `GET /health` | `{"status": "healthy"}` |
| Telemetry | `GET /health` | `{"status": "healthy"}` |
| Drift Detector | `GET /health` | `{"status": "healthy"}` |
| Controller | `GET /health` | `{"status": "healthy"}` |
| Evaluation | `GET /health` | `{"status": "healthy"}` |

---

## Service Issues

### Issue: Service Not Starting

**Symptoms:**
- Pod in `CrashLoopBackOff` or `Error` state
- Container exits immediately

**Diagnosis:**
```bash
# Check pod status
kubectl describe pod <pod-name> -n cognimend

# Check container logs
kubectl logs <pod-name> -n cognimend --previous

# Check events
kubectl get events -n cognimend --field-selector involvedObject.name=<pod-name>
```

**Common Causes & Solutions:**

1. **Missing environment variables**
   ```bash
   # Check if ConfigMap is mounted
   kubectl get configmap rag-config -n cognimend -o yaml
   
   # Verify env vars in pod
   kubectl exec <pod-name> -n cognimend -- env | grep -E "DATABASE|REDIS|QDRANT"
   ```

2. **Database connection failure**
   ```bash
   # Test database connectivity from pod
   kubectl exec <pod-name> -n cognimend -- nc -zv postgres-service 5432
   ```

3. **Insufficient resources**
   ```yaml
   # Increase resource limits in deployment
   resources:
     requests:
       memory: "512Mi"
       cpu: "250m"
     limits:
       memory: "1Gi"
       cpu: "500m"
   ```

### Issue: Service Returning 5xx Errors

**Symptoms:**
- HTTP 500, 502, 503, or 504 errors
- Intermittent failures

**Diagnosis:**
```bash
# Check service logs
kubectl logs -f -l app=<service-name> -n cognimend --tail=100

# Check error metrics
curl -s http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m])
```

**Common Causes & Solutions:**

1. **500 Internal Server Error**
   ```python
   # Check for unhandled exceptions in logs
   # Add proper error handling
   try:
       result = await process_request(data)
   except ValidationError as e:
       raise HTTPException(status_code=400, detail=str(e))
   except Exception as e:
       logger.exception("Unexpected error")
       raise HTTPException(status_code=500, detail="Internal server error")
   ```

2. **502 Bad Gateway**
   ```bash
   # Usually indicates backend service is down
   # Check if pods are ready
   kubectl get pods -n cognimend -l app=<service-name>
   
   # Check readiness probe
   kubectl describe pod <pod-name> -n cognimend | grep -A5 "Readiness"
   ```

3. **503 Service Unavailable**
   ```bash
   # Check HPA scaling
   kubectl get hpa -n cognimend
   
   # Check if pods are overloaded
   kubectl top pods -n cognimend
   ```

4. **504 Gateway Timeout**
   ```yaml
   # Increase timeout in ingress
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     annotations:
       nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
       nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
   ```

---

## Database Issues

### Issue: PostgreSQL Connection Errors

**Symptoms:**
- `connection refused` errors
- `too many connections` errors
- Slow database queries

**Diagnosis:**
```bash
# Check PostgreSQL pod
kubectl logs postgres-0 -n cognimend

# Check connection count
kubectl exec postgres-0 -n cognimend -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check for long-running queries
kubectl exec postgres-0 -n cognimend -- psql -U postgres -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

**Solutions:**

1. **Connection pool exhaustion**
   ```python
   # Increase pool size in connection settings
   DATABASE_URL = "postgresql://user:pass@host:5432/db?pool_size=20&max_overflow=10"
   ```

2. **Kill long-running queries**
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE duration > interval '10 minutes' 
   AND state != 'idle';
   ```

3. **Database restart**
   ```bash
   kubectl rollout restart statefulset/postgres -n cognimend
   ```

### Issue: Database Disk Full

**Symptoms:**
- `FATAL: could not write to file` errors
- Database becomes read-only

**Diagnosis:**
```bash
# Check PV usage
kubectl exec postgres-0 -n cognimend -- df -h /var/lib/postgresql/data

# Check table sizes
kubectl exec postgres-0 -n cognimend -- psql -U postgres -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"
```

**Solutions:**

1. **Clean up old data**
   ```sql
   -- Delete old logs
   DELETE FROM query_logs WHERE timestamp < NOW() - INTERVAL '90 days';
   
   -- Vacuum to reclaim space
   VACUUM FULL;
   ```

2. **Expand PVC**
   ```bash
   kubectl patch pvc postgres-pvc -n cognimend -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'
   ```

---

## Vector Store Issues

### Issue: Qdrant Not Responding

**Symptoms:**
- Connection timeouts to Qdrant
- Vector search failures

**Diagnosis:**
```bash
# Check Qdrant pod
kubectl logs qdrant-0 -n cognimend

# Check Qdrant health
kubectl exec qdrant-0 -n cognimend -- curl -s http://localhost:6333/healthz

# Check collection status
kubectl exec qdrant-0 -n cognimend -- curl -s http://localhost:6333/collections
```

**Solutions:**

1. **Restart Qdrant**
   ```bash
   kubectl rollout restart statefulset/qdrant -n cognimend
   ```

2. **Recreate collection if corrupted**
   ```python
   from qdrant_client import QdrantClient
   
   client = QdrantClient(host="qdrant-service", port=6333)
   
   # Backup existing data first
   # Then recreate collection
   client.recreate_collection(
       collection_name="documents",
       vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
   )
   ```

### Issue: Slow Vector Search

**Symptoms:**
- Search latency > 500ms
- Timeouts during search

**Diagnosis:**
```bash
# Check collection info
curl -s http://qdrant:6333/collections/documents | jq

# Check index status
curl -s http://qdrant:6333/collections/documents/points/count
```

**Solutions:**

1. **Optimize HNSW parameters**
   ```python
   client.update_collection(
       collection_name="documents",
       optimizer_config=OptimizersConfigDiff(
           indexing_threshold=10000
       ),
       hnsw_config=HnswConfigDiff(
           ef_construct=128,
           m=16
       )
   )
   ```

2. **Add payload indexes for filtering**
   ```python
   client.create_payload_index(
       collection_name="documents",
       field_name="tenant_id",
       field_schema=PayloadSchemaType.KEYWORD
   )
   ```

---

## LLM/API Issues

### Issue: OpenRouter API Errors

**Symptoms:**
- 401 Unauthorized errors
- 429 Rate limit errors
- Timeout errors

**Diagnosis:**
```bash
# Check API key is set
kubectl get secret rag-secrets -n cognimend -o jsonpath='{.data.openrouter-api-key}' | base64 -d

# Test API connectivity
curl -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4-turbo", "messages": [{"role": "user", "content": "test"}]}'
```

**Solutions:**

1. **401 Unauthorized**
   ```bash
   # Update API key in secret
   kubectl create secret generic rag-secrets \
     --from-literal=openrouter-api-key=<new-key> \
     -n cognimend \
     --dry-run=client -o yaml | kubectl apply -f -
   
   # Restart services
   kubectl rollout restart deployment -n cognimend
   ```

2. **429 Rate Limit**
   ```python
   # Implement exponential backoff
   import asyncio
   from tenacity import retry, stop_after_attempt, wait_exponential
   
   @retry(
       stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=1, min=4, max=60)
   )
   async def call_llm_with_retry(prompt: str) -> str:
       return await llm_client.generate(prompt)
   ```

3. **Timeout errors**
   ```python
   # Increase timeout settings
   import httpx
   
   client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
   ```

### Issue: High LLM Costs

**Symptoms:**
- API costs exceeding budget
- Unexpected token usage

**Diagnosis:**
```bash
# Check token usage metrics
curl -s http://prometheus:9090/api/v1/query?query=sum(increase(llm_tokens_total[24h]))

# Check by endpoint
curl -s http://prometheus:9090/api/v1/query?query=sum(increase(llm_tokens_total[24h]))by(endpoint)
```

**Solutions:**

1. **Enable caching**
   ```python
   # Cache LLM responses
   @cached(ttl=3600, key_builder=lambda q: hashlib.md5(q.encode()).hexdigest())
   async def generate_response(query: str) -> str:
       return await llm_client.generate(query)
   ```

2. **Optimize prompts**
   ```python
   # Use shorter system prompts
   # Limit context length
   max_context_tokens = 2000
   truncated_context = truncate_to_tokens(context, max_context_tokens)
   ```

3. **Use cheaper models for simple queries**
   ```python
   def select_model(query_complexity: str) -> str:
       if query_complexity == "simple":
           return "openai/gpt-3.5-turbo"
       return "openai/gpt-4-turbo"
   ```

---

## Kubernetes Issues

### Issue: Pods Pending

**Symptoms:**
- Pods stuck in `Pending` state

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n cognimend | grep -A10 "Events:"
```

**Common Causes & Solutions:**

1. **Insufficient resources**
   ```bash
   # Check node resources
   kubectl describe nodes | grep -A5 "Allocated resources"
   
   # Scale down other workloads or add nodes
   ```

2. **PVC not bound**
   ```bash
   # Check PVC status
   kubectl get pvc -n cognimend
   
   # Check if StorageClass exists
   kubectl get sc
   ```

3. **Node selector/affinity not matching**
   ```bash
   # Check node labels
   kubectl get nodes --show-labels
   ```

### Issue: OOMKilled

**Symptoms:**
- Pod restarts with reason `OOMKilled`

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n cognimend | grep -A5 "Last State"
```

**Solutions:**

1. **Increase memory limits**
   ```yaml
   resources:
     limits:
       memory: "2Gi"  # Increase from 1Gi
   ```

2. **Fix memory leaks in application**
   ```python
   # Profile memory usage
   import tracemalloc
   tracemalloc.start()
   
   # ... run operations ...
   
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')
   for stat in top_stats[:10]:
       print(stat)
   ```

---

## Performance Issues

### Issue: High Latency

**Symptoms:**
- P95 latency > 500ms
- Slow response times

**Diagnosis:**
```bash
# Check latency metrics
curl -s http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))

# Check slow endpoints
curl -s http://prometheus:9090/api/v1/query?query=topk(5,avg(rate(http_request_duration_seconds_sum[5m]))by(endpoint))
```

**Solutions:**

1. **Enable caching**
2. **Optimize database queries**
3. **Scale horizontally**
4. **Profile and optimize code**

See [Performance Guide](PERFORMANCE.md) for detailed optimization strategies.

### Issue: High Error Rate

**Symptoms:**
- Error rate > 1%
- Increasing failed requests

**Diagnosis:**
```bash
# Check error rate by service
curl -s http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m])/rate(http_requests_total[5m])

# Check error logs
kubectl logs -l app=query -n cognimend | grep -i error | tail -50
```

**Solutions:**

1. **Add circuit breakers**
   ```python
   from circuitbreaker import circuit
   
   @circuit(failure_threshold=5, recovery_timeout=30)
   async def external_api_call():
       return await api.call()
   ```

2. **Improve error handling**
3. **Add retries for transient failures**

---

## Authentication Issues

### Issue: JWT Token Errors

**Symptoms:**
- 401 Unauthorized with valid credentials
- Token validation failures

**Diagnosis:**
```bash
# Check JWT secret
kubectl get secret rag-secrets -n cognimend -o jsonpath='{.data.jwt-secret}' | base64 -d

# Decode and verify token
echo $TOKEN | cut -d. -f2 | base64 -d | jq
```

**Solutions:**

1. **Token expired**
   - Request new token from auth endpoint
   - Implement token refresh mechanism

2. **Wrong secret**
   ```bash
   # Update JWT secret across all services
   kubectl create secret generic rag-secrets \
     --from-literal=jwt-secret=<new-secret> \
     -n cognimend \
     --dry-run=client -o yaml | kubectl apply -f -
   
   kubectl rollout restart deployment -n cognimend
   ```

---

## Network Issues

### Issue: DNS Resolution Failures

**Symptoms:**
- `Name or service not known` errors
- Intermittent connectivity

**Diagnosis:**
```bash
# Test DNS from pod
kubectl exec <pod-name> -n cognimend -- nslookup postgres-service

# Check CoreDNS
kubectl logs -n kube-system -l k8s-app=kube-dns
```

**Solutions:**

1. **Restart CoreDNS**
   ```bash
   kubectl rollout restart deployment/coredns -n kube-system
   ```

2. **Use IP addresses temporarily**
   ```bash
   # Get service IP
   kubectl get svc postgres-service -n cognimend -o jsonpath='{.spec.clusterIP}'
   ```

### Issue: Network Policy Blocking Traffic

**Symptoms:**
- Connection refused between services
- Timeout errors

**Diagnosis:**
```bash
# Check network policies
kubectl get networkpolicy -n cognimend -o yaml

# Test connectivity
kubectl exec <source-pod> -n cognimend -- nc -zv <target-service> <port>
```

**Solutions:**

1. **Update network policy**
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: allow-query-to-qdrant
   spec:
     podSelector:
       matchLabels:
         app: query
     egress:
       - to:
           - podSelector:
               matchLabels:
                 app: qdrant
         ports:
           - port: 6333
   ```

---

## Monitoring Issues

### Issue: Prometheus Not Scraping

**Symptoms:**
- Missing metrics in Grafana
- `up` metric is 0

**Diagnosis:**
```bash
# Check Prometheus targets
curl -s http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Check ServiceMonitor
kubectl get servicemonitor -n cognimend -o yaml
```

**Solutions:**

1. **Fix ServiceMonitor selector**
   ```yaml
   apiVersion: monitoring.coreos.com/v1
   kind: ServiceMonitor
   spec:
     selector:
       matchLabels:
         app: query  # Must match service labels
     endpoints:
       - port: http  # Must match service port name
         path: /metrics
   ```

2. **Check metrics endpoint**
   ```bash
   kubectl exec <pod-name> -n cognimend -- curl -s http://localhost:8000/metrics
   ```

---

## Quick Reference

### Useful Commands

```bash
# Restart all deployments
kubectl rollout restart deployment -n cognimend

# Get all logs
kubectl logs -l app.kubernetes.io/part-of=cognimend -n cognimend --all-containers

# Port forward for debugging
kubectl port-forward svc/query-service 8000:8000 -n cognimend

# Exec into pod
kubectl exec -it <pod-name> -n cognimend -- /bin/sh

# Force delete stuck pod
kubectl delete pod <pod-name> -n cognimend --force --grace-period=0
```

### Emergency Contacts

| Issue Type | Escalation Path |
|------------|-----------------|
| P0 - System Down | On-call SRE → Slack #incidents |
| P1 - Degraded | Engineering Lead → Slack #alerts |
| P2 - Non-critical | Create GitHub issue |

---

*Last updated: 2024*
