# DriftGuard Disaster Recovery Plan

## Executive Summary

This document outlines the disaster recovery (DR) procedures for DriftGuard, including Recovery Time Objectives (RTO), Recovery Point Objectives (RPO), and step-by-step procedures for various failure scenarios.

---

## 1. Recovery Objectives

### 1.1 RTO (Recovery Time Objective)

| Service | RTO Target | Priority |
|---------|-----------|----------|
| Query Service | 15 minutes | P0 |
| Upload Service | 30 minutes | P0 |
| Controller Service | 30 minutes | P1 |
| PostgreSQL Database | 30 minutes | P0 |
| Qdrant Vector DB | 1 hour | P1 |
| Redis Cache | 15 minutes | P2 |
| Frontend | 15 minutes | P0 |

### 1.2 RPO (Recovery Point Objective)

| Data Type | RPO Target | Backup Frequency |
|-----------|-----------|------------------|
| User documents | 1 hour | Hourly |
| Document metadata | 1 hour | Hourly |
| Vector embeddings | 24 hours | Daily |
| Query history | 6 hours | Every 6 hours |
| Configuration | 24 hours | Daily |
| User sessions | N/A (ephemeral) | Not backed up |

---

## 2. Backup Strategy

### 2.1 Automated Backup Schedule

```bash
# PostgreSQL - Every 6 hours
0 */6 * * * /opt/driftguard/scripts/backup.py --type postgres

# Qdrant - Daily at 2 AM
0 2 * * * /opt/driftguard/scripts/backup.py --type qdrant

# Redis - Daily at 3 AM
0 3 * * * /opt/driftguard/scripts/backup.py --type redis

# Full backup with cleanup - Weekly Sunday at 4 AM
0 4 * * 0 /opt/driftguard/scripts/backup.py --type all --cleanup
```

### 2.2 Backup Storage

| Location | Purpose | Retention |
|----------|---------|-----------|
| Local `/backups` | Fast recovery | 7 days |
| S3 `driftguard-backups` | Long-term storage | 90 days |
| Cross-region S3 | DR site recovery | 30 days |

### 2.3 Manual Backup Commands

```bash
# Run full backup
python scripts/backup.py --type all

# Backup PostgreSQL only
python scripts/backup.py --type postgres

# Backup with S3 upload
python scripts/backup.py --type all --upload-s3

# Verify a backup
python scripts/backup.py --verify ./backups/postgres/pg_20260127_120000.sql.gz
```

---

## 3. Disaster Scenarios & Recovery Procedures

### 3.1 Scenario A: Single Pod/Container Failure

**Impact:** One service instance unavailable  
**Automatic Recovery:** Yes (Kubernetes restarts)  
**Manual Intervention:** Only if auto-restart fails

**Steps (if manual intervention needed):**
```bash
# Check pod status
kubectl get pods -n driftguard

# View pod logs
kubectl logs -n driftguard <pod-name> --previous

# Delete pod to force restart
kubectl delete pod -n driftguard <pod-name>

# Scale deployment if needed
kubectl scale deployment query-service -n driftguard --replicas=3
```

**Estimated Recovery:** 1-5 minutes (automatic)

---

### 3.2 Scenario B: Single Service Deployment Failure

**Impact:** All instances of one service unavailable  
**Detection:** Alerts, health check failures

**Steps:**
```bash
# 1. Check deployment status
kubectl describe deployment query-service -n driftguard

# 2. Check recent events
kubectl get events -n driftguard --sort-by='.lastTimestamp'

# 3. If bad deployment, rollback
kubectl rollout undo deployment/query-service -n driftguard

# 4. Verify rollback
kubectl rollout status deployment/query-service -n driftguard

# 5. If still failing, check logs
kubectl logs -l app=driftguard,component=query-service -n driftguard --tail=100
```

**Estimated Recovery:** 5-15 minutes

---

### 3.3 Scenario C: Database Failure

**Impact:** All data-dependent operations fail  
**Severity:** Critical

#### 3.3.1 PostgreSQL Primary Failure (Patroni auto-failover)

```bash
# 1. Check Patroni cluster status
kubectl exec -it driftguard-postgres-0 -n driftguard -- patronictl list

# 2. If automatic failover didn't happen, force it
kubectl exec -it driftguard-postgres-1 -n driftguard -- patronictl failover --force

# 3. Verify new primary
kubectl exec -it driftguard-postgres-1 -n driftguard -- patronictl list

# 4. Check application connectivity
kubectl logs -l app=driftguard -n driftguard --tail=20 | grep -i postgres
```

#### 3.3.2 Complete PostgreSQL Cluster Failure

```bash
# 1. Scale down applications to prevent data corruption
kubectl scale deployment --all -n driftguard --replicas=0

# 2. Check for any surviving pods
kubectl get pods -l app=postgres -n driftguard

# 3. If all pods down, restore from backup
# First, list available backups
python scripts/restore.py --type postgres --list

# 4. Restore from latest backup
python scripts/restore.py --type postgres --force

# 5. Recreate PostgreSQL cluster if needed
kubectl delete postgresql driftguard-postgres -n driftguard
kubectl apply -f infrastructure/kubernetes/ha-databases.yaml

# 6. Wait for cluster to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n driftguard --timeout=300s

# 7. Restore data
python scripts/restore.py --type postgres

# 8. Scale applications back up
kubectl scale deployment query-service -n driftguard --replicas=3
kubectl scale deployment upload-service -n driftguard --replicas=3
kubectl scale deployment controller-service -n driftguard --replicas=2
```

**Estimated Recovery:** 15-60 minutes

---

### 3.4 Scenario D: Qdrant Vector Database Failure

**Impact:** Search functionality unavailable  
**Fallback:** Queries return degraded results or error

```bash
# 1. Check Qdrant cluster status
kubectl get pods -l app=qdrant -n driftguard
curl http://qdrant.driftguard:6333/cluster

# 2. If single node failure, cluster auto-recovers
# Wait for pod restart and data sync

# 3. If complete cluster failure, restore from snapshot
# List available backups
python scripts/restore.py --type qdrant --list

# 4. Restore collection
python scripts/restore.py --type qdrant --file ./backups/qdrant/documents_20260127.snapshot

# 5. Verify restoration
curl http://qdrant.driftguard:6333/collections/documents

# 6. If needed, re-embed all documents
python scripts/reindex_documents.py --all
```

**Estimated Recovery:** 30 minutes - 4 hours (depending on reindexing)

---

### 3.5 Scenario E: Complete Cluster Failure

**Impact:** All services unavailable  
**Trigger for DR Site:** Yes

```bash
# 1. Assess the situation
kubectl cluster-info
kubectl get nodes

# 2. If cluster unrecoverable, activate DR site
./scripts/activate-dr-site.sh

# 3. Update DNS to point to DR site
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://dr-dns-failover.json

# 4. Verify DR site is serving traffic
curl https://driftguard.example.com/health

# 5. Restore data from cross-region backups
python scripts/restore.py --type all --backup-dir s3://driftguard-backups-dr/
```

**Estimated Recovery:** 1-4 hours

---

### 3.6 Scenario F: Data Corruption

**Impact:** Inconsistent or incorrect data  
**Requires:** Point-in-time recovery

```bash
# 1. Identify when corruption occurred
kubectl logs -l app=driftguard -n driftguard --since=24h | grep -i error

# 2. Stop writes to prevent further corruption
kubectl scale deployment upload-service -n driftguard --replicas=0

# 3. Identify last known good backup
python scripts/restore.py --type postgres --list

# 4. Create backup of current (corrupted) state for analysis
python scripts/backup.py --type postgres --suffix corrupted

# 5. Restore from last known good backup
python scripts/restore.py --type postgres --file ./backups/postgres/pg_20260126_180000.sql.gz --force

# 6. If WAL replay available, apply transactions up to corruption point
# (Requires PostgreSQL PITR configuration)

# 7. Restart services
kubectl scale deployment upload-service -n driftguard --replicas=3
```

**Estimated Recovery:** 1-8 hours (depending on data analysis)

---

## 4. DR Site Configuration

### 4.1 DR Site Location
- **Primary:** us-east-1
- **DR:** us-west-2

### 4.2 DR Site Sync
- Database: Asynchronous replication with 1-minute lag
- Qdrant: Daily snapshot sync
- Configurations: Continuous sync via GitOps

### 4.3 Failover Decision Matrix

| Outage Duration | Action |
|----------------|--------|
| < 15 minutes | Wait for auto-recovery |
| 15-30 minutes | Assess and prepare DR activation |
| > 30 minutes | Activate DR site |
| Primary site unrecoverable | Full DR activation |

---

## 5. Communication Plan

### 5.1 Internal Escalation

| Level | Trigger | Notify |
|-------|---------|--------|
| L1 | Health check failure | On-call engineer (PagerDuty) |
| L2 | Service degraded > 5 min | Engineering lead |
| L3 | Multiple services down | CTO, All engineering |
| L4 | Data loss confirmed | CEO, Legal, PR |

### 5.2 External Communication

| Time | Action |
|------|--------|
| 0-5 min | Update status page to "Investigating" |
| 5-15 min | Post initial incident details |
| Every 30 min | Post updates until resolved |
| Resolution | Post RCA timeline, prevention measures |

### 5.3 Status Page Updates

```bash
# Update status page (example with Statuspage.io)
curl -X POST https://api.statuspage.io/v1/pages/$PAGE_ID/incidents \
  -H "Authorization: OAuth $API_KEY" \
  -d '{
    "incident": {
      "name": "Service Degradation",
      "status": "investigating",
      "body": "We are investigating reports of slow query responses."
    }
  }'
```

---

## 6. Testing & Drills

### 6.1 Testing Schedule

| Test Type | Frequency | Last Tested | Next Scheduled |
|-----------|-----------|-------------|----------------|
| Backup verification | Weekly | - | - |
| Single service failover | Monthly | - | - |
| Database failover | Quarterly | - | - |
| Full DR drill | Annually | - | - |
| Tabletop exercise | Quarterly | - | - |

### 6.2 Drill Checklist

```markdown
## Pre-Drill
- [ ] Notify all stakeholders
- [ ] Ensure backup team availability
- [ ] Verify monitoring is active
- [ ] Document current system state

## During Drill
- [ ] Execute failure scenario
- [ ] Record actual recovery time
- [ ] Note any issues or blockers
- [ ] Document decision points

## Post-Drill
- [ ] Compare actual vs target RTO
- [ ] Document lessons learned
- [ ] Update procedures if needed
- [ ] Schedule follow-up improvements
```

---

## 7. Recovery Verification Checklist

After any recovery, verify:

```markdown
## Service Health
- [ ] All pods running: `kubectl get pods -n driftguard`
- [ ] All health checks passing: `curl /health` for each service
- [ ] No error logs: `kubectl logs -l app=driftguard --tail=100`

## Data Integrity
- [ ] Document count matches pre-incident
- [ ] Sample queries return correct results
- [ ] No orphaned vectors in Qdrant
- [ ] User sessions working

## Performance
- [ ] Response times within SLA
- [ ] No elevated error rates
- [ ] Cache hit rates normal
- [ ] Database connections stable

## External Dependencies
- [ ] OpenRouter API accessible
- [ ] S3 storage accessible
- [ ] DNS resolution working
```

---

## 8. Contacts

| Role | Name | Contact |
|------|------|---------|
| Primary On-call | - | PagerDuty |
| Engineering Lead | - | - |
| CTO | - | - |
| AWS Support | - | AWS Support Console |
| Database Vendor | - | - |

---

## 9. Appendix

### A. Useful Commands Quick Reference

```bash
# Cluster status
kubectl get all -n driftguard

# Force pod restart
kubectl rollout restart deployment/<name> -n driftguard

# Check logs
kubectl logs -f -l app=driftguard -n driftguard

# Port forward for debugging
kubectl port-forward svc/query-service 8002:8002 -n driftguard

# Execute backup
python scripts/backup.py --type all

# List backups
python scripts/restore.py --type all --list

# Database shell
kubectl exec -it driftguard-postgres-0 -n driftguard -- psql -U driftguard cognimend
```

### B. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-27 | System | Initial version |

---

**Last Updated:** 2026-01-27  
**Next Review:** 2026-04-27  
**Document Owner:** Platform Engineering Team
