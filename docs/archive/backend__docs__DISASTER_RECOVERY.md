# Disaster Recovery Plan

## Overview

This document outlines the disaster recovery (DR) procedures for the RAG Query Service. It defines Recovery Time Objectives (RTO), Recovery Point Objectives (RPO), and step-by-step procedures for various disaster scenarios.

## Recovery Objectives

### RTO (Recovery Time Objective)

| Tier | RTO | Systems |
|------|-----|---------|
| Critical | < 15 minutes | Query Service, Database |
| High | < 1 hour | Upload Service, Vector DB |
| Medium | < 4 hours | Monitoring, Telemetry |
| Low | < 24 hours | Analytics, Reporting |

### RPO (Recovery Point Objective)

| Data Type | RPO | Backup Frequency |
|-----------|-----|------------------|
| User Data | 0 (real-time) | Continuous replication |
| Documents | < 1 hour | Hourly snapshots |
| Vectors | < 1 hour | Hourly snapshots |
| Metrics | < 24 hours | Daily export |
| Logs | < 6 hours | 6-hour rotation |

## Backup Strategy

### Automated Backups

```bash
# Daily backup at 2 AM
0 2 * * * /opt/scripts/backup.py --type all --cleanup

# Hourly vector DB snapshot
0 * * * * /opt/scripts/backup.py --type qdrant

# Continuous PostgreSQL WAL archiving
# Configured via postgresql.conf
```

### Backup Locations

| Type | Primary | Secondary | Retention |
|------|---------|-----------|-----------|
| PostgreSQL | S3 bucket | Local NAS | 30 days |
| Qdrant | S3 bucket | Local NAS | 14 days |
| Redis | S3 bucket | Local | 7 days |
| Config | Git repo | S3 | Indefinite |

## Disaster Scenarios

### Scenario 1: Single Service Failure

**Detection**: Health check fails, alerts triggered

**Response**:
1. Kubernetes automatically restarts pod
2. If restart fails 3x, alert on-call engineer
3. Check logs: `kubectl logs -f deployment/<service>`
4. If persistent, scale up replicas: `kubectl scale --replicas=3`

**Recovery Time**: < 5 minutes (automated)

### Scenario 2: Database Failure

**Detection**: Database health check fails

**Response**:
1. Check Patroni cluster status
2. Verify automatic failover occurred
3. If no failover, manual promotion:
   ```bash
   patronictl switchover --master <current> --candidate <new>
   ```
4. Verify replication is caught up
5. Update connection strings if needed

**Recovery Time**: < 5 minutes (automated), < 15 minutes (manual)

### Scenario 3: Complete Cluster Failure

**Detection**: All services unreachable

**Response**:
1. **Assess**: Determine scope of failure
2. **Communicate**: Notify stakeholders
3. **Activate DR Site**:
   ```bash
   # Switch DNS to DR site
   ./scripts/activate-dr-site.sh
   
   # Start DR cluster
   kubectl apply -f infrastructure/kubernetes/ha-services.yaml
   ```
4. **Restore Data**:
   ```bash
   # Restore from latest backup
   python scripts/restore.py --type all --latest
   ```
5. **Verify**: Run smoke tests
6. **Monitor**: Watch for issues

**Recovery Time**: < 1 hour

### Scenario 4: Data Corruption

**Detection**: Application errors, data validation failures

**Response**:
1. **Isolate**: Stop affected services
2. **Assess**: Determine corruption scope
3. **Point-in-Time Recovery**:
   ```bash
   # Restore to specific point
   python scripts/restore.py --type postgres --point-in-time "2024-01-15 14:30:00"
   ```
4. **Verify**: Check data integrity
5. **Resume**: Restart services

**Recovery Time**: < 2 hours

### Scenario 5: Security Breach

**Detection**: Security alerts, anomalous activity

**Response**:
1. **Contain**: Isolate affected systems
2. **Preserve**: Capture forensic data
3. **Investigate**: Determine breach scope
4. **Remediate**: 
   - Rotate all credentials
   - Patch vulnerabilities
   - Restore from clean backup
5. **Report**: Notify stakeholders and authorities if required

**Recovery Time**: Variable (depends on severity)

### Scenario 6: Region Failure

**Detection**: AWS/GCP region unavailable

**Response**:
1. **Failover DNS**: Route to DR region
2. **Activate DR**: Start services in secondary region
3. **Restore Data**: Use cross-region replicated data
4. **Verify**: Confirm service functionality
5. **Monitor**: Watch for primary region recovery

**Recovery Time**: < 30 minutes

## DR Site Configuration

### Primary Site
- Region: us-east-1
- Kubernetes: 3-node cluster
- Database: PostgreSQL with Patroni (3 nodes)
- Vector DB: Qdrant cluster (3 nodes)

### DR Site
- Region: us-west-2
- Kubernetes: 3-node cluster (standby)
- Database: Streaming replica
- Vector DB: Async replication

### Failover Procedure

```bash
#!/bin/bash
# activate-dr-site.sh

# 1. Promote DR database
kubectl exec -n database pg-dr-0 -- patronictl switchover

# 2. Update DNS
aws route53 change-resource-record-sets ...

# 3. Scale up DR services
kubectl -n rag-system scale deployment --all --replicas=3

# 4. Verify health
./scripts/health-check.sh --all
```

## Communication Plan

### Escalation Matrix

| Severity | Response Time | Notify |
|----------|--------------|--------|
| SEV1 | Immediate | On-call, Eng Lead, Director |
| SEV2 | 15 minutes | On-call, Eng Lead |
| SEV3 | 1 hour | On-call |
| SEV4 | Next business day | Team lead |

### Communication Channels

- **PagerDuty**: Primary alerting
- **Slack #incidents**: Real-time updates
- **Status Page**: Customer communication
- **Email**: Stakeholder updates

### Incident Response Template

```
INCIDENT REPORT
===============
Incident ID: INC-YYYY-NNNN
Severity: SEV1/2/3/4
Status: Active/Resolved

Summary: [Brief description]

Timeline:
- [Time] Detection
- [Time] Response initiated
- [Time] Root cause identified
- [Time] Mitigation applied
- [Time] Resolved

Root Cause: [Description]

Resolution: [Actions taken]

Follow-up: [Preventive measures]
```

## Testing Schedule

### DR Drill Schedule

| Test Type | Frequency | Duration | Scope |
|-----------|-----------|----------|-------|
| Tabletop | Monthly | 2 hours | Team discussion |
| Failover | Quarterly | 4 hours | Database failover |
| Full DR | Annually | 8 hours | Complete site failover |

### Test Checklist

- [ ] Backup integrity verified
- [ ] Restore procedure tested
- [ ] Failover time measured
- [ ] Communication plan tested
- [ ] Runbooks updated
- [ ] Gaps documented

## Runbook Updates

This document should be reviewed and updated:
- After every DR test
- After every actual incident
- Quarterly at minimum
- When infrastructure changes

## Contacts

| Role | Name | Contact |
|------|------|---------|
| On-call Primary | Rotation | PagerDuty |
| On-call Secondary | Rotation | PagerDuty |
| Engineering Lead | TBD | [email] |
| Director of Eng | TBD | [email] |
| Security Team | TBD | [email] |
