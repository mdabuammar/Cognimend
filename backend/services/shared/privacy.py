"""
Privacy & GDPR/CCPA Compliance Module
Implements Data Subject Access Requests (DSAR), PII detection, and audit logging
"""
import os
import re
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from functools import wraps

logger = logging.getLogger(__name__)


# =============================================================================
# PII Detection
# =============================================================================

class PIIType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    NAME = "name"
    ADDRESS = "address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"


@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str  # Masked value
    start: int
    end: int
    confidence: float


@dataclass
class PIIScanResult:
    has_pii: bool
    matches: List[PIIMatch]
    risk_level: str  # none, low, medium, high
    summary: str
    scan_time_ms: float


# PII Detection Patterns
PII_PATTERNS = [
    (PIIType.EMAIL, r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 0.95),
    (PIIType.PHONE, r'\b(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', 0.85),
    (PIIType.SSN, r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', 0.90),
    (PIIType.CREDIT_CARD, r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 0.90),
    (PIIType.IP_ADDRESS, r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 0.80),
    (PIIType.DATE_OF_BIRTH, r'\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b', 0.70),
    (PIIType.PASSPORT, r'\b[A-Z]{1,2}\d{6,9}\b', 0.60),
]

# Compile patterns
_compiled_patterns = [(t, re.compile(p, re.IGNORECASE), c) for t, p, c in PII_PATTERNS]


def mask_pii_value(value: str, pii_type: PIIType) -> str:
    """Mask PII for safe display/logging"""
    if pii_type == PIIType.EMAIL:
        parts = value.split('@')
        if len(parts) == 2:
            return f"{parts[0][0]}***@{parts[1]}"
        return "***@***"
    elif pii_type == PIIType.PHONE:
        return re.sub(r'\d(?=\d{4})', '*', value)
    elif pii_type == PIIType.SSN:
        return "***-**-" + value[-4:]
    elif pii_type == PIIType.CREDIT_CARD:
        return "**** **** **** " + value[-4:]
    elif pii_type == PIIType.IP_ADDRESS:
        parts = value.split('.')
        return f"***.***{parts[2]}.{parts[3]}" if len(parts) == 4 else "***"
    else:
        if len(value) <= 4:
            return "****"
        return value[:2] + "*" * (len(value) - 4) + value[-2:]


def scan_for_pii(text: str) -> PIIScanResult:
    """Scan text for PII patterns"""
    import time
    start_time = time.time()
    
    matches: List[PIIMatch] = []
    
    for pii_type, pattern, confidence in _compiled_patterns:
        for match in pattern.finditer(text):
            matches.append(PIIMatch(
                pii_type=pii_type,
                value=mask_pii_value(match.group(), pii_type),
                start=match.start(),
                end=match.end(),
                confidence=confidence
            ))
    
    # Determine risk level
    if not matches:
        risk_level = "none"
    elif any(m.pii_type in [PIIType.SSN, PIIType.CREDIT_CARD, PIIType.PASSPORT] for m in matches):
        risk_level = "high"
    elif len(matches) > 5:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    # Generate summary
    if not matches:
        summary = "No PII detected"
    else:
        type_counts = {}
        for m in matches:
            type_counts[m.pii_type.value] = type_counts.get(m.pii_type.value, 0) + 1
        summary = "Found: " + ", ".join(f"{c} {t}" for t, c in type_counts.items())
    
    scan_time = (time.time() - start_time) * 1000
    
    return PIIScanResult(
        has_pii=len(matches) > 0,
        matches=matches,
        risk_level=risk_level,
        summary=summary,
        scan_time_ms=round(scan_time, 2)
    )


def redact_pii(text: str) -> str:
    """Redact all PII from text"""
    result = text
    for pii_type, pattern, _ in _compiled_patterns:
        result = pattern.sub(f"[{pii_type.value.upper()}_REDACTED]", result)
    return result


# =============================================================================
# Audit Logging
# =============================================================================

class AuditAction(str, Enum):
    # Data access
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_VIEW = "data_view"
    
    # Data modification
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    
    # DSAR
    DSAR_REQUEST = "dsar_request"
    DSAR_COMPLETED = "dsar_completed"
    
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    
    # Consent
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    
    # Admin
    ADMIN_ACTION = "admin_action"
    CONFIG_CHANGE = "config_change"


@dataclass
class AuditLogEntry:
    id: str
    timestamp: str
    action: AuditAction
    user_id: Optional[str]  # Hashed for privacy
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]  # Masked
    user_agent: Optional[str]
    details: Dict[str, Any]
    success: bool


class AuditLogger:
    """
    GDPR-compliant audit logger
    Logs all data access and modifications without storing PII
    """
    
    def __init__(self, storage_backend=None):
        self.storage = storage_backend  # Database, file, or external service
        self._buffer: List[AuditLogEntry] = []
        self._buffer_size = 100
    
    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy"""
        salt = os.environ.get('AUDIT_SALT', 'default-audit-salt')
        return hashlib.sha256(f"{salt}{user_id}".encode()).hexdigest()[:16]
    
    def _mask_ip(self, ip: str) -> str:
        """Mask IP address for privacy"""
        if not ip:
            return None
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return "***"
    
    def _generate_id(self) -> str:
        """Generate unique audit log ID"""
        import uuid
        return f"audit_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"
    
    def log(
        self,
        action: AuditAction,
        resource_type: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> AuditLogEntry:
        """Log an audit event"""
        
        entry = AuditLogEntry(
            id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            action=action,
            user_id=self._hash_user_id(user_id) if user_id else None,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=self._mask_ip(ip_address) if ip_address else None,
            user_agent=user_agent[:100] if user_agent else None,  # Truncate
            details=self._sanitize_details(details or {}),
            success=success
        )
        
        self._buffer.append(entry)
        
        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            self._flush()
        
        # Also log to standard logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(log_level, f"AUDIT: {action.value} on {resource_type}", extra={
            "audit_id": entry.id,
            "action": action.value,
            "resource_type": resource_type,
            "success": success
        })
        
        return entry
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove any PII from details"""
        sanitized = {}
        sensitive_keys = ['password', 'token', 'secret', 'key', 'email', 'phone', 'ssn']
        
        for key, value in details.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _flush(self):
        """Flush buffer to storage"""
        if not self._buffer:
            return
        
        if self.storage:
            try:
                # Store to database/file
                pass
            except Exception as e:
                logger.error(f"Failed to flush audit logs: {e}")
        
        self._buffer = []
    
    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Query audit logs"""
        # Implementation depends on storage backend
        return []


# Global audit logger instance
audit_logger = AuditLogger()


def audit_log(action: AuditAction, resource_type: str):
    """Decorator for automatic audit logging"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request info if available
            request = kwargs.get('request')
            user_id = None
            ip_address = None
            
            if request:
                user_id = getattr(request.state, 'user_id', None)
                ip_address = request.client.host if request.client else None
            
            try:
                result = await func(*args, **kwargs)
                audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    user_id=user_id,
                    ip_address=ip_address,
                    success=True
                )
                return result
            except Exception as e:
                audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    user_id=user_id,
                    ip_address=ip_address,
                    success=False,
                    details={"error": str(e)[:200]}
                )
                raise
        
        return wrapper
    return decorator


# =============================================================================
# DSAR (Data Subject Access Request)
# =============================================================================

class DSARType(str, Enum):
    ACCESS = "access"           # GDPR Art. 15
    RECTIFICATION = "rectification"  # GDPR Art. 16
    ERASURE = "erasure"         # GDPR Art. 17
    RESTRICTION = "restriction"  # GDPR Art. 18
    PORTABILITY = "portability"  # GDPR Art. 20
    OBJECTION = "objection"     # GDPR Art. 21
    CCPA_DELETE = "ccpa_delete"
    CCPA_OPTOUT = "ccpa_optout"
    CCPA_KNOW = "ccpa_know"


class DSARStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"  # Identity verified
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class DSARRequest:
    id: str
    user_id: str
    user_email: str  # For verification
    request_type: DSARType
    status: DSARStatus
    requested_at: datetime
    verified_at: Optional[datetime]
    completed_at: Optional[datetime]
    deadline: datetime  # GDPR: 30 days
    notes: Optional[str]
    result_url: Optional[str]  # Download URL for exports


class DSARManager:
    """
    Manages Data Subject Access Requests
    GDPR requires response within 30 days
    """
    
    DEADLINE_DAYS = 30
    
    def __init__(self, db=None):
        self.db = db
        self._requests: Dict[str, DSARRequest] = {}
    
    def _generate_id(self) -> str:
        import uuid
        return f"DSAR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    async def create_request(
        self,
        user_id: str,
        user_email: str,
        request_type: DSARType,
        notes: Optional[str] = None
    ) -> DSARRequest:
        """Create a new DSAR request"""
        
        now = datetime.utcnow()
        request = DSARRequest(
            id=self._generate_id(),
            user_id=user_id,
            user_email=user_email,
            request_type=request_type,
            status=DSARStatus.PENDING,
            requested_at=now,
            verified_at=None,
            completed_at=None,
            deadline=now + timedelta(days=self.DEADLINE_DAYS),
            notes=notes,
            result_url=None
        )
        
        self._requests[request.id] = request
        
        # Audit log
        audit_logger.log(
            action=AuditAction.DSAR_REQUEST,
            resource_type="dsar",
            user_id=user_id,
            resource_id=request.id,
            details={"request_type": request_type.value}
        )
        
        # TODO: Send notification to admin
        # TODO: Send confirmation email to user
        
        return request
    
    async def verify_identity(self, request_id: str) -> bool:
        """Mark request as identity verified"""
        request = self._requests.get(request_id)
        if not request:
            return False
        
        request.status = DSARStatus.VERIFIED
        request.verified_at = datetime.utcnow()
        return True
    
    async def process_request(self, request_id: str) -> Dict[str, Any]:
        """Process a DSAR request"""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")
        
        request.status = DSARStatus.IN_PROGRESS
        
        if request.request_type == DSARType.ACCESS:
            return await self._handle_access(request)
        elif request.request_type == DSARType.ERASURE:
            return await self._handle_erasure(request)
        elif request.request_type == DSARType.PORTABILITY:
            return await self._handle_portability(request)
        elif request.request_type == DSARType.RECTIFICATION:
            return await self._handle_rectification(request)
        else:
            raise ValueError(f"Unsupported request type: {request.request_type}")
    
    async def _handle_access(self, request: DSARRequest) -> Dict[str, Any]:
        """Handle Right of Access request (GDPR Art. 15)"""
        user_data = await self._collect_user_data(request.user_id)
        
        request.status = DSARStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        
        audit_logger.log(
            action=AuditAction.DSAR_COMPLETED,
            resource_type="dsar",
            user_id=request.user_id,
            resource_id=request.id,
            details={"request_type": "access"}
        )
        
        return user_data
    
    async def _handle_erasure(self, request: DSARRequest) -> Dict[str, Any]:
        """Handle Right to Erasure request (GDPR Art. 17)"""
        result = {
            "deleted_categories": [],
            "retained_categories": [],
            "errors": []
        }
        
        # Categories that can be deleted
        deletable = ["documents", "queries", "feedback", "analytics"]
        
        # Categories retained for legal reasons
        retained = ["audit_logs", "consent_records", "billing_records"]
        
        for category in deletable:
            try:
                await self._delete_category(request.user_id, category)
                result["deleted_categories"].append(category)
            except Exception as e:
                result["errors"].append(f"Failed to delete {category}: {str(e)}")
        
        result["retained_categories"] = retained
        
        request.status = DSARStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        
        audit_logger.log(
            action=AuditAction.DSAR_COMPLETED,
            resource_type="dsar",
            user_id=request.user_id,
            resource_id=request.id,
            details={"request_type": "erasure", "result": result}
        )
        
        return result
    
    async def _handle_portability(self, request: DSARRequest) -> Dict[str, Any]:
        """Handle Data Portability request (GDPR Art. 20)"""
        user_data = await self._collect_user_data(request.user_id)
        
        # Format as machine-readable JSON
        export_data = {
            "export_format": "GDPR-Article-20-Portable",
            "export_version": "1.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "data_controller": "DriftGuard",
            "data": user_data
        }
        
        # TODO: Generate download URL
        # request.result_url = await self._create_download(export_data)
        
        request.status = DSARStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        
        return export_data
    
    async def _handle_rectification(self, request: DSARRequest) -> Dict[str, Any]:
        """Handle Rectification request (GDPR Art. 16)"""
        # This typically requires manual review
        return {
            "status": "pending_review",
            "message": "Your rectification request has been received and will be reviewed within 30 days."
        }
    
    async def _collect_user_data(self, user_id: str) -> Dict[str, Any]:
        """Collect all user data for export"""
        # TODO: Implement actual data collection from database
        return {
            "account": {
                "user_id": user_id,
                "created_at": None,
                "last_login": None
            },
            "documents": [],
            "queries": [],
            "feedback": [],
            "consent_history": [],
            "processing_activities": []
        }
    
    async def _delete_category(self, user_id: str, category: str):
        """Delete a category of user data"""
        # TODO: Implement actual deletion
        logger.info(f"Deleting {category} for user {user_id[:8]}...")
    
    async def get_request(self, request_id: str) -> Optional[DSARRequest]:
        """Get a DSAR request by ID"""
        return self._requests.get(request_id)
    
    async def get_user_requests(self, user_id: str) -> List[DSARRequest]:
        """Get all DSAR requests for a user"""
        return [r for r in self._requests.values() if r.user_id == user_id]
    
    async def check_deadlines(self) -> List[DSARRequest]:
        """Check for requests approaching deadline"""
        now = datetime.utcnow()
        warning_threshold = timedelta(days=5)
        
        approaching = []
        for request in self._requests.values():
            if request.status in [DSARStatus.PENDING, DSARStatus.VERIFIED, DSARStatus.IN_PROGRESS]:
                if request.deadline - now < warning_threshold:
                    approaching.append(request)
        
        return approaching


# Global DSAR manager
dsar_manager = DSARManager()


# =============================================================================
# Data Retention
# =============================================================================

class RetentionPolicy:
    """Data retention policies per data type"""
    
    POLICIES = {
        "user_account": {"days": 365 * 3, "legal_basis": "contract", "auto_delete": False},
        "documents": {"days": 365 * 2, "legal_basis": "contract", "auto_delete": True},
        "queries": {"days": 90, "legal_basis": "legitimate_interest", "auto_delete": True},
        "feedback": {"days": 365, "legal_basis": "consent", "auto_delete": True},
        "analytics": {"days": 365 * 2, "legal_basis": "legitimate_interest", "auto_delete": True},
        "audit_logs": {"days": 365 * 7, "legal_basis": "legal_obligation", "auto_delete": False},
        "consent_records": {"days": 365 * 7, "legal_basis": "legal_obligation", "auto_delete": False},
    }
    
    @classmethod
    def get_expiry_date(cls, data_type: str, created_at: datetime) -> Optional[datetime]:
        """Calculate expiry date for data"""
        policy = cls.POLICIES.get(data_type)
        if not policy:
            return None
        return created_at + timedelta(days=policy["days"])
    
    @classmethod
    def is_expired(cls, data_type: str, created_at: datetime) -> bool:
        """Check if data has expired"""
        expiry = cls.get_expiry_date(data_type, created_at)
        return expiry and datetime.utcnow() > expiry
    
    @classmethod
    def get_retention_period(cls, data_type: str) -> str:
        """Get human-readable retention period"""
        policy = cls.POLICIES.get(data_type)
        if not policy:
            return "Unknown"
        
        days = policy["days"]
        if days >= 365:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''}"
        elif days >= 30:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        return f"{days} days"


# =============================================================================
# Consent Management
# =============================================================================

@dataclass
class ConsentRecord:
    id: str
    user_id: str
    consent_type: str  # analytics, ai_processing, third_party, marketing
    consented: bool
    timestamp: datetime
    ip_address: Optional[str]
    policy_version: str


class ConsentManager:
    """Manages user consent records for GDPR compliance"""
    
    POLICY_VERSION = "1.0.0"
    
    def __init__(self, db=None):
        self.db = db
        self._records: Dict[str, List[ConsentRecord]] = {}
    
    def _generate_id(self) -> str:
        import uuid
        return f"consent_{uuid.uuid4().hex[:12]}"
    
    async def record_consent(
        self,
        user_id: str,
        consent_type: str,
        consented: bool,
        ip_address: Optional[str] = None
    ) -> ConsentRecord:
        """Record a consent decision"""
        
        record = ConsentRecord(
            id=self._generate_id(),
            user_id=user_id,
            consent_type=consent_type,
            consented=consented,
            timestamp=datetime.utcnow(),
            ip_address=ip_address[:20] if ip_address else None,  # Truncate IP
            policy_version=self.POLICY_VERSION
        )
        
        if user_id not in self._records:
            self._records[user_id] = []
        self._records[user_id].append(record)
        
        # Audit log
        audit_logger.log(
            action=AuditAction.CONSENT_GIVEN if consented else AuditAction.CONSENT_WITHDRAWN,
            resource_type="consent",
            user_id=user_id,
            details={"consent_type": consent_type, "consented": consented}
        )
        
        return record
    
    async def get_current_consent(self, user_id: str, consent_type: str) -> Optional[bool]:
        """Get current consent status for a user"""
        records = self._records.get(user_id, [])
        for record in reversed(records):
            if record.consent_type == consent_type:
                return record.consented
        return None
    
    async def get_consent_history(self, user_id: str) -> List[ConsentRecord]:
        """Get full consent history for a user"""
        return self._records.get(user_id, [])
    
    async def has_required_consent(self, user_id: str, required_types: List[str]) -> bool:
        """Check if user has given all required consents"""
        for consent_type in required_types:
            if not await self.get_current_consent(user_id, consent_type):
                return False
        return True


# Global consent manager
consent_manager = ConsentManager()
