"""Configuration management utilities."""

import os
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """Configuration manager."""
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._secrets: set = set()
        
    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Database
        self._config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://localhost/rag_db')
        self._config['DB_POOL_SIZE'] = int(os.getenv('DB_POOL_SIZE', '10'))
        
        # Redis
        self._config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        # OpenRouter
        self._config['OPENROUTER_API_KEY'] = os.getenv('OPENROUTER_API_KEY', '')
        self._secrets.add('OPENROUTER_API_KEY')
        
        # Qdrant
        self._config['QDRANT_URL'] = os.getenv('QDRANT_URL', 'http://localhost:6333')
        self._config['QDRANT_API_KEY'] = os.getenv('QDRANT_API_KEY', '')
        if self._config['QDRANT_API_KEY']:
            self._secrets.add('QDRANT_API_KEY')
        
        # Service ports
        self._config['UPLOAD_PORT'] = int(os.getenv('UPLOAD_PORT', '8001'))
        self._config['QUERY_PORT'] = int(os.getenv('QUERY_PORT', '8002'))
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any, is_secret: bool = False) -> None:
        """Set configuration value."""
        self._config[key] = value
        if is_secret:
            self._secrets.add(key)
    
    def validate(self) -> bool:
        """
        Validate required configuration is present.
        
        Returns:
            True if valid
            
        Raises:
            ConfigError: If required config is missing
        """
        required = ['DATABASE_URL', 'REDIS_URL', 'OPENROUTER_API_KEY']
        
        missing = []
        for key in required:
            value = self._config.get(key)
            if not value:
                missing.append(key)
        
        if missing:
            raise ConfigError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
    
    def is_secret(self, key: str) -> bool:
        """Check if a config key is marked as secret."""
        return key in self._secrets
    
    def safe_repr(self) -> Dict[str, Any]:
        """Get safe representation with secrets masked."""
        result = {}
        for key, value in self._config.items():
            if key in self._secrets:
                result[key] = '***REDACTED***'
            else:
                result[key] = value
        return result
    
    def __repr__(self) -> str:
        """String representation (secrets masked)."""
        return f"Config({self.safe_repr()})"


# Global config instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
        _config_instance.load_from_env()
    return _config_instance


def validate_config(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate configuration.
    
    Args:
        config: Configuration dict to validate, or None to validate global config
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If validation fails
    """
    if config is None:
        # Use global config
        cfg = get_config()
        return cfg.validate()
    
    # Validate provided dict
    required = ["database_url", "redis_url"]
    missing = [key for key in required if key not in config or not config[key]]
    
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    return True


def get_safe_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get configuration with secrets masked.
    
    Args:
        config: Configuration dict to sanitize, or None to use global config
        
    Returns:
        Dict with secrets masked
    """
    if config is None:
        # Use global config
        cfg = get_config()
        return cfg.safe_repr()
    
    # Sanitize provided dict
    result = {}
    secret_keys = ['password', 'secret', 'key', 'token', 'api_key']
    
    for key, value in config.items():
        # Check if key indicates it's a secret
        if any(sk in key.lower() for sk in secret_keys):
            result[key] = "***REDACTED***"
        # Check if value contains sensitive patterns
        elif isinstance(value, str):
            # Mask passwords in URLs
            import re
            if re.search(r'://[^:]+:([^@]+)@', value):
                result[key] = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', value)
            elif any(sk in value.lower() for sk in ['sk-', 'secret', 'password']):
                result[key] = "***REDACTED***"
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result
