"""
Database Security Utilities
SQL injection prevention, parameterized queries, and secure data handling
"""
import re
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# SQL Injection Prevention
# =============================================================================

# Patterns that indicate potential SQL injection
SQL_INJECTION_PATTERNS = [
    # Union-based injection
    r"\bUNION\b.*\bSELECT\b",
    r"\bUNION\b.*\bALL\b",
    
    # Comment injection
    r"--",
    r"/\*",
    r"\*/",
    r"#(?![\w])",  # # not followed by word char
    
    # Boolean-based injection
    r"\bOR\b\s+[\d'\"]+\s*=\s*[\d'\"]+",
    r"\bAND\b\s+[\d'\"]+\s*=\s*[\d'\"]+",
    r"'\s*OR\s*'1'\s*=\s*'1",
    r"'\s*OR\s*1\s*=\s*1",
    
    # Stacked queries
    r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC)",
    
    # Command execution
    r"\bEXEC\b",
    r"\bXP_",
    r"\bSP_",
    
    # Schema manipulation
    r"\bDROP\b.*\b(TABLE|DATABASE|INDEX|VIEW)",
    r"\bALTER\b.*\bTABLE\b",
    r"\bCREATE\b.*\b(TABLE|DATABASE|INDEX|VIEW)",
    r"\bTRUNCATE\b",
    
    # Information disclosure
    r"\bINFORMATION_SCHEMA\b",
    r"\bSYS\.",
    r"\bPG_",
    
    # Time-based injection
    r"\bSLEEP\s*\(",
    r"\bWAITFOR\b",
    r"\bBENCHMARK\s*\(",
    r"\bPG_SLEEP\s*\(",
]

# Compile patterns for performance
_sql_patterns = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]


def check_sql_injection(value: str) -> bool:
    """
    Check if a string contains potential SQL injection patterns.
    Returns True if suspicious patterns found.
    """
    if not value:
        return False
    
    for pattern in _sql_patterns:
        if pattern.search(value):
            logger.security(f"SQL injection pattern detected: {pattern.pattern[:30]}")
            return True
    
    return False


def sanitize_identifier(identifier: str) -> str:
    """
    Sanitize a database identifier (table name, column name).
    Only allows alphanumeric and underscore characters.
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")
    
    # Only allow alphanumeric and underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    # Must start with letter or underscore
    if not re.match(r'^[a-zA-Z_]', sanitized):
        sanitized = '_' + sanitized
    
    # Limit length
    sanitized = sanitized[:63]  # PostgreSQL identifier limit
    
    if sanitized != identifier:
        logger.warning(f"Identifier sanitized: {identifier[:20]} -> {sanitized[:20]}")
    
    return sanitized


def sanitize_value(value: Any, max_length: int = 10000) -> Any:
    """
    Sanitize a value for database insertion.
    """
    if value is None:
        return None
    
    if isinstance(value, str):
        # Check for SQL injection
        if check_sql_injection(value):
            logger.security("SQL injection attempt blocked")
            raise ValueError("Invalid input detected")
        
        # Trim and limit length
        return value.strip()[:max_length]
    
    if isinstance(value, (int, float, bool)):
        return value
    
    if isinstance(value, datetime):
        return value
    
    if isinstance(value, (list, dict)):
        # For JSONB columns - will be serialized by database driver
        return value
    
    # Convert unknown types to string
    return str(value)[:max_length]


# =============================================================================
# Parameterized Query Builder
# =============================================================================

class QueryBuilder:
    """
    Safe SQL query builder with automatic parameterization.
    NEVER use string formatting for user input!
    """
    
    def __init__(self, table: str):
        self.table = sanitize_identifier(table)
        self._columns: List[str] = []
        self._values: List[Any] = []
        self._where_clauses: List[str] = []
        self._where_values: List[Any] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """Add SELECT columns"""
        self._columns = [sanitize_identifier(c) for c in columns] if columns else ['*']
        return self
    
    def where(self, column: str, operator: str, value: Any) -> 'QueryBuilder':
        """Add WHERE clause with parameterized value"""
        safe_column = sanitize_identifier(column)
        
        # Only allow safe operators
        safe_operators = ['=', '!=', '<', '>', '<=', '>=', 'LIKE', 'ILIKE', 'IN', 'IS NULL', 'IS NOT NULL']
        if operator.upper() not in safe_operators:
            raise ValueError(f"Invalid operator: {operator}")
        
        if operator.upper() in ('IS NULL', 'IS NOT NULL'):
            self._where_clauses.append(f"{safe_column} {operator}")
        else:
            self._where_clauses.append(f"{safe_column} {operator} %s")
            self._where_values.append(sanitize_value(value))
        
        return self
    
    def order_by(self, column: str, direction: str = 'ASC') -> 'QueryBuilder':
        """Add ORDER BY clause"""
        safe_column = sanitize_identifier(column)
        safe_direction = 'DESC' if direction.upper() == 'DESC' else 'ASC'
        self._order_by = f"{safe_column} {safe_direction}"
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """Add LIMIT clause"""
        self._limit = max(1, min(count, 1000))  # Limit between 1 and 1000
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """Add OFFSET clause"""
        self._offset = max(0, count)
        return self
    
    def build_select(self) -> Tuple[str, List[Any]]:
        """Build SELECT query"""
        columns = ', '.join(self._columns) if self._columns else '*'
        query = f"SELECT {columns} FROM {self.table}"
        
        if self._where_clauses:
            query += " WHERE " + " AND ".join(self._where_clauses)
        
        if self._order_by:
            query += f" ORDER BY {self._order_by}"
        
        if self._limit:
            query += f" LIMIT {self._limit}"
        
        if self._offset:
            query += f" OFFSET {self._offset}"
        
        return query, self._where_values
    
    def build_insert(self, data: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Build INSERT query"""
        columns = []
        placeholders = []
        values = []
        
        for key, value in data.items():
            columns.append(sanitize_identifier(key))
            placeholders.append('%s')
            values.append(sanitize_value(value))
        
        query = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        return query, values
    
    def build_update(self, data: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Build UPDATE query"""
        if not self._where_clauses:
            raise ValueError("UPDATE without WHERE clause is not allowed")
        
        set_clauses = []
        values = []
        
        for key, value in data.items():
            set_clauses.append(f"{sanitize_identifier(key)} = %s")
            values.append(sanitize_value(value))
        
        query = f"UPDATE {self.table} SET {', '.join(set_clauses)}"
        query += " WHERE " + " AND ".join(self._where_clauses)
        
        return query, values + self._where_values
    
    def build_delete(self) -> Tuple[str, List[Any]]:
        """Build DELETE query"""
        if not self._where_clauses:
            raise ValueError("DELETE without WHERE clause is not allowed")
        
        query = f"DELETE FROM {self.table}"
        query += " WHERE " + " AND ".join(self._where_clauses)
        
        return query, self._where_values


# =============================================================================
# Password Security
# =============================================================================

import bcrypt
import secrets


class PasswordSecurity:
    """Secure password hashing and verification using bcrypt"""
    
    # bcrypt work factor (12 is recommended for 2024)
    BCRYPT_ROUNDS = 12
    
    # Minimum password requirements
    MIN_PASSWORD_LENGTH = 8
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password meets security requirements.
        Returns (is_valid, error_message)
        """
        if len(password) < PasswordSecurity.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {PasswordSecurity.MIN_PASSWORD_LENGTH} characters"
        
        # Check for common patterns
        common_patterns = ['password', '123456', 'qwerty', 'admin', 'letmein']
        if password.lower() in common_patterns:
            return False, "Password is too common"
        
        # Require mix of character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and numbers"
        
        return True, ""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password securely using bcrypt.
        Pre-hashes with SHA-256 to handle passwords > 72 bytes.
        """
        # Validate password strength
        is_valid, error = PasswordSecurity.validate_password_strength(password)
        if not is_valid:
            raise ValueError(error)
        
        # Pre-hash with SHA-256 (bcrypt has 72 byte limit)
        password_bytes = hashlib.sha256(password.encode()).digest()
        
        # Hash with bcrypt
        salt = bcrypt.gensalt(rounds=PasswordSecurity.BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        try:
            password_bytes = hashlib.sha256(password.encode()).digest()
            return bcrypt.checkpw(password_bytes, hashed.encode('utf-8'))
        except Exception:
            return False
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key() -> Tuple[str, str]:
        """
        Generate an API key and its hash.
        Returns (raw_key, hashed_key)
        """
        prefix = 'dg_'
        raw_key = prefix + secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, hashed_key


# =============================================================================
# Data Encryption
# =============================================================================

from cryptography.fernet import Fernet
import base64


class DataEncryption:
    """
    Encrypt sensitive data before storage.
    Uses Fernet (AES-128-CBC with HMAC).
    """
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize with encryption key.
        Key should be 32 URL-safe base64-encoded bytes.
        """
        if key:
            self._key = key.encode()
        else:
            self._key = os.environ.get('ENCRYPTION_KEY', '').encode()
        
        if not self._key:
            logger.warning("No encryption key configured. Data encryption disabled.")
            self._fernet = None
        else:
            try:
                self._fernet = Fernet(self._key)
            except Exception as e:
                logger.error(f"Invalid encryption key: {e}")
                self._fernet = None
    
    def encrypt(self, data: str) -> Optional[str]:
        """Encrypt a string"""
        if not self._fernet:
            return data  # Return unencrypted if no key
        
        try:
            encrypted = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None
    
    def decrypt(self, encrypted_data: str) -> Optional[str]:
        """Decrypt a string"""
        if not self._fernet:
            return encrypted_data  # Return as-is if no key
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key"""
        return Fernet.generate_key().decode()


# Add missing import
import os

# Secure logging extension
class SecureLoggingFilter(logging.Filter):
    """Filter that adds a 'security' log method"""
    
    def filter(self, record):
        return True

# Add security method to logger
def _security_log(self, msg, *args, **kwargs):
    """Log a security event"""
    self.warning(f"🔒 SECURITY: {msg}", *args, **kwargs)

logging.Logger.security = _security_log
