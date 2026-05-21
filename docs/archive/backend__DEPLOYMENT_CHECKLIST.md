# ✅ PRODUCTION DEPLOYMENT CHECKLIST

## **PRE-DEPLOYMENT (DO THIS FIRST)**

### **Code Preparation**
- [ ] All environment variables set in `.env`
- [ ] API key verified and working
- [ ] Database credentials configured
- [ ] Qdrant host/port correct
- [ ] No hardcoded secrets in code
- [ ] All imports resolved (test imports)

### **Dependencies**
- [ ] `pip install -r requirements.txt` successful
- [ ] Python version >= 3.8
- [ ] PostgreSQL 12+ running
- [ ] Qdrant 0.10+ running
- [ ] OpenAI API key valid (test call works)

### **Database**
- [ ] Database created and accessible
- [ ] Run `python setup_database.py` successful
- [ ] All 8 tables created
- [ ] Indexes created
- [ ] Connection pooling enabled

### **Services**
- [ ] Backend service starts: `python -m uvicorn main_production:app --port 8002`
- [ ] No startup errors
- [ ] Health check passes: `/health`
- [ ] Sample query works: `POST /query`

---

## **LOCAL TESTING (VERIFY EVERYTHING)**

### **Health Checks**
- [ ] Basic health: `curl http://localhost:8002/health`
- [ ] Detailed health: `curl http://localhost:8002/health/detailed`
- [ ] All components show `healthy`
- [ ] Database connected ✅
- [ ] Qdrant connected ✅
- [ ] OpenAI accessible ✅

### **Query Testing**
- [ ] Sample query succeeds
- [ ] Response includes: answer, confidence, citations, latency, cost
- [ ] Confidence score between 0-100%
- [ ] Cost > $0
- [ ] Latency < 5000ms

### **Metrics Testing**
- [ ] `/metrics/summary` returns data
- [ ] `/metrics/prometheus` returns Prometheus format
- [ ] `/profile/query_documents` available
- [ ] `/alerts/history` shows no alerts (good sign)
- [ ] Run test script: `python test_monitoring.py`

### **Caching Testing**
- [ ] First query not cached
- [ ] Second identical query cached
- [ ] Latency on cached query < 100ms
- [ ] Cache hit counter increases

### **Error Handling**
- [ ] Invalid question returns 400
- [ ] Empty question returns 400
- [ ] Missing context returns 404 (gracefully)
- [ ] Circuit breaker not OPEN

---

## **INFRASTRUCTURE SETUP**

### **Docker (Optional)**
- [ ] Dockerfile exists and builds
- [ ] `docker-compose.yml` configured
- [ ] All services defined (query, postgres, qdrant)
- [ ] Environment variables passed to container
- [ ] Volumes mounted for persistence
- [ ] Networks configured

### **Load Balancer**
- [ ] NGINX or HAProxy configured
- [ ] Port 8002 accessible
- [ ] SSL/TLS certificate installed
- [ ] Health check endpoint configured
- [ ] Rate limiting configured

### **Monitoring**
- [ ] Prometheus running (optional)
- [ ] Scrape config added for service
- [ ] Grafana running (optional)
- [ ] Dashboards imported
- [ ] Alerting rules configured

### **Logging**
- [ ] ELK/Splunk configured (optional)
- [ ] Logs being ingested
- [ ] Query-level logs visible
- [ ] Error logs aggregated

### **Backups**
- [ ] PostgreSQL backups scheduled (daily)
- [ ] Backup location secure and tested
- [ ] Recovery procedure documented
- [ ] Retention policy set (30 days minimum)

---

## **SECURITY CHECKLIST**

### **Code Security**
- [ ] No API keys in code
- [ ] No passwords in code
- [ ] No debug mode enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention verified
- [ ] CORS properly configured

### **Infrastructure Security**
- [ ] Firewall rules configured
- [ ] Only necessary ports open (8002)
- [ ] SSH key-based auth only
- [ ] Fail2ban or similar configured
- [ ] DDoS protection considered
- [ ] VPN for admin access

### **API Security**
- [ ] Rate limiting enabled
- [ ] API key rotation plan
- [ ] Circuit breaker configured
- [ ] Timeout limits set (30s)
- [ ] Maximum request size limited
- [ ] HTTPS enforced

### **Database Security**
- [ ] Strong password (20+ chars)
- [ ] Database not exposed to internet
- [ ] Connection encryption enabled
- [ ] Read-only user for backups
- [ ] Audit logging enabled
- [ ] SQL queries parameterized

---

## **PERFORMANCE VERIFICATION**

### **Latency**
- [ ] P50 < 800ms
- [ ] P95 < 2000ms
- [ ] P99 < 3000ms
- [ ] Avg latency stable

### **Throughput**
- [ ] 10+ QPS tested
- [ ] 100+ QPS tested
- [ ] No degradation under load
- [ ] Connection pooling effective

### **Cost**
- [ ] Cost per query < $0.006
- [ ] Cost tracking working
- [ ] Models optimized
- [ ] Cache hit rate > 30%

### **Reliability**
- [ ] Error rate < 1%
- [ ] No data loss on restart
- [ ] Recovery time < 1 minute
- [ ] Health checks pass 100%

---

## **DOCUMENTATION**

- [ ] Deployment guide updated
- [ ] Runbook created
- [ ] Troubleshooting guide available
- [ ] Team trained
- [ ] On-call rotation established
- [ ] Escalation procedures documented

---

## **MONITORING SETUP**

### **Metrics**
- [ ] Prometheus collecting metrics
- [ ] Grafana dashboards created
- [ ] Latency dashboard visible
- [ ] Cost dashboard visible
- [ ] Error rate dashboard visible

### **Alerts**
- [ ] Alert thresholds configured
- [ ] Slack integration (or email)
- [ ] PagerDuty integration (if critical)
- [ ] Alert testing done
- [ ] On-call notified of alerts

### **Logs**
- [ ] Centralized logging configured
- [ ] Query logs searchable
- [ ] Error logs aggregated
- [ ] Retention policy set

---

## **PRODUCTION ENVIRONMENT SETUP**

### **Environment Variables**
```bash
# Required (already set)
OPENAI_API_KEY=<your-openrouter-api-key>
POSTGRES_PASSWORD=<redacted-secret>

# Optional (verify defaults)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=cognimend_prod
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

### **Resource Allocation**
- [ ] CPU: 2+ cores
- [ ] RAM: 4GB+
- [ ] Disk: 100GB+ (for data growth)
- [ ] Network: 100Mbps+

### **Scaling Readiness**
- [ ] Horizontal scaling possible
- [ ] Load balancing configured
- [ ] Database replication ready
- [ ] Cache layer ready

---

## **FINAL CHECKS (BEFORE GOING LIVE)**

### **Week Before**
- [ ] Production environment fully set up
- [ ] All tests passing
- [ ] Team trained and ready
- [ ] Escalation procedures in place
- [ ] Monitoring verified

### **Day Before**
- [ ] Final load testing
- [ ] Backup verified
- [ ] Disaster recovery tested
- [ ] Team on-call roster confirmed
- [ ] Rollback procedure ready

### **Day Of**
- [ ] Service starts cleanly
- [ ] Health checks all green ✅
- [ ] Initial queries successful
- [ ] Metrics flowing to monitoring
- [ ] Alerts tested and working
- [ ] Team monitoring in real-time

### **Post-Launch (24 hours)**
- [ ] Monitor P50/P95/P99 latency
- [ ] Check error rate (should be < 1%)
- [ ] Verify cache hit rate (should be > 30%)
- [ ] Monitor costs (should be $0.004-0.006 per query)
- [ ] Check for any SLO violations
- [ ] Review logs for issues

### **Post-Launch (1 week)**
- [ ] All metrics stable
- [ ] No unexpected errors
- [ ] Cost within budget
- [ ] User feedback positive
- [ ] SLO compliance > 99%

---

## **ROLLBACK PROCEDURE**

If something goes wrong:

1. **Immediate:**
   - [ ] Stop new traffic (at load balancer)
   - [ ] Restart service: `docker restart query-service`
   - [ ] Check health: `curl /health/detailed`

2. **If health checks fail:**
   - [ ] Revert to previous version
   - [ ] Check database connectivity
   - [ ] Check OpenAI API status
   - [ ] Check Qdrant status

3. **If still failing:**
   - [ ] Restore from backup
   - [ ] Contact support
   - [ ] Document incident
   - [ ] Post-mortem after recovery

---

## **OPERATIONAL PROCEDURES**

### **Daily**
- [ ] Check health dashboard
- [ ] Review error logs
- [ ] Verify cost tracking
- [ ] Check alert history

### **Weekly**
- [ ] Review SLO compliance
- [ ] Check performance trends
- [ ] Analyze error patterns
- [ ] Review capacity trends

### **Monthly**
- [ ] Full backup verification
- [ ] Disaster recovery drill
- [ ] Performance analysis
- [ ] Cost optimization review
- [ ] Security audit

---

## **SUCCESS CRITERIA**

Your system is production-ready when:

✅ All checklist items checked  
✅ All health checks passing  
✅ P95 latency < 2000ms  
✅ Error rate < 1%  
✅ Success rate > 99%  
✅ Cost tracking working  
✅ Monitoring alerts functional  
✅ Team trained and ready  
✅ Documentation complete  
✅ Backup/recovery tested  

---

## **SIGN-OFF**

- [ ] Technical Lead: _____________ Date: _______
- [ ] DevOps Engineer: _____________ Date: _______
- [ ] Product Manager: _____________ Date: _______

---

**DEPLOYMENT APPROVED:** _____________ (Date/Time)

---

**Reference Documents:**
- [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)
- [MONITORING_GUIDE.md](MONITORING_GUIDE.md)
- [SYSTEM_COMPLETE.md](SYSTEM_COMPLETE.md)

**Need Help?**
- Check logs: `docker logs query-service`
- Health check: `curl http://localhost:8002/health/detailed`
- Metrics: `curl http://localhost:8002/metrics/summary`
- Test monitoring: `python test_monitoring.py`

Good luck with your deployment! 🚀
