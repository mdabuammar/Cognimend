"""
Shared utilities for all microservices
Production service modules

All imports are wrapped in try/except to handle missing dependencies gracefully.
"""
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Core modules (with graceful fallbacks)
# ============================================================

# Database
try:
    from .database import (
        db_pool, 
        get_db, 
        DatabasePool,
        async_db_pool,
        get_async_db,
        AsyncDatabasePool,
        PoolConfig,
    )
except ImportError as e:
    logger.warning(f"Database module not available: {e}")
    db_pool = None
    get_db = None
    DatabasePool = None
    async_db_pool = None
    get_async_db = None
    AsyncDatabasePool = None
    PoolConfig = None

# Query Optimizer
try:
    from .query_optimizer import (
        QueryCache,
        QueryAnalyzer,
        QueryStats,
        get_query_cache,
        get_query_analyzer,
        cached_query,
        timed_query,
    )
except ImportError as e:
    logger.debug(f"Query optimizer module not available: {e}")
    QueryCache = None
    QueryAnalyzer = None
    QueryStats = None
    get_query_cache = None
    get_query_analyzer = None
    cached_query = None
    timed_query = None

# Cache
try:
    from .cache import cache, cache_get_or_compute, CacheManager
except ImportError as e:
    logger.warning(f"Cache module not available: {e}")
    cache = None
    cache_get_or_compute = None
    CacheManager = None

# Resilience
try:
    from .resilience import (
        CircuitBreaker, 
        CircuitBreakerError,
        CircuitState,
        retry_async,
        retry_sync,
        async_timeout
    )
except ImportError as e:
    logger.warning(f"Resilience module not available: {e}")
    CircuitBreaker = None
    CircuitBreakerError = None
    CircuitState = None
    retry_async = None
    retry_sync = None
    async_timeout = None

# Tracing (optional - requires opentelemetry)
try:
    from .tracing import init_tracing, get_tracer, create_span_attributes
except ImportError as e:
    logger.debug(f"Tracing module not available (opentelemetry not installed): {e}")
    init_tracing = lambda x: None
    get_tracer = lambda: None
    create_span_attributes = lambda **kwargs: {}

# Correlation IDs for distributed tracing
try:
    from .correlation import (
        CorrelationIdMiddleware,
        CorrelationIdLogFilter,
        CorrelationJsonFormatter,
        CorrelatedHttpClient,
        get_correlation_id,
        get_request_id,
        get_span_id,
        propagate_correlation_headers,
        setup_correlation_logging,
        setup_json_logging,
        with_correlation,
    )
except ImportError as e:
    logger.debug(f"Correlation module not available: {e}")
    CorrelationIdMiddleware = None
    CorrelationIdLogFilter = None
    CorrelationJsonFormatter = None
    CorrelatedHttpClient = None
    get_correlation_id = lambda: None
    get_request_id = lambda: None
    get_span_id = lambda: None
    propagate_correlation_headers = lambda h: h
    setup_correlation_logging = lambda: None
    setup_json_logging = lambda: None
    with_correlation = lambda f: f

# Utilities
try:
    from .utils import (
        DatabaseManager,
        HealthCheckBuilder,
        ServiceLogger,
        setup_logging,
        datetime_to_iso,
        format_query_results,
        validate_pagination,
        sanitize_string,
        get_db_fallback
    )
except ImportError as e:
    logger.warning(f"Utils module not available: {e}")
    DatabaseManager = None
    HealthCheckBuilder = None
    ServiceLogger = None
    setup_logging = None
    datetime_to_iso = None
    format_query_results = None
    validate_pagination = None
    sanitize_string = None
    get_db_fallback = None

# Actions
try:
    from .actions import (
        ActionRegistry,
        ActionResult,
        BaseAction,
        action_registry
    )
except ImportError as e:
    logger.warning(f"Actions module not available: {e}")
    ActionRegistry = None
    ActionResult = None
    BaseAction = None
    action_registry = None

# Exceptions
try:
    from .exceptions import (
        ServiceException,
        DatabaseError,
        DocumentError,
        QueryError,
        EmbeddingError,
        SearchError,
        ExternalServiceError,
        VectorStoreError
    )
except ImportError as e:
    logger.debug(f"Exceptions module not available: {e}")
    ServiceException = Exception
    DatabaseError = Exception
    DocumentError = Exception
    QueryError = Exception
    EmbeddingError = Exception
    SearchError = Exception
    ExternalServiceError = Exception
    VectorStoreError = Exception

# ============================================================
# Health check module
# ============================================================

try:
    from .health import (
        HealthChecker,
        HealthStatus,
        ProbeType,
        ComponentHealth,
        HealthCheckResult,
        create_database_check,
        create_redis_check,
        create_qdrant_check,
        create_openrouter_check,
        create_circuit_breaker_check,
        setup_health_routes,
    )
except ImportError as e:
    logger.debug(f"Health module not available: {e}")
    HealthChecker = None
    HealthStatus = None
    ProbeType = None
    ComponentHealth = None
    HealthCheckResult = None
    create_database_check = None
    create_redis_check = None
    create_qdrant_check = None
    create_openrouter_check = None
    create_circuit_breaker_check = None
    setup_health_routes = None

# ============================================================
# Graceful shutdown module
# ============================================================

try:
    from .shutdown import (
        GracefulShutdownManager,
        ShutdownConfig,
        ShutdownPhase,
        ShutdownState,
        ShutdownMiddleware,
        create_database_pool_hook,
        create_redis_hook,
        create_qdrant_hook,
        create_flush_metrics_hook,
        create_lifespan_manager,
        add_shutdown_middleware,
    )
except ImportError as e:
    logger.debug(f"Shutdown module not available: {e}")
    GracefulShutdownManager = None
    ShutdownConfig = None
    ShutdownPhase = None
    ShutdownState = None
    ShutdownMiddleware = None
    create_database_pool_hook = None
    create_redis_hook = None
    create_qdrant_hook = None
    create_flush_metrics_hook = None
    create_lifespan_manager = None
    add_shutdown_middleware = None

# ============================================================
# Security module (always available - no external deps)
# ============================================================

from .security import (
    SecurityConfig,
    SecureLogger,
    get_secure_logger,
    verify_api_key,
    require_api_key,
    RateLimiter,
    rate_limiter,
    check_rate_limit,
    sanitize_string as secure_sanitize_string,
    sanitize_filename,
    validate_file_extension,
    validate_mime_type,
    check_sql_injection,
    escape_html,
    redact_sensitive,
    SecureQueryInput,
    SecureUploadInput,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    create_error_response,
    global_exception_handler,
    setup_security
)

# ============================================================
# Redis client (optional - requires redis)
# ============================================================

try:
    from .redis_client import (
        RedisConfig,
        SecureRedisClient,
        redis_client
    )
except ImportError as e:
    logger.debug(f"Redis client not available: {e}")
    RedisConfig = None
    SecureRedisClient = None
    redis_client = None

# ============================================================
# Database security utilities
# ============================================================

try:
    from .db_security import (
        check_sql_injection as db_check_sql_injection,
        sanitize_identifier,
        sanitize_value,
        QueryBuilder,
        PasswordSecurity,
        DataEncryption
    )
except ImportError as e:
    logger.debug(f"DB security module not available: {e}")
    db_check_sql_injection = None
    sanitize_identifier = None
    sanitize_value = None
    QueryBuilder = None
    PasswordSecurity = None
    DataEncryption = None

# ============================================================
# Privacy & GDPR/CCPA compliance
# ============================================================

try:
    from .privacy import (
        # PII Detection
        PIIType,
        PIIMatch,
        PIIScanResult,
        scan_for_pii,
        redact_pii,
        # Audit Logging
        AuditAction,
        AuditLogEntry,
        AuditLogger,
        audit_logger,
        audit_log,
        # DSAR
        DSARType,
        DSARStatus,
        DSARRequest,
        DSARManager,
        dsar_manager,
        # Consent
        ConsentRecord,
        ConsentManager,
        consent_manager,
        # Retention
        RetentionPolicy,
    )
except ImportError as e:
    logger.debug(f"Privacy module not available: {e}")
    PIIType = None
    PIIMatch = None
    PIIScanResult = None
    scan_for_pii = None
    redact_pii = None
    AuditAction = None
    AuditLogEntry = None
    AuditLogger = None
    audit_logger = None
    audit_log = None
    DSARType = None
    DSARStatus = None
    DSARRequest = None
    DSARManager = None
    dsar_manager = None
    ConsentRecord = None
    ConsentManager = None
    consent_manager = None
    RetentionPolicy = None

# ============================================================
# Scaling & Performance modules
# ============================================================

# Database Scaling
try:
    from .database_scaling import (
        ScaleTier,
        DatabaseConfig,
        ConnectionPool,
        ReadWriteSplitter,
        ShardRouter,
        ScalableDatabase,
        get_database_config,
        get_database,
        close_database,
        CAPACITY_ESTIMATES,
    )
except ImportError as e:
    logger.debug(f"Database scaling module not available: {e}")
    ScaleTier = None
    DatabaseConfig = None
    ConnectionPool = None
    ReadWriteSplitter = None
    ShardRouter = None
    ScalableDatabase = None
    get_database_config = None
    get_database = None
    close_database = None
    CAPACITY_ESTIMATES = None

# Vector DB Scaling
try:
    from .vector_db_scaling import (
        QdrantNode,
        CollectionConfig,
        ScalableQdrantClient,
        get_qdrant_client,
        close_qdrant_client,
    )
except ImportError as e:
    logger.debug(f"Vector DB scaling module not available: {e}")
    QdrantNode = None
    CollectionConfig = None
    ScalableQdrantClient = None
    get_qdrant_client = None
    close_qdrant_client = None

# Cache Service
try:
    from .cache_service import (
        CacheConfig,
        LocalCache,
        CacheService,
        cached,
        get_cache_service,
        close_cache_service,
    )
except ImportError as e:
    logger.debug(f"Cache service module not available: {e}")
    CacheConfig = None
    LocalCache = None
    CacheService = None
    cached = None
    get_cache_service = None
    close_cache_service = None

# Rate Limiting
try:
    from .rate_limiting import (
        RateLimitAlgorithm,
        RateLimitConfig,
        RateLimitResult,
        RATE_LIMIT_TIERS,
        get_rate_limit_config,
        DistributedRateLimiter,
        CircuitBreaker as DistributedCircuitBreaker,
        BackpressureManager,
        OpenRouterQuotaManager,
        rate_limited,
        get_rate_limiter,
        get_quota_manager,
    )
except ImportError as e:
    logger.debug(f"Rate limiting module not available: {e}")
    RateLimitAlgorithm = None
    RateLimitConfig = None
    RateLimitResult = None
    RATE_LIMIT_TIERS = None
    get_rate_limit_config = None
    DistributedRateLimiter = None
    DistributedCircuitBreaker = None
    BackpressureManager = None
    OpenRouterQuotaManager = None
    rate_limited = None
    get_rate_limiter = None
    get_quota_manager = None

# Metrics
try:
    from .metrics import (
        PROMETHEUS_AVAILABLE,
        metrics,
        MetricsRecorder,
        MetricsCollector,
        track_request,
        track_search,
        track_llm_call,
        get_metrics_response,
        setup_metrics_endpoint,
        start_metrics_collector,
        stop_metrics_collector,
    )
except ImportError as e:
    logger.debug(f"Metrics module not available: {e}")
    PROMETHEUS_AVAILABLE = False
    metrics = None
    MetricsRecorder = None
    MetricsCollector = None
    track_request = None
    track_search = None
    track_llm_call = None
    get_metrics_response = None
    setup_metrics_endpoint = None
    start_metrics_collector = None
    stop_metrics_collector = None

# Backpressure
try:
    from .backpressure import (
        ServiceState,
        ServiceHealth,
        AdaptiveRateLimiter,
        LoadShedder,
        LoadSheddedException,
        RetryPolicy,
        BulkheadIsolator,
        BackpressureController,
        CircuitOpenException,
        RateLimitedException,
        OpenRouterBackpressure,
        QdrantBackpressure,
        DatabaseBackpressure,
        get_backpressure,
        get_all_status,
        with_backpressure,
        with_retry,
    )
except ImportError as e:
    logger.debug(f"Backpressure module not available: {e}")
    ServiceState = None
    ServiceHealth = None
    AdaptiveRateLimiter = None
    LoadShedder = None
    LoadSheddedException = None
    RetryPolicy = None
    BulkheadIsolator = None
    BackpressureController = None
    CircuitOpenException = None
    RateLimitedException = None
    OpenRouterBackpressure = None
    QdrantBackpressure = None
    DatabaseBackpressure = None
    get_backpressure = None
    get_all_status = None
    with_backpressure = None
    with_retry = None

# ============================================================
# Chaos Engineering module
# ============================================================

try:
    from .chaos import (
        ChaosEngine,
        ChaosConfig,
        ChaosExperiment,
        ExperimentType,
        ExperimentStatus,
        ExperimentResult,
        LatencyExperiment,
        FailureExperiment,
        TimeoutExperiment,
        ResourceExhaustionExperiment,
        NetworkPartitionExperiment,
        DataCorruptionExperiment,
        create_standard_experiments,
        setup_chaos_routes,
    )
except ImportError as e:
    logger.debug(f"Chaos module not available: {e}")
    ChaosEngine = None
    ChaosConfig = None
    ChaosExperiment = None
    ExperimentType = None
    ExperimentStatus = None
    ExperimentResult = None
    LatencyExperiment = None
    FailureExperiment = None
    TimeoutExperiment = None
    ResourceExhaustionExperiment = None
    NetworkPartitionExperiment = None
    DataCorruptionExperiment = None
    create_standard_experiments = None
    setup_chaos_routes = None

# ============================================================
# Data Consistency module
# ============================================================

try:
    from .consistency import (
        # Transaction management
        TransactionManager,
        TransactionConfig,
        TransactionContext,
        TransactionStatus,
        IsolationLevel,
        # Idempotency
        IdempotencyManager,
        IdempotencyConfig,
        IdempotencyRecord,
        # Saga pattern
        SagaOrchestrator,
        SagaStep,
        SagaContext,
        SagaStepStatus,
        SagaFailedException,
        # Distributed locks
        DistributedLock,
        LockConfig,
        LockAcquisitionError,
        # Optimistic locking
        OptimisticLockManager,
        VersionedEntity,
        # Middleware
        ConsistencyMiddleware,
        setup_consistency_routes,
    )
except ImportError as e:
    logger.debug(f"Consistency module not available: {e}")
    TransactionManager = None
    TransactionConfig = None
    TransactionContext = None
    TransactionStatus = None
    IsolationLevel = None
    IdempotencyManager = None
    IdempotencyConfig = None
    IdempotencyRecord = None
    SagaOrchestrator = None
    SagaStep = None
    SagaContext = None
    SagaStepStatus = None
    SagaFailedException = None
    DistributedLock = None
    LockConfig = None
    LockAcquisitionError = None
    OptimisticLockManager = None
    VersionedEntity = None
    ConsistencyMiddleware = None
    setup_consistency_routes = None

# ============================================================
# Automated Failover module
# ============================================================

try:
    from .failover import (
        FailoverManager,
        FailoverConfig,
        FailoverEvent,
        FailoverReason,
        Node,
        NodeRole,
        NodeStatus,
        NodeHealth,
        setup_failover_routes,
    )
except ImportError as e:
    logger.debug(f"Failover module not available: {e}")
    FailoverManager = None
    FailoverConfig = None
    FailoverEvent = None
    FailoverReason = None
    Node = None
    NodeRole = None
    NodeStatus = None
    NodeHealth = None
    setup_failover_routes = None

# ============================================================
# Enhanced Circuit Breaker module
# ============================================================

try:
    from .circuit_breaker import (
        CircuitBreaker as EnhancedCircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerMetrics,
        CircuitBreakerOpenError,
        CircuitBreakerRegistry,
        CircuitState as EnhancedCircuitState,
        FailureType,
        CallResult,
        get_circuit_breaker,
        Bulkhead,
        BulkheadFullError,
        setup_circuit_breaker_routes,
    )
except ImportError as e:
    logger.debug(f"Enhanced circuit breaker module not available: {e}")
    EnhancedCircuitBreaker = None
    CircuitBreakerConfig = None
    CircuitBreakerMetrics = None
    CircuitBreakerOpenError = None
    CircuitBreakerRegistry = None
    EnhancedCircuitState = None
    FailureType = None
    CallResult = None
    get_circuit_breaker = None
    Bulkhead = None
    BulkheadFullError = None
    setup_circuit_breaker_routes = None


__all__ = [
    # Database
    'db_pool',
    'get_db', 
    'DatabasePool',
    'async_db_pool',
    'get_async_db',
    'AsyncDatabasePool',
    'PoolConfig',
    'DatabaseManager',
    'get_db_fallback',
    # Query Optimizer
    'QueryCache',
    'QueryAnalyzer',
    'QueryStats',
    'get_query_cache',
    'get_query_analyzer',
    'cached_query',
    'timed_query',
    # Cache
    'cache',
    'cache_get_or_compute',
    'CacheManager',
    # Resilience
    'CircuitBreaker',
    'CircuitBreakerError', 
    'CircuitState',
    'retry_async',
    'retry_sync',
    'async_timeout',
    # Tracing
    'init_tracing',
    'get_tracer',
    'create_span_attributes',
    # Correlation IDs
    'CorrelationIdMiddleware',
    'CorrelationIdLogFilter',
    'CorrelationJsonFormatter',
    'CorrelatedHttpClient',
    'get_correlation_id',
    'get_request_id',
    'get_span_id',
    'propagate_correlation_headers',
    'setup_correlation_logging',
    'setup_json_logging',
    'with_correlation',
    # Utilities
    'HealthCheckBuilder',
    'ServiceLogger',
    'setup_logging',
    'datetime_to_iso',
    'format_query_results',
    'validate_pagination',
    'sanitize_string',
    # Actions
    'ActionRegistry',
    'ActionResult',
    'BaseAction',
    'action_registry',
    # Exceptions
    'ServiceException',
    'DatabaseError',
    'DocumentError',
    'QueryError',
    'EmbeddingError',
    'SearchError',
    'ExternalServiceError',
    'VectorStoreError',
    # Security
    'SecurityConfig',
    'SecureLogger',
    'get_secure_logger',
    'verify_api_key',
    'require_api_key',
    'RateLimiter',
    'rate_limiter',
    'check_rate_limit',
    'secure_sanitize_string',
    'sanitize_filename',
    'validate_file_extension',
    'validate_mime_type',
    'check_sql_injection',
    'escape_html',
    'redact_sensitive',
    'SecureQueryInput',
    'SecureUploadInput',
    'SecurityHeadersMiddleware',
    'RateLimitMiddleware',
    'RequestLoggingMiddleware',
    'create_error_response',
    'global_exception_handler',
    'setup_security',
    # Redis
    'RedisConfig',
    'SecureRedisClient',
    'redis_client',
    # Database Security
    'db_check_sql_injection',
    'sanitize_identifier',
    'sanitize_value',
    'QueryBuilder',
    'PasswordSecurity',
    'DataEncryption',
    # Privacy & GDPR
    'PIIType',
    'PIIMatch',
    'PIIScanResult',
    'scan_for_pii',
    'redact_pii',
    'AuditAction',
    'AuditLogEntry',
    'AuditLogger',
    'audit_logger',
    'audit_log',
    'DSARType',
    'DSARStatus',
    'DSARRequest',
    'DSARManager',
    'dsar_manager',
    'ConsentRecord',
    'ConsentManager',
    'consent_manager',
    'RetentionPolicy',
    # Database Scaling
    'ScaleTier',
    'DatabaseConfig',
    'ConnectionPool',
    'ReadWriteSplitter',
    'ShardRouter',
    'ScalableDatabase',
    'get_database_config',
    'get_database',
    'close_database',
    'CAPACITY_ESTIMATES',
    # Vector DB Scaling
    'QdrantNode',
    'CollectionConfig',
    'ScalableQdrantClient',
    'get_qdrant_client',
    'close_qdrant_client',
    # Cache Service
    'CacheConfig',
    'LocalCache',
    'CacheService',
    'cached',
    'get_cache_service',
    'close_cache_service',
    # Rate Limiting
    'RateLimitAlgorithm',
    'RateLimitConfig',
    'RateLimitResult',
    'RATE_LIMIT_TIERS',
    'get_rate_limit_config',
    'DistributedRateLimiter',
    'DistributedCircuitBreaker',
    'BackpressureManager',
    'OpenRouterQuotaManager',
    'rate_limited',
    'get_rate_limiter',
    'get_quota_manager',
    # Metrics
    'PROMETHEUS_AVAILABLE',
    'metrics',
    'MetricsRecorder',
    'MetricsCollector',
    'track_request',
    'track_search',
    'track_llm_call',
    'get_metrics_response',
    'setup_metrics_endpoint',
    'start_metrics_collector',
    'stop_metrics_collector',
    # Backpressure
    'ServiceState',
    'ServiceHealth',
    'AdaptiveRateLimiter',
    'LoadShedder',
    'LoadSheddedException',
    'RetryPolicy',
    'BulkheadIsolator',
    'BackpressureController',
    'CircuitOpenException',
    'RateLimitedException',
    'OpenRouterBackpressure',
    'QdrantBackpressure',
    'DatabaseBackpressure',
    'get_backpressure',
    'get_all_status',
    'with_backpressure',
    'with_retry',
    # Chaos Engineering
    'ChaosEngine',
    'ChaosConfig',
    'ChaosExperiment',
    'ExperimentType',
    'ExperimentStatus',
    'ExperimentResult',
    'LatencyExperiment',
    'FailureExperiment',
    'TimeoutExperiment',
    'ResourceExhaustionExperiment',
    'NetworkPartitionExperiment',
    'DataCorruptionExperiment',
    'create_standard_experiments',
    'setup_chaos_routes',
    # Data Consistency
    'TransactionManager',
    'TransactionConfig',
    'TransactionContext',
    'TransactionStatus',
    'IsolationLevel',
    'IdempotencyManager',
    'IdempotencyConfig',
    'IdempotencyRecord',
    'SagaOrchestrator',
    'SagaStep',
    'SagaContext',
    'SagaStepStatus',
    'SagaFailedException',
    'DistributedLock',
    'LockConfig',
    'LockAcquisitionError',
    'OptimisticLockManager',
    'VersionedEntity',
    'ConsistencyMiddleware',
    'setup_consistency_routes',
    # Automated Failover
    'FailoverManager',
    'FailoverConfig',
    'FailoverEvent',
    'FailoverReason',
    'Node',
    'NodeRole',
    'NodeStatus',
    'NodeHealth',
    'setup_failover_routes',
    # Enhanced Circuit Breaker
    'EnhancedCircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerMetrics',
    'CircuitBreakerOpenError',
    'CircuitBreakerRegistry',
    'EnhancedCircuitState',
    'FailureType',
    'CallResult',
    'get_circuit_breaker',
    'Bulkhead',
    'BulkheadFullError',
    'setup_circuit_breaker_routes',
]
