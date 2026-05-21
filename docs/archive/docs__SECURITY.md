# Security Guide

> Security best practices, hardening guidelines, and compliance requirements for the Cognimend RAG System.

## Table of Contents

- [Security Overview](#security-overview)
- [Authentication & Authorization](#authentication--authorization)
- [API Security](#api-security)
- [Data Protection](#data-protection)
- [Infrastructure Security](#infrastructure-security)
- [Secrets Management](#secrets-management)
- [Network Security](#network-security)
- [Container Security](#container-security)
- [Compliance](#compliance)
- [Security Monitoring](#security-monitoring)
- [Incident Response](#incident-response)

---

## Security Overview

### Security Principles

1. **Defense in Depth** - Multiple layers of security controls
2. **Least Privilege** - Minimal permissions necessary
3. **Zero Trust** - Verify everything, trust nothing
4. **Secure by Default** - Security-first configuration

### Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WAF / DDoS Protection                    │
├─────────────────────────────────────────────────────────────────┤
│                      TLS Termination (Ingress)                   │
├─────────────────────────────────────────────────────────────────┤
│                    API Gateway (Rate Limiting)                   │
├─────────────────────────────────────────────────────────────────┤
│                 Authentication (JWT/OAuth2)                      │
├─────────────────────────────────────────────────────────────────┤
│                    Authorization (RBAC)                          │
├─────────────────────────────────────────────────────────────────┤
│              Service Mesh (mTLS between services)                │
├─────────────────────────────────────────────────────────────────┤
│         Network Policies (Pod-to-Pod restrictions)               │
├─────────────────────────────────────────────────────────────────┤
│              Encrypted Storage (Data at Rest)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication & Authorization

### JWT Authentication

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime, timedelta

security = HTTPBearer()

class JWTAuth:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_id: str, roles: list[str], expires_delta: timedelta = timedelta(hours=1)) -> str:
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": user_id,
            "roles": roles,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())  # Unique token ID for revocation
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    return jwt_auth.verify_token(credentials.credentials)
```

### Role-Based Access Control (RBAC)

```python
from enum import Enum
from functools import wraps

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READER = "reader"
    SERVICE = "service"

class Permission(str, Enum):
    READ_DOCUMENTS = "read:documents"
    WRITE_DOCUMENTS = "write:documents"
    DELETE_DOCUMENTS = "delete:documents"
    MANAGE_USERS = "manage:users"
    VIEW_METRICS = "view:metrics"

ROLE_PERMISSIONS = {
    Role.ADMIN: [Permission.READ_DOCUMENTS, Permission.WRITE_DOCUMENTS, 
                 Permission.DELETE_DOCUMENTS, Permission.MANAGE_USERS, Permission.VIEW_METRICS],
    Role.USER: [Permission.READ_DOCUMENTS, Permission.WRITE_DOCUMENTS],
    Role.READER: [Permission.READ_DOCUMENTS],
    Role.SERVICE: [Permission.READ_DOCUMENTS, Permission.WRITE_DOCUMENTS, Permission.VIEW_METRICS]
}

def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            user_roles = current_user.get("roles", [])
            user_permissions = set()
            for role in user_roles:
                user_permissions.update(ROLE_PERMISSIONS.get(Role(role), []))
            
            if permission not in user_permissions:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Usage
@app.delete("/documents/{doc_id}")
@require_permission(Permission.DELETE_DOCUMENTS)
async def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    ...
```

### Multi-Tenancy

```python
class TenantMiddleware:
    """Enforce tenant isolation."""
    
    async def __call__(self, request: Request, call_next):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            payload = jwt_auth.verify_token(token)
            request.state.tenant_id = payload.get("tenant_id")
        
        response = await call_next(request)
        return response

# Always filter by tenant
async def get_documents(
    current_user: dict = Depends(get_current_user)
) -> list[Document]:
    tenant_id = current_user["tenant_id"]
    return await db.query(Document).filter(Document.tenant_id == tenant_id).all()
```

---

## API Security

### Input Validation

```python
from pydantic import BaseModel, Field, validator
import re

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    max_results: int = Field(default=10, ge=1, le=100)
    
    @validator('query')
    def sanitize_query(cls, v):
        # Remove potential injection patterns
        v = re.sub(r'[<>"\']', '', v)
        return v.strip()

class UploadRequest(BaseModel):
    filename: str = Field(..., regex=r'^[\w\-. ]+$')
    content_type: str = Field(..., regex=r'^(text|application)/(plain|pdf|json)$')
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/query")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def query_endpoint(request: Request, query: QueryRequest):
    ...

@app.post("/upload")
@limiter.limit("10/minute")  # More restrictive for uploads
async def upload_endpoint(request: Request, file: UploadFile):
    ...
```

### Request Size Limits

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request too large"}
            )
        return await call_next(request)
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.cognimend.com",
        "https://admin.cognimend.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600
)
```

---

## Data Protection

### Encryption at Rest

```yaml
# Kubernetes StorageClass with encryption
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: encrypted-storage
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  encrypted: "true"
  kmsKeyId: arn:aws:kms:region:account:key/key-id
```

### Encryption in Transit

```yaml
# TLS configuration for Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - api.cognimend.com
      secretName: tls-secret
```

### Data Classification

| Classification | Description | Handling Requirements |
|---------------|-------------|----------------------|
| **Public** | General information | Standard protection |
| **Internal** | Business data | Encryption, access control |
| **Confidential** | User PII, credentials | Encryption, audit logging, masking |
| **Restricted** | API keys, secrets | Vault storage, rotation |

### PII Handling

```python
import hashlib
from typing import Any

class PIIMasker:
    """Mask personally identifiable information."""
    
    @staticmethod
    def mask_email(email: str) -> str:
        parts = email.split('@')
        if len(parts) == 2:
            return f"{parts[0][:2]}***@{parts[1]}"
        return "***@***.***"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        return f"***-***-{phone[-4:]}" if len(phone) >= 4 else "***"
    
    @staticmethod
    def hash_identifier(identifier: str) -> str:
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

def sanitize_logs(data: dict) -> dict:
    """Remove PII from log data."""
    sensitive_keys = ['email', 'phone', 'ssn', 'password', 'api_key']
    sanitized = data.copy()
    for key in sensitive_keys:
        if key in sanitized:
            sanitized[key] = '[REDACTED]'
    return sanitized
```

---

## Infrastructure Security

### Pod Security Standards

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: app:latest
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      resources:
        limits:
          cpu: "1"
          memory: "1Gi"
        requests:
          cpu: "100m"
          memory: "128Mi"
```

### Pod Security Policy

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: restricted
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  hostNetwork: false
  hostIPC: false
  hostPID: false
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
  readOnlyRootFilesystem: true
```

---

## Secrets Management

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-secrets
  namespace: cognimend
type: Opaque
data:
  database-password: <base64-encoded>
  openrouter-api-key: <base64-encoded>
  jwt-secret: <base64-encoded>
```

### External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: rag-secrets
  namespace: cognimend
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: rag-secrets
  data:
    - secretKey: database-password
      remoteRef:
        key: cognimend/production
        property: database-password
    - secretKey: openrouter-api-key
      remoteRef:
        key: cognimend/production
        property: openrouter-api-key
```

### Secret Rotation

```python
import schedule
import time

def rotate_api_keys():
    """Rotate API keys periodically."""
    new_key = generate_new_api_key()
    
    # Update secret in Kubernetes
    update_kubernetes_secret("rag-secrets", "openrouter-api-key", new_key)
    
    # Notify services to reload
    trigger_rolling_restart()
    
    # Log rotation event
    audit_log.info("API key rotated", extra={"service": "openrouter"})

# Schedule rotation every 30 days
schedule.every(30).days.do(rotate_api_keys)
```

---

## Network Security

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: cognimend
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-query-traffic
  namespace: cognimend
spec:
  podSelector:
    matchLabels:
      app: query
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: qdrant
      ports:
        - port: 6333
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - port: 6379
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
```

### Service Mesh (mTLS)

```yaml
# Istio PeerAuthentication
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: cognimend
spec:
  mtls:
    mode: STRICT
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: query-authz
  namespace: cognimend
spec:
  selector:
    matchLabels:
      app: query
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/cognimend/sa/upload-service"
              - "cluster.local/ns/cognimend/sa/ingress"
```

---

## Container Security

### Image Scanning

```yaml
# GitHub Actions workflow for image scanning
- name: Scan image with Trivy
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: '${{ env.IMAGE_NAME }}'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'  # Fail on vulnerabilities
```

### Dockerfile Best Practices

```dockerfile
# Use minimal base image
FROM python:3.11-slim-bookworm AS base

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# Install dependencies with pinned versions
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . /app
WORKDIR /app

# Switch to non-root user
USER app

# Use HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Don't run as PID 1
ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Runtime Security

```yaml
# Falco rules for runtime monitoring
- rule: Unexpected outbound connection
  desc: Detect unexpected outbound connections
  condition: >
    container and 
    outbound and 
    not (fd.sip in (allowed_outbound_ips))
  output: >
    Unexpected outbound connection 
    (user=%user.name command=%proc.cmdline connection=%fd.name 
     container_id=%container.id image=%container.image.repository)
  priority: WARNING
```

---

## Compliance

### GDPR Requirements

| Requirement | Implementation |
|-------------|---------------|
| Right to access | `/users/{id}/data` endpoint |
| Right to erasure | `/users/{id}/delete` endpoint |
| Data portability | `/users/{id}/export` endpoint |
| Consent management | Consent tracking in database |
| Breach notification | Automated alerting within 72h |

### SOC 2 Controls

| Control | Implementation |
|---------|---------------|
| Access Control | RBAC, MFA, audit logs |
| Encryption | TLS 1.3, AES-256 at rest |
| Logging | Centralized logging, 90-day retention |
| Monitoring | Real-time alerting, 24/7 coverage |
| Incident Response | Documented procedures, regular drills |

### Audit Logging

```python
import structlog
from datetime import datetime

audit_logger = structlog.get_logger("audit")

class AuditEvent:
    def __init__(self, action: str, user_id: str, resource: str):
        self.action = action
        self.user_id = user_id
        self.resource = resource
        self.timestamp = datetime.utcnow().isoformat()
        self.ip_address = None
        self.user_agent = None
    
    def log(self):
        audit_logger.info(
            "audit_event",
            action=self.action,
            user_id=self.user_id,
            resource=self.resource,
            timestamp=self.timestamp,
            ip_address=self.ip_address,
            user_agent=self.user_agent
        )

# Usage
@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    event = AuditEvent(
        action="DELETE_DOCUMENT",
        user_id=current_user["sub"],
        resource=f"document:{doc_id}"
    )
    event.ip_address = request.client.host
    event.user_agent = request.headers.get("user-agent")
    event.log()
    
    await document_service.delete(doc_id)
```

---

## Security Monitoring

### Security Metrics

```yaml
# Prometheus alerts for security events
groups:
  - name: security
    rules:
      - alert: HighFailedLoginRate
        expr: rate(auth_failed_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High rate of failed login attempts
          
      - alert: SuspiciousAPIActivity
        expr: rate(api_requests_total{status="403"}[5m]) > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High rate of forbidden requests
          
      - alert: PotentialBruteForce
        expr: >
          sum(rate(auth_failed_total[5m])) by (source_ip) > 20
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: Potential brute force attack detected
```

### SIEM Integration

```python
from opensearchpy import OpenSearch

class SecurityEventLogger:
    def __init__(self, host: str):
        self.client = OpenSearch([host])
    
    def log_security_event(self, event_type: str, details: dict):
        doc = {
            "@timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": details.get("severity", "info"),
            "source_ip": details.get("source_ip"),
            "user_id": details.get("user_id"),
            "details": details
        }
        self.client.index(index="security-events", body=doc)
```

---

## Incident Response

### Response Procedures

1. **Detection** - Automated alerting triggers
2. **Triage** - Assess severity and impact
3. **Containment** - Isolate affected systems
4. **Eradication** - Remove threat
5. **Recovery** - Restore normal operations
6. **Lessons Learned** - Post-incident review

### Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Security On-Call | security@company.com | PagerDuty |
| Engineering Lead | eng-lead@company.com | Slack #incidents |
| Executive Sponsor | cto@company.com | Phone |

### Runbook: Compromised Credentials

```bash
#!/bin/bash
# Emergency credential rotation

# 1. Revoke current API keys
kubectl delete secret rag-secrets -n cognimend

# 2. Generate new secrets
NEW_DB_PASS=$(openssl rand -base64 32)
NEW_API_KEY=$(openssl rand -base64 32)
NEW_JWT_SECRET=$(openssl rand -base64 64)

# 3. Create new secret
kubectl create secret generic rag-secrets \
  --from-literal=database-password=$NEW_DB_PASS \
  --from-literal=openrouter-api-key=$NEW_API_KEY \
  --from-literal=jwt-secret=$NEW_JWT_SECRET \
  -n cognimend

# 4. Restart all services
kubectl rollout restart deployment -n cognimend

# 5. Invalidate all sessions
redis-cli -h redis-service FLUSHDB

# 6. Log incident
echo "Credential rotation completed at $(date)" >> /var/log/security-incidents.log
```

---

## Security Checklist

### Pre-Deployment

- [ ] All dependencies scanned for vulnerabilities
- [ ] Container images scanned
- [ ] Secrets stored in vault/secret manager
- [ ] Network policies configured
- [ ] RBAC policies reviewed
- [ ] TLS certificates valid

### Ongoing

- [ ] Regular security audits (quarterly)
- [ ] Penetration testing (annually)
- [ ] Dependency updates (weekly)
- [ ] Secret rotation (monthly)
- [ ] Access review (quarterly)
- [ ] Incident response drills (semi-annually)

---

*Last updated: 2024*
