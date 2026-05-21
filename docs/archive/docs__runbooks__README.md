# DriftGuard Runbooks

This directory contains operational runbooks for managing DriftGuard in production.

## Quick Reference

| Scenario | Runbook | Severity | Escalation |
|----------|---------|----------|------------|
| Service Down | [service-recovery.md](./service-recovery.md) | P1 | On-call → Lead → Manager |
| High Error Rate | [high-error-rate.md](./high-error-rate.md) | P2 | On-call → Lead |
| Deployment Rollback | [rollback.md](./rollback.md) | P1 | On-call |
| Database Issues | [database-recovery.md](./database-recovery.md) | P1 | On-call → DBA |
| High Latency | [high-latency.md](./high-latency.md) | P2 | On-call |
| Security Incident | [security-incident.md](./security-incident.md) | P1 | Security Team |

## Escalation Matrix

| Priority | Response Time | Resolution Time | Who |
|----------|--------------|-----------------|-----|
| P1 (Critical) | 15 min | 1 hour | On-call + Lead + Manager |
| P2 (High) | 30 min | 4 hours | On-call + Lead |
| P3 (Medium) | 2 hours | 24 hours | On-call |
| P4 (Low) | 8 hours | 72 hours | Team |

## On-Call Information

- **PagerDuty Service**: driftguard-production
- **Slack Channel**: #driftguard-incidents
- **Status Page**: status.driftguard.example.com

## Common Commands

```bash
# Check pod status
kubectl get pods -n driftguard-prod -l app=driftguard

# Check logs
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=100 -f

# Check deployments
kubectl get deployments -n driftguard-prod

# Check services
kubectl get svc -n driftguard-prod

# Check events
kubectl get events -n driftguard-prod --sort-by='.lastTimestamp' | tail -20

# Port forward for debugging
kubectl port-forward svc/driftguard-api 8080:80 -n driftguard-prod
```
