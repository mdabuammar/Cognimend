# 🚀 QUICK MONITORING REFERENCE

## **🔗 Key Endpoints**

```bash
# Health Check
curl http://localhost:8002/health
curl http://localhost:8002/health/detailed

# Metrics
curl http://localhost:8002/metrics                 # Legacy
curl http://localhost:8002/metrics/summary         # New (recommended)
curl http://localhost:8002/metrics/prometheus      # Prometheus format

# Performance
curl http://localhost:8002/profile/query_documents

# Alerts
curl http://localhost:8002/alerts/history?limit=10
```

---

## **📊 What to Monitor**

### **Critical (🔴 Alert Immediately)**
- ❌ Service health status = unhealthy
- ❌ Circuit breaker = OPEN
- ❌ Success rate < 98%
- ❌ P99 latency > 5000ms

### **Warning (🟡 Investigate)**
- ⚠️ P95 latency > 2000ms
- ⚠️ Cache hit rate < 30%
- ⚠️ Hourly cost > $2.00
- ⚠️ SLO violation alert

### **Informational (🟢 Track)**
- ℹ️ Average latency
- ℹ️ Cache hit rate
- ℹ️ Cost per query
- ℹ️ Model distribution

---

## **🎯 SLO Targets**

```
P50:  800ms      ✅ Target
P95:  2000ms     ✅ Target
P99:  3000ms     ✅ Target
Success: 99.5%   ✅ Target
Cache: 40%+      ✅ Target
```

---

## **🔄 Common Queries**

**Check if healthy:**
```bash
curl http://localhost:8002/health/detailed | jq '.status'
```

**View SLO compliance:**
```bash
curl http://localhost:8002/metrics/summary | jq '.slo_compliance'
```

**Check costs:**
```bash
curl http://localhost:8002/metrics/summary | jq '.costs'
```

**See recent errors:**
```bash
curl http://localhost:8002/metrics/summary | jq '.errors'
```

**List recent alerts:**
```bash
curl http://localhost:8002/alerts/history | jq '.alerts[] | {title, severity}'
```

---

## **⚡ Performance Tips**

| Slow? | Check |
|-------|-------|
| P99 > 3s | Qdrant/OpenAI latency |
| Cost high | Model distribution |
| Errors high | Health checks |
| Cache low | Query diversity |

---

## **🔌 How Monitoring Works**

```
Request → Query Service → Metrics Collector
                           ↓
                    Record metrics
                           ↓
                    Update SLO status
                           ↓
                    Check thresholds
                           ↓
                    Send alerts (if needed)
```

---

## **📈 Dashboard Metrics to Plot**

1. **Performance:**
   - P50, P95, P99 latency (line graph)
   - Success rate (gauge)
   - Query count (counter)

2. **Cost:**
   - Hourly cost (line graph)
   - Cost per query (gauge)
   - Total daily cost (counter)

3. **Cache:**
   - Hit rate % (gauge)
   - Hits vs misses (pie chart)

4. **Errors:**
   - Error count by type (bar chart)
   - Error rate % (gauge)

---

**Version:** 2.0.0 | **Status:** ✅ Production Ready
