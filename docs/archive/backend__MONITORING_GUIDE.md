# 🔍 MONITORING & OBSERVABILITY GUIDE (FAANG-LEVEL)

## **📊 WHAT'S BEEN IMPLEMENTED**

### **Enterprise Monitoring Stack**
- ✅ **Metrics Collector** - Prometheus-compatible metrics
- ✅ **Distributed Tracing** - Request flow tracking
- ✅ **Alert Manager** - Automated alerting with cooldown
- ✅ **Health Checker** - Multi-component health verification
- ✅ **Structured Logging** - ELK/Splunk compatible
- ✅ **Performance Profiler** - Operation-level profiling
- ✅ **SLO Compliance** - Service Level Objective tracking

---

## **📈 KEY MONITORING ENDPOINTS**

### **1. Real-Time Metrics (Prometheus)**
```bash
curl http://localhost:8002/metrics/prometheus
```

**Output:**
```
# HELP queries_total Total number of queries
# TYPE queries_total counter
queries_total 1543

# HELP query_latency_ms Query latency in milliseconds
# TYPE query_latency_ms histogram
query_latency_ms_bucket{le="100"} 23
query_latency_ms_bucket{le="500"} 456
query_latency_ms_bucket{le="1000"} 892
query_latency_ms_bucket{le="3000"} 1201
```

**Use Case:** Feed this to Prometheus/Grafana for real-time dashboards

---

### **2. Comprehensive Metrics Summary**
```bash
curl http://localhost:8002/metrics/summary
```

**Output:**
```json
{
  "overview": {
    "total_queries": 1543,
    "successful": 1512,
    "failed": 31,
    "success_rate": 98.01
  },
  "performance": {
    "avg_latency_ms": 847.23,
    "p50_latency_ms": 800,
    "p95_latency_ms": 1950,
    "p99_latency_ms": 2850
  },
  "cache": {
    "hits": 623,
    "misses": 920,
    "hit_rate": 40.38
  },
  "costs": {
    "total_usd": 8.12,
    "avg_per_query": 0.00527,
    "total_tokens": 246532
  },
  "models": {
    "gpt-4o": 1200,
    "gpt-4o-mini": 312
  },
  "slo_compliance": {
    "p50_latency": {
      "current": 800,
      "target": 800,
      "met": true
    },
    "p95_latency": {
      "current": 1950,
      "target": 2000,
      "met": true
    },
    "p99_latency": {
      "current": 2850,
      "target": 3000,
      "met": true
    },
    "success_rate": {
      "current": 98.01,
      "target": 99.5,
      "met": false
    },
    "cache_hit_rate": {
      "current": 40.38,
      "target": 40.0,
      "met": true
    }
  }
}
```

---

### **3. Detailed Health Check**
```bash
curl http://localhost:8002/health/detailed
```

**Output:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-26T15:30:00.123456",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 45,
      "details": "Database connected"
    },
    "qdrant": {
      "status": "healthy",
      "latency_ms": 32,
      "details": "3 collections available"
    },
    "openai": {
      "status": "healthy",
      "latency_ms": 512,
      "details": "OpenAI API accessible"
    }
  }
}
```

---

### **4. Performance Profiles**
```bash
curl http://localhost:8002/profile/query_documents
```

**Output:**
```json
{
  "operation": "query_documents",
  "count": 1543,
  "wall_time": {
    "min": 245,
    "max": 5123,
    "avg": 847.23,
    "p50": 800,
    "p95": 1950,
    "p99": 2850
  },
  "cpu_time": {
    "min": 12,
    "max": 234,
    "avg": 87.45
  }
}
```

---

### **5. Alert History**
```bash
curl http://localhost:8002/alerts/history?limit=10
```

**Output:**
```json
{
  "alerts": [
    {
      "severity": "warning",
      "title": "SLO Violation: success_rate",
      "message": "Current: 98.01, Target: 99.5",
      "metadata": {
        "current": 98.01,
        "target": 99.5,
        "met": false
      },
      "timestamp": "2024-01-26T15:25:00.123456"
    }
  ],
  "total": 47
}
```

---

## **🎯 SERVICE LEVEL OBJECTIVES (SLOs)**

### **Default SLO Targets**
```
✅ P50 Latency:        800ms
✅ P95 Latency:       2000ms
✅ P99 Latency:       3000ms
✅ Success Rate:      99.5%
✅ Cache Hit Rate:    40.0%
```

### **Modifying SLOs**
Edit [backend/core/monitoring.py](backend/core/monitoring.py):

```python
class MetricsCollector:
    def __init__(self):
        self.slo_targets = {
            "p50_latency_ms": 600,      # Lower = stricter
            "p95_latency_ms": 1500,
            "p99_latency_ms": 2500,
            "success_rate": 99.9,
            "cache_hit_rate": 50.0
        }
```

---

## **🚨 ALERTING SYSTEM**

### **Automatic Alerts**
Alerts are sent when:

1. **SLO Violations** - Latency exceeds target
2. **High Error Rate** - More than 1% failures
3. **Cost Anomalies** - Hourly cost > $2.00
4. **Circuit Breaker Open** - OpenAI API failures

### **Alert Cooldown**
Each alert type has a 5-minute cooldown to prevent spam:
```python
alert_manager.cooldown_seconds = 300  # 5 minutes
```

### **Integrating External Services**

Currently logs to standard Python logger. To add:

**Slack:**
```python
def send_to_slack(alert):
    webhook = os.getenv("SLACK_WEBHOOK")
    requests.post(webhook, json={"text": alert["message"]})
```

**PagerDuty:**
```python
def send_to_pagerduty(alert):
    if alert["severity"] == "critical":
        pagerduty_client.trigger_incident(alert)
```

**Email:**
```python
def send_email_alert(alert):
    send_email(
        to=os.getenv("ALERT_EMAIL"),
        subject=alert["title"],
        body=alert["message"]
    )
```

---

## **📊 METRICS EXPLAINED**

### **Overview Metrics**
| Metric | Meaning | Good Range |
|--------|---------|-----------|
| `success_rate` | % of queries that succeeded | > 99.5% |
| `total_queries` | Total queries processed | N/A |
| `failed_queries` | Count of failed queries | < 1% of total |

### **Performance Metrics**
| Metric | Meaning | Good Range |
|--------|---------|-----------|
| `avg_latency_ms` | Average response time | < 900ms |
| `p50_latency_ms` | Median response time | < 800ms |
| `p95_latency_ms` | 95th percentile latency | < 2000ms |
| `p99_latency_ms` | 99th percentile latency | < 3000ms |

### **Cache Metrics**
| Metric | Meaning | Good Range |
|--------|---------|-----------|
| `cache_hit_rate` | % of cached responses | > 40% |
| `hits` | Count of cache hits | N/A |
| `misses` | Count of cache misses | N/A |

### **Cost Metrics**
| Metric | Meaning | Good Range |
|--------|---------|-----------|
| `total_usd` | Total cost accrued | Track trend |
| `avg_per_query` | Average cost per query | < $0.006 |
| `total_tokens` | Total tokens used | Track trend |

---

## **🔍 DEBUGGING WITH MONITORING**

### **Issue: High Latency**
```bash
# Check P95/P99 latency
curl http://localhost:8002/metrics/summary | jq '.performance'

# Check profile
curl http://localhost:8002/profile/query_documents | jq '.wall_time'

# Review recent alerts
curl http://localhost:8002/alerts/history | jq '.alerts[-5:]'
```

### **Issue: High Error Rate**
```bash
# Check success rate
curl http://localhost:8002/metrics/summary | jq '.overview.success_rate'

# Check error types
curl http://localhost:8002/metrics/summary | jq '.errors'

# Check health
curl http://localhost:8002/health/detailed | jq '.status'
```

### **Issue: High Costs**
```bash
# Check costs
curl http://localhost:8002/metrics/summary | jq '.costs'

# Check hourly costs
curl http://localhost:8002/metrics/summary | jq '.hourly_costs'

# Review model usage
curl http://localhost:8002/metrics/summary | jq '.models'
```

---

## **📈 INTEGRATION WITH MONITORING TOOLS**

### **Prometheus**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'query-service'
    static_configs:
      - targets: ['localhost:8002']
    metrics_path: '/metrics/prometheus'
```

### **Grafana**
Create dashboard with:
- Success rate gauge
- Latency histogram (P50, P95, P99)
- Cache hit rate trend
- Cost trend (hourly/daily)
- Error rate alert

### **DataDog**
```python
# Automatically export to DataDog
from datadog import initialize, api

options = {
    'api_key': os.getenv('DATADOG_API_KEY'),
    'app_key': os.getenv('DATADOG_APP_KEY')
}
initialize(**options)
```

### **ELK Stack**
Structured logs automatically compatible:
```json
{
  "service": "query-service",
  "timestamp": "2024-01-26T15:30:00.123456",
  "level": "INFO",
  "message": "Query processed",
  "query_id": "uuid-here",
  "latency_ms": 847,
  "cost_usd": 0.005
}
```

---

## **⚙️ PERFORMANCE PROFILING**

### **Available Operations to Profile**
- `query_documents` - Main query operation
- `get_embedding` - OpenAI embedding call
- `generate_answer` - Answer generation

### **Example: Identifying Bottlenecks**
```bash
curl http://localhost:8002/profile/query_documents | jq '.'

# Output:
{
  "operation": "query_documents",
  "wall_time": {
    "avg": 847.23,
    "p95": 1950,
    "p99": 2850,
    ...
  }
}

# If P99 is high, investigate:
# 1. OpenAI API response time
# 2. Qdrant search performance
# 3. Database queries
```

---

## **🏥 HEALTH CHECK BEST PRACTICES**

### **Kubernetes Integration**
```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/detailed
    port: 8002
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/detailed
    port: 8002
  initialDelaySeconds: 10
  periodSeconds: 5
```

### **What Makes Service Unhealthy**
- Database connection fails
- Qdrant connection fails
- OpenAI API unreachable
- Circuit breaker is OPEN

---

## **📊 MONITORING BEST PRACTICES**

### **1. Set Realistic SLOs**
- Don't set SLOs too strict initially
- Base on actual performance data
- Gradually improve over time

### **2. Act on Alerts**
- Don't ignore SLO violations
- Investigate root causes
- Track trends

### **3. Monitor the Monitors**
- Ensure health checks run regularly
- Verify alert delivery
- Test failover scenarios

### **4. Regular Review**
- Weekly: Check SLO compliance
- Daily: Review error logs
- Monthly: Optimize based on metrics

---

## **🎯 NEXT STEPS**

1. **Start service:**
   ```bash
   cd backend/services/query
   python -m uvicorn main_production:app --port 8002
   ```

2. **Test endpoints:**
   ```bash
   curl http://localhost:8002/health/detailed
   curl http://localhost:8002/metrics/summary
   ```

3. **Set up Prometheus:**
   ```bash
   docker run -p 9090:9090 prom/prometheus
   ```

4. **Create Grafana dashboard**

5. **Configure alerting** (Slack/Email/PagerDuty)

---

**Status:** ✅ FAANG-LEVEL MONITORING IMPLEMENTED  
**Version:** 2.0.0  
**Last Updated:** January 26, 2024
