# 🔄 Deployment Rollback Runbook

## Overview

This runbook covers rolling back a failed DriftGuard deployment using blue-green deployment strategy.

## Severity: P1 (Critical)

## When to Use

- Error rate exceeds 5% after deployment
- P95 latency exceeds 3 seconds
- Health checks failing
- User-reported errors spiking
- Service is unresponsive

## Automatic Rollback

The system will **automatically trigger rollback** if:
1. Error rate exceeds 10% for 1 minute
2. Health checks fail for 3 consecutive checks
3. Deployment does not become ready within 5 minutes

## Manual Rollback Procedure

### Step 1: Assess the Situation (2 min)

```bash
# Check current deployment status
kubectl get deployments -n driftguard-prod -l app=driftguard

# Check which version is active
kubectl get svc driftguard-api -n driftguard-prod -o jsonpath='{.spec.selector.version}'
# Output: "blue" or "green"

# Check pod status
kubectl get pods -n driftguard-prod -l app=driftguard-controller --show-labels

# Check recent events
kubectl get events -n driftguard-prod --sort-by='.lastTimestamp' | tail -20

# Check logs for errors
kubectl logs -l app=driftguard-controller -n driftguard-prod --tail=50 | grep -i error
```

### Step 2: Confirm Rollback Decision

**Checklist before rollback:**
- [ ] Confirmed error rate or latency exceeds thresholds
- [ ] Verified this is a deployment-related issue (not infrastructure)
- [ ] Notified team in #driftguard-incidents
- [ ] Documented the decision

### Step 3: Execute Rollback

#### Option A: GitHub Actions (Preferred)

1. Go to GitHub → Actions → "Deploy" workflow
2. Click "Run workflow"
3. Select:
   - Environment: `production`
   - Rollback: `true`
4. Confirm and run

#### Option B: kubectl (Manual)

```bash
# Get current active version
ACTIVE=$(kubectl get svc driftguard-api -n driftguard-prod -o jsonpath='{.spec.selector.version}')
echo "Current active: $ACTIVE"

# Determine rollback target
if [ "$ACTIVE" = "blue" ]; then
  TARGET="green"
else
  TARGET="blue"
fi
echo "Rolling back to: $TARGET"

# Switch traffic
kubectl patch svc driftguard-api \
  -n driftguard-prod \
  -p "{\"spec\":{\"selector\":{\"version\":\"$TARGET\"}}}"

# Verify switch
kubectl get svc driftguard-api -n driftguard-prod -o jsonpath='{.spec.selector.version}'
```

### Step 4: Verify Rollback (5 min)

```bash
# Check pod status
kubectl get pods -n driftguard-prod -l app=driftguard-controller

# Check health endpoint
curl -s https://driftguard.example.com/health | jq .

# Check error rate (from Prometheus)
curl -s "http://prometheus:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))' \
  | jq '.data.result[0].value[1]'

# Watch logs for errors
kubectl logs -l app=driftguard-controller -n driftguard-prod -f --tail=20
```

### Step 5: Post-Rollback Actions

1. **Update Status Page**
   ```
   Title: Service Degradation Resolved
   Status: Resolved
   Message: Rolled back to previous version. Service restored.
   ```

2. **Notify Team**
   - Post in #driftguard-incidents with details
   - Tag relevant engineers

3. **Create Incident Ticket**
   - Create JIRA ticket with:
     - Timeline of events
     - Commands executed
     - Error logs/screenshots
     - Root cause hypothesis

4. **Schedule Post-Mortem**
   - Within 48 hours for P1 incidents
   - Include all stakeholders

## Rollback Did Not Work?

If traffic switch didn't resolve the issue:

### Check if it's an infrastructure issue

```bash
# Check database
kubectl get pods -n driftguard-prod -l app=postgres
kubectl exec -it postgres-0 -n driftguard-prod -- pg_isready

# Check Redis
kubectl get pods -n driftguard-prod -l app=redis
kubectl exec -it redis-0 -n driftguard-prod -- redis-cli ping

# Check Qdrant
kubectl get pods -n driftguard-prod -l app=qdrant
curl -s http://qdrant:6333/health
```

### Escalate if needed

If infrastructure is healthy but service is still down:
1. Page secondary on-call
2. Page engineering lead
3. Consider declaring major incident

## Prevention Checklist

For future deployments:
- [ ] Always deploy to staging first
- [ ] Run smoke tests before production
- [ ] Use canary deployments for risky changes
- [ ] Monitor metrics during and after deployment
- [ ] Have rollback plan ready before deploying

## Contact

- **On-Call**: Check PagerDuty schedule
- **Slack**: #driftguard-incidents
- **Engineering Lead**: @lead in Slack
