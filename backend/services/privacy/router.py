"""
Privacy API Endpoints
GDPR/CCPA compliant Data Subject Access Request (DSAR) endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ..shared.privacy import (
    DSARType, 
    DSARStatus, 
    dsar_manager, 
    consent_manager,
    scan_for_pii,
    redact_pii,
    audit_logger,
    AuditAction,
    RetentionPolicy
)
from ..shared.security import require_api_key, get_current_user

router = APIRouter(prefix="/privacy", tags=["Privacy & Compliance"])


# =============================================================================
# Request/Response Models
# =============================================================================

class DSARRequestCreate(BaseModel):
    request_type: str = Field(..., description="Type of DSAR request")
    email: EmailStr = Field(..., description="Email for verification")
    notes: Optional[str] = Field(None, max_length=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_type": "access",
                "email": "user@example.com",
                "notes": "Please include all my uploaded documents"
            }
        }


class DSARResponse(BaseModel):
    request_id: str
    status: str
    request_type: str
    requested_at: str
    deadline: str
    message: str


class ConsentUpdate(BaseModel):
    analytics: bool = False
    ai_processing: bool = False
    third_party: bool = False
    marketing: bool = False


class ConsentResponse(BaseModel):
    user_id: str
    consent: Dict[str, bool]
    timestamp: str
    policy_version: str


class PIIScanRequest(BaseModel):
    text: str = Field(..., max_length=50000)


class PIIScanResponse(BaseModel):
    has_pii: bool
    risk_level: str
    summary: str
    matches: List[Dict[str, Any]]
    scan_time_ms: float


class RetentionPolicyResponse(BaseModel):
    data_type: str
    retention_period: str
    legal_basis: str
    auto_delete: bool


# =============================================================================
# DSAR Endpoints
# =============================================================================

@router.post("/dsar/request", response_model=DSARResponse)
async def create_dsar_request(
    request_data: DSARRequestCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a Data Subject Access Request (DSAR)
    
    Supported request types:
    - access: Get a copy of your personal data (GDPR Art. 15)
    - rectification: Correct inaccurate data (GDPR Art. 16)
    - erasure: Delete your data (GDPR Art. 17)
    - portability: Export your data (GDPR Art. 20)
    - objection: Object to processing (GDPR Art. 21)
    """
    try:
        request_type = DSARType(request_data.request_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request type. Valid types: {[t.value for t in DSARType]}"
        )
    
    dsar = await dsar_manager.create_request(
        user_id=current_user["id"],
        user_email=request_data.email,
        request_type=request_type,
        notes=request_data.notes
    )
    
    return DSARResponse(
        request_id=dsar.id,
        status=dsar.status.value,
        request_type=dsar.request_type.value,
        requested_at=dsar.requested_at.isoformat() + "Z",
        deadline=dsar.deadline.isoformat() + "Z",
        message=f"Your request has been submitted. We will respond within 30 days. Reference ID: {dsar.id}"
    )


@router.get("/dsar/requests", response_model=List[DSARResponse])
async def get_my_dsar_requests(
    current_user: dict = Depends(get_current_user)
):
    """Get all DSAR requests for the current user"""
    requests = await dsar_manager.get_user_requests(current_user["id"])
    
    return [
        DSARResponse(
            request_id=r.id,
            status=r.status.value,
            request_type=r.request_type.value,
            requested_at=r.requested_at.isoformat() + "Z",
            deadline=r.deadline.isoformat() + "Z",
            message=f"Status: {r.status.value}"
        )
        for r in requests
    ]


@router.get("/dsar/request/{request_id}")
async def get_dsar_request(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get status of a specific DSAR request"""
    dsar = await dsar_manager.get_request(request_id)
    
    if not dsar:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if dsar.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "request_id": dsar.id,
        "status": dsar.status.value,
        "request_type": dsar.request_type.value,
        "requested_at": dsar.requested_at.isoformat() + "Z",
        "verified_at": dsar.verified_at.isoformat() + "Z" if dsar.verified_at else None,
        "completed_at": dsar.completed_at.isoformat() + "Z" if dsar.completed_at else None,
        "deadline": dsar.deadline.isoformat() + "Z",
        "result_url": dsar.result_url
    }


@router.post("/dsar/export")
async def export_my_data(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Export all your data (Data Portability - GDPR Art. 20)
    Returns a download link when ready.
    """
    dsar = await dsar_manager.create_request(
        user_id=current_user["id"],
        user_email=current_user.get("email", ""),
        request_type=DSARType.PORTABILITY,
        notes="Self-service data export"
    )
    
    # Process in background
    async def process_export():
        await dsar_manager.process_request(dsar.id)
    
    background_tasks.add_task(process_export)
    
    return {
        "message": "Your data export is being prepared. You will receive an email when ready.",
        "request_id": dsar.id
    }


@router.delete("/dsar/delete-my-data")
async def delete_my_data(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Request deletion of all your data (Right to Erasure - GDPR Art. 17)
    Some data may be retained for legal compliance.
    """
    dsar = await dsar_manager.create_request(
        user_id=current_user["id"],
        user_email=current_user.get("email", ""),
        request_type=DSARType.ERASURE,
        notes="Self-service data deletion request"
    )
    
    # Process in background
    async def process_deletion():
        await dsar_manager.process_request(dsar.id)
    
    background_tasks.add_task(process_deletion)
    
    return {
        "message": "Your deletion request has been submitted. We will process it within 30 days.",
        "request_id": dsar.id,
        "note": "Some data may be retained for legal compliance (audit logs, consent records)."
    }


# =============================================================================
# Consent Endpoints
# =============================================================================

@router.post("/consent", response_model=ConsentResponse)
async def update_consent(
    consent_data: ConsentUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Update consent preferences"""
    user_id = current_user["id"]
    ip_address = request.client.host if request.client else None
    
    consent_types = {
        "analytics": consent_data.analytics,
        "ai_processing": consent_data.ai_processing,
        "third_party": consent_data.third_party,
        "marketing": consent_data.marketing
    }
    
    for consent_type, consented in consent_types.items():
        await consent_manager.record_consent(
            user_id=user_id,
            consent_type=consent_type,
            consented=consented,
            ip_address=ip_address
        )
    
    return ConsentResponse(
        user_id=user_id[:8] + "...",  # Partial ID for privacy
        consent=consent_types,
        timestamp=datetime.utcnow().isoformat() + "Z",
        policy_version=consent_manager.POLICY_VERSION
    )


@router.get("/consent", response_model=ConsentResponse)
async def get_consent(
    current_user: dict = Depends(get_current_user)
):
    """Get current consent preferences"""
    user_id = current_user["id"]
    
    consent = {
        "analytics": await consent_manager.get_current_consent(user_id, "analytics") or False,
        "ai_processing": await consent_manager.get_current_consent(user_id, "ai_processing") or False,
        "third_party": await consent_manager.get_current_consent(user_id, "third_party") or False,
        "marketing": await consent_manager.get_current_consent(user_id, "marketing") or False,
    }
    
    return ConsentResponse(
        user_id=user_id[:8] + "...",
        consent=consent,
        timestamp=datetime.utcnow().isoformat() + "Z",
        policy_version=consent_manager.POLICY_VERSION
    )


@router.get("/consent/history")
async def get_consent_history(
    current_user: dict = Depends(get_current_user)
):
    """Get consent history for the current user"""
    history = await consent_manager.get_consent_history(current_user["id"])
    
    return [
        {
            "consent_type": r.consent_type,
            "consented": r.consented,
            "timestamp": r.timestamp.isoformat() + "Z",
            "policy_version": r.policy_version
        }
        for r in history
    ]


# =============================================================================
# PII Detection Endpoints
# =============================================================================

@router.post("/pii/scan", response_model=PIIScanResponse)
async def scan_text_for_pii(
    scan_request: PIIScanRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Scan text for PII before uploading
    Use this to check documents before processing
    """
    result = scan_for_pii(scan_request.text)
    
    return PIIScanResponse(
        has_pii=result.has_pii,
        risk_level=result.risk_level,
        summary=result.summary,
        matches=[
            {
                "type": m.pii_type.value,
                "masked_value": m.value,
                "confidence": m.confidence
            }
            for m in result.matches
        ],
        scan_time_ms=result.scan_time_ms
    )


@router.post("/pii/redact")
async def redact_pii_from_text(
    scan_request: PIIScanRequest,
    current_user: dict = Depends(get_current_user)
):
    """Redact all PII from text"""
    redacted = redact_pii(scan_request.text)
    
    return {
        "original_length": len(scan_request.text),
        "redacted_length": len(redacted),
        "redacted_text": redacted
    }


# =============================================================================
# Data Retention Endpoints
# =============================================================================

@router.get("/retention-policies", response_model=List[RetentionPolicyResponse])
async def get_retention_policies():
    """Get data retention policies"""
    return [
        RetentionPolicyResponse(
            data_type=data_type,
            retention_period=RetentionPolicy.get_retention_period(data_type),
            legal_basis=policy["legal_basis"],
            auto_delete=policy["auto_delete"]
        )
        for data_type, policy in RetentionPolicy.POLICIES.items()
    ]


# =============================================================================
# Audit Log Endpoints (Admin only)
# =============================================================================

@router.get("/audit-logs")
async def get_audit_logs(
    resource_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """
    Get audit logs (admin only)
    Logs are anonymized - user IDs are hashed
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Query logs
    logs = audit_logger.query(
        resource_type=resource_type,
        action=AuditAction(action) if action else None,
        limit=limit
    )
    
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp,
            "action": log.action.value,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "user_hash": log.user_id,  # Hashed, not real ID
            "success": log.success,
            "details": log.details
        }
        for log in logs
    ]


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def privacy_health():
    """Privacy module health check"""
    return {
        "status": "healthy",
        "module": "privacy",
        "gdpr_compliant": True,
        "ccpa_compliant": True,
        "policy_version": consent_manager.POLICY_VERSION,
        "dsar_deadline_days": dsar_manager.DEADLINE_DAYS
    }
