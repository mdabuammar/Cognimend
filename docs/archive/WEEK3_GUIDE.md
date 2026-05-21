# WEEK 3: DRIFT DETECTION + TELEMETRY
## Complete Implementation Guide

### Services Overview

#### 1. **Telemetry Service** (Port 8003)
- Collects and aggregates metrics from the system
- Tracks query performance, confidence scores, and document statistics
- Provides dashboard data for visualization

**Key Endpoints:**
- `GET /dashboard/stats` - Overall system statistics
- `GET /dashboard/drift-status` - Current drift detection status
- `GET /dashboard/confidence-trend` - 24-hour confidence trend
- `GET /dashboard/query-volume` - Query volume over 24 hours
- `GET /health` - Health check

#### 2. **Drift Detector Service** (Port 8004)
- Continuously monitors for data, retrieval, and performance drift
- Runs drift detection every 5 minutes in background
- Logs drift events to database for alerting
- Detects 3 types of drift:
  1. **Data Drift** - Document embeddings shift
  2. **Retrieval Drift** - Similarity scores drop (>10%)
  3. **Performance Drift** - Confidence scores drop (>5%)

**Key Endpoints:**
- `POST /detect` - Manually trigger drift detection
- `GET /health` - Health check

### Running the Services

#### Terminal 1: Telemetry Service
```bash
cd D:\Project\backend\services\telemetry
pip install -r requirements.txt
python main.py
# Runs on: http://localhost:8003
```

#### Terminal 2: Drift Detector Service
```bash
cd D:\Project\backend\services\drift_detector
pip install -r requirements.txt
python main.py
# Runs on: http://localhost:8004
```

### Frontend Integration

The frontend now includes API clients for:
- `telemetryAPI` - Dashboard statistics and metrics
- `driftDetectorAPI` - Drift detection controls

**Environment Variables** (add to `frontend/.env.local`):
```
VITE_TELEMETRY_API_URL=http://localhost:8003
VITE_DRIFT_DETECTOR_API_URL=http://localhost:8004
```

### Testing the Services

#### Get Dashboard Statistics
```bash
curl http://localhost:8003/dashboard/stats
```
Response:
```json
{
  "total_queries": 5,
  "avg_confidence": 85.5,
  "avg_latency_ms": 250,
  "total_documents": 2,
  "confidence_change": 2.3
}
```

#### Get Drift Status
```bash
curl http://localhost:8003/dashboard/drift-status
```
Response:
```json
{
  "data_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "No action needed"
  },
  "retrieval_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "Monitoring"
  },
  "performance_drift": {
    "status": "no_drift",
    "last_detected": null,
    "action": "Stable"
  }
}
```

#### Get Confidence Trend (24 hours)
```bash
curl http://localhost:8003/dashboard/confidence-trend
```

#### Get Query Volume (24 hours)
```bash
curl http://localhost:8003/dashboard/query-volume
```

#### Manually Run Drift Detection
```bash
curl -X POST http://localhost:8004/detect
```

### Complete System Architecture

```
┌─────────────────────────────────────────────────────┐
│         Frontend Dashboard (8080)                   │
│  - Upload Page                                      │
│  - Query Page                                       │
│  - Dashboard Page (NEW - Shows drift alerts)       │
│  - Settings Page                                    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┼──────────┬──────────────┐
        │          │          │              │
        ▼          ▼          ▼              ▼
   ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
   │Upload  │ │ Query  │ │Telemetry │ │Drift         │
   │Service │ │Service │ │Service   │ │Detector      │
   │(8001)  │ │(8002)  │ │(8003)    │ │Service (8004)│
   └────────┘ └────────┘ └──────────┘ └──────────────┘
        │          │          │              │
        └──────────┴──────────┴──────────────┘
                   │
        ┌──────────▼──────────────┐
        │  PostgreSQL Database    │
        │  - documents            │
        │  - chunks               │
        │  - query_events         │
        │  - drift_events (NEW)   │
        └─────────────────────────┘
```

### Database Changes

New table created automatically:
```sql
CREATE TABLE drift_events (
    id SERIAL PRIMARY KEY,
    drift_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    metric_value FLOAT,
    threshold FLOAT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)
```

### Drift Detection Thresholds

| Type | Threshold | Severity |
|------|-----------|----------|
| **Data Drift** | >15% embedding shift | High: >25%, Medium: 15-25% |
| **Retrieval Drift** | >10% similarity drop | High: >20%, Medium: 10-20% |
| **Performance Drift** | >5% confidence drop | High: >15%, Medium: 5-15% |

### Next Steps

1. ✅ Start both services
2. ✅ Upload documents via frontend
3. ✅ Make queries to generate telemetry
4. ✅ Monitor drift alerts in dashboard
5. ✅ Integrate drift alerts into Dashboard page

### Service Status Check

```bash
# Check all services are running
curl http://localhost:8003/health
curl http://localhost:8004/health
```

### Troubleshooting

**Services won't start?**
- Check PostgreSQL is running: `docker ps`
- Check ports aren't in use: `netstat -an | findstr :8003` or `:8004`
- Check requirements are installed: `pip install -r requirements.txt`

**No drift events showing?**
- Need at least 100 queries in database to compare
- Drift is only detected if thresholds are exceeded
- Check database: `SELECT * FROM drift_events;`

---

**Week 3 Complete!** Your system now has:
- ✅ Telemetry tracking
- ✅ Drift detection (3 types)
- ✅ Database logging
- ✅ Dashboard APIs
- ✅ Frontend integration
