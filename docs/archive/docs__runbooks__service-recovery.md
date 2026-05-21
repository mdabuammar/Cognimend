# 🚨 Service Recovery Runbook

## Overview

This runbook covers recovering DriftGuard services when they are completely down or unresponsive.

## Severity: P1 (Critical)

## Response Time: 15 minutes

## Step 1: Initial Assessment (2 min)

### Quick Health Check

```bash
# Check all pods
kubectl get pods -n driftguard-prod

# Check all services
kubectl get svc -n driftguard-prod

# Check deployments
kubectl get deployments -n driftguard-prod

# Quick health endpoint check
curl -s -o /dev/null -w "%{http_code}" https://driftguard.example.com/health
```

### Identify Which Service is Down

```bash
# Check each service
for svc in controller query upload evaluation drift telemetry; do
  echo "=== $svc ==="
  kubectl get pods -n driftguard-prod -l app=driftguard-$svc
done
```

## Step 2: Diagnose the Issue

### Check Pod Status

```bash
# Get detailed pod status
kubectl describe pod -n driftguard-prod -l app=driftguard-controller | grep -A 20 "Events:"

# Check for OOMKilled or CrashLoopBackOff
kubectl get pods -n driftguard-prod -o wide | grep -E "OOMKilled|CrashLoop|Error"
```

### Check Logs

```bash
# Current pod logs
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=100

# Previous pod logs (if crashed)
kubectl logs -l app=driftguard-controller -n driftguard-prod --previous --tail=100
```

### Check Resources

```bash
# Check node resources
kubectl top nodes

# Check pod resources
kubectl top pods -n driftguard-prod

# Check if resource quota exceeded
kubectl describe resourcequota -n driftguard-prod
```

## Step 3: Recovery Actions

### Scenario A: Pods Crashing (CrashLoopBackOff)

```bash
# Check why pods are crashing
kubectl logs -l app=driftguard-controller -n driftguard-prod --previous

# Common causes:
# 1. Config error - Check configmaps
kubectl get configmap driftguard-config -n driftguard-prod -o yaml

# 2. Secret missing - Check secrets
kubectl get secrets driftguard-secrets -n driftguard-prod

# 3. Dependency unavailable - Check dependencies
kubectl get pods -n driftguard-prod -l tier=infrastructure

# Force restart with fresh pods
kubectl rollout restart deployment/driftguard-controller -n driftguard-prod
```

### Scenario B: Pods Not Starting (Pending)

```bash
# Check why pending
kubectl describe pod <pod-name> -n driftguard-prod | grep -A 10 "Events:"

# Common causes:
# 1. Insufficient resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# 2. Image pull error
kubectl get events -n driftguard-prod | grep -i "pull"

# 3. Volume mount issues
kubectl get pvc -n driftguard-prod
```

### Scenario C: Pods Running But Not Responding

```bash
# Check readiness probe
kubectl describe pod <pod-name> -n driftguard-prod | grep -A 5 "Readiness"

# Check if app is listening
kubectl exec -it <pod-name> -n driftguard-prod -- curl -s localhost:8005/health

# Restart pods
kubectl delete pod <pod-name> -n driftguard-prod
```

### Scenario D: All Pods Down

```bash
# Check node status
kubectl get nodes

# If nodes are down, check cloud provider console

# Scale deployment to 0 and back
kubectl scale deployment/driftguard-controller -n driftguard-prod --replicas=0
sleep 10
kubectl scale deployment/driftguard-controller -n driftguard-prod --replicas=3

# Or force rollout
kubectl rollout restart deployment -n driftguard-prod
```

## Step 4: Infrastructure Recovery

### Database Recovery

```bash
# Check PostgreSQL
kubectl get pods -n driftguard-prod -l app=postgres

# If down, restart
kubectl rollout restart statefulset/postgres -n driftguard-prod

# Check if data is intact
kubectl exec -it postgres-0 -n driftguard-prod -- psql -U postgres -c "\dt"
```

### Redis Recovery

```bash
# Check Redis
kubectl get pods -n driftguard-prod -l app=redis

# If down, restart
kubectl rollout restart statefulset/redis -n driftguard-prod

# Check connection
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli ping
```

### Qdrant Recovery

```bash
# Check Qdrant
kubectl get pods -n driftguard-prod -l app=qdrant

# If down, restart
kubectl rollout restart statefulset/qdrant -n driftguard-prod

# Check health
kubectl exec -it qdrant-0 -n driftguard-prod -- curl localhost:6333/health
```

## Step 5: Verify Recovery

```bash
# Check all pods running
kubectl get pods -n driftguard-prod

# Check health endpoint
curl -s https://driftguard.example.com/health | jq .

# Check key functionality
curl -s https://driftguard.example.com/api/documents | jq .

# Monitor for 5 minutes
watch -n 10 'kubectl get pods -n driftguard-prod && echo "---" && curl -s -o /dev/null -w "%{http_code}" https://driftguard.example.com/health'
```

## Step 6: Post-Recovery

1. **Update Status Page**
   ```
   Status: Resolved
   Message: Service restored. Root cause under investigation.
   ```

2. **Notify Stakeholders**
   - Post in #driftguard-incidents
   - Email to stakeholders if prolonged outage

3. **Document**
   - Create incident ticket
   - Record timeline
   - Document actions taken

4. **Post-Mortem**
   - Schedule within 48 hours
   - Include all responders

## Emergency Contacts

| Role | Contact |
|------|---------|
| On-Call | Check PagerDuty |
| Eng Lead | @lead in Slack |
| DevOps | @devops-team in Slack |
| DBA | @dba-team in Slack |

## Escalation

If service cannot be recovered within 30 minutes:
1. Escalate to engineering lead
2. Consider failover to DR region (if available)
3. Declare major incident
4. Engage all hands
