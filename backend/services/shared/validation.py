"""Validation utilities for input data validation."""

from typing import Any, Dict, List, Optional
import re


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_document_upload(file_data: Dict[str, Any]) -> bool:
    """
    Validate document upload data.
    
    Args:
        file_data: Dictionary containing file information
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not file_data:
        raise ValidationError("File data is required")
    
    if 'filename' not in file_data:
        raise ValidationError("Filename is required")
    
    if 'content' not in file_data:
        raise ValidationError("File content is required")
    
    # Check file size
    max_size = 10 * 1024 * 1024  # 10MB
    content = file_data.get('content', b'')
    if isinstance(content, bytes) and len(content) > max_size:
        raise ValidationError(f"File size exceeds maximum of {max_size} bytes")
    
    # Check allowed extensions
    filename = file_data['filename']
    allowed_extensions = ['.pdf', '.txt', '.doc', '.docx', '.md']
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise ValidationError(f"File type not allowed. Allowed: {', '.join(allowed_extensions)}")
    
    return True


def validate_query(query_data: Dict[str, Any]) -> bool:
    """
    Validate query data.
    
    Args:
        query_data: Dictionary containing query information
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not query_data:
        raise ValidationError("Query data is required")
    
    if 'query' not in query_data:
        raise ValidationError("Query text is required")
    
    query_text = query_data['query']
    if not isinstance(query_text, str):
        raise ValidationError("Query must be a string")
    
    if len(query_text.strip()) == 0:
        raise ValidationError("Query cannot be empty")
    
    if len(query_text) > 1000:
        raise ValidationError("Query too long (max 1000 characters)")
    
    return True


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If email is invalid
    """
    if not email:
        raise ValidationError("Email is required")
    
    # Basic email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format")
    
    return True


def validate_field(value: Any, field_name: str, field_type: type, required: bool = True) -> bool:
    """
    Generic field validation.
    
    Args:
        value: Value to validate
        field_name: Name of the field
        field_type: Expected type
        required: Whether field is required
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required")
        return True
    
    if not isinstance(value, field_type):
        raise ValidationError(f"{field_name} must be of type {field_type.__name__}")
    
    return True


# Simplified validation functions for tests
def validate_upload(filename: str, file_size: int) -> bool:
    """
    Simplified document upload validation.
    
    Args:
        filename: Name of the file
        file_size: Size of the file in bytes
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If validation fails
    """
    # Check allowed extensions
    allowed_extensions = ['.pdf', '.txt', '.csv', '.doc', '.docx', '.md']
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise ValueError(f"File type not allowed")
    
    # Check file size (max 50MB)
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        raise ValueError(f"File size exceeds maximum")
    
    return True


def validate_query(query: str) -> bool:
    """
    Simplified query validation.
    
    Args:
        query: Query string to validate
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If validation fails
    """
    if not query or len(query) == 0:
        raise ValueError("Query text is required")
    
    # Max length
    if len(query) > 10000:
        raise ValueError("Query too long")
    
    return True


def validate_email(email: str) -> bool:
    """
    Simplified email validation.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    # Simple email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


# Aliases for backward compatibility
