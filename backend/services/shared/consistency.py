"""
Data Consistency Patterns
Provides tools for ensuring data consistency in distributed systems.

Features:
- Transaction management with retry logic
- Idempotency handling
- Saga pattern for distributed transactions
- Distributed locks
- Optimistic/pessimistic locking

Usage:
    from services.shared.consistency import (
        TransactionManager, IdempotencyManager, SagaOrchestrator, DistributedLock
    )
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, TypeVar, Generic, Awaitable
from contextlib import asynccontextmanager
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Transaction Management
# ============================================================================

class TransactionStatus(str, Enum):
    """Status of a transaction."""
    PENDING = "pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class IsolationLevel(str, Enum):
    """Database isolation levels."""
    READ_UNCOMMITTED = "read_uncommitted"
    READ_COMMITTED = "read_committed"
    REPEATABLE_READ = "repeatable_read"
    SERIALIZABLE = "serializable"


@dataclass
class TransactionConfig:
    """Configuration for transaction management."""
    max_retries: int = 3
    retry_delay_ms: int = 100
    retry_backoff_multiplier: float = 2.0
    timeout_seconds: float = 30.0
    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    savepoint_enabled: bool = True


@dataclass
class TransactionContext:
    """Context for a transaction."""
    transaction_id: str
    started_at: datetime
    status: TransactionStatus = TransactionStatus.PENDING
    retries: int = 0
    savepoints: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TransactionManager:
    """
    Manages database transactions with retry logic and savepoints.
    """
    
    def __init__(self, db_pool, config: TransactionConfig = None):
        self.db_pool = db_pool
        self.config = config or TransactionConfig()
        self.active_transactions: Dict[str, TransactionContext] = {}
    
    @asynccontextmanager
    async def transaction(
        self,
        isolation_level: IsolationLevel = None,
        read_only: bool = False
    ):
        """
        Execute operations within a transaction.
        
        Usage:
            async with tx_manager.transaction() as tx:
                await tx.execute("INSERT ...")
                await tx.execute("UPDATE ...")
        """
        tx_id = str(uuid.uuid4())
        isolation = isolation_level or self.config.isolation_level
        
        context = TransactionContext(
            transaction_id=tx_id,
            started_at=datetime.now()
        )
        self.active_transactions[tx_id] = context
        
        async with self.db_pool.acquire() as conn:
            try:
                # Set isolation level
                await conn.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation.value.upper().replace('_', ' ')}")
                if read_only:
                    await conn.execute("SET TRANSACTION READ ONLY")
                
                async with conn.transaction():
                    yield conn
                    context.status = TransactionStatus.COMMITTED
                    
            except Exception as e:
                context.status = TransactionStatus.ROLLED_BACK
                logger.error(f"Transaction {tx_id} rolled back: {e}")
                raise
            finally:
                del self.active_transactions[tx_id]
    
    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        retryable_exceptions: tuple = (Exception,)
    ) -> T:
        """
        Execute an operation with automatic retry on failure.
        """
        last_exception = None
        delay = self.config.retry_delay_ms / 1000
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    operation(),
                    timeout=self.config.timeout_seconds
                )
            except retryable_exceptions as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    logger.warning(f"Operation failed (attempt {attempt + 1}), retrying: {e}")
                    await asyncio.sleep(delay)
                    delay *= self.config.retry_backoff_multiplier
        
        raise last_exception
    
    @asynccontextmanager
    async def savepoint(self, conn, name: str = None):
        """
        Create a savepoint within a transaction.
        """
        if not self.config.savepoint_enabled:
            yield
            return
        
        sp_name = name or f"sp_{int(time.time()*1000)}"
        
        try:
            await conn.execute(f"SAVEPOINT {sp_name}")
            yield
        except Exception:
            await conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            raise
        finally:
            await conn.execute(f"RELEASE SAVEPOINT {sp_name}")


# ============================================================================
# Idempotency
# ============================================================================

@dataclass
class IdempotencyConfig:
    """Configuration for idempotency handling."""
    key_ttl_seconds: int = 86400  # 24 hours
    storage_backend: str = "redis"  # redis, memory, database
    hash_algorithm: str = "sha256"


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation."""
    key: str
    request_hash: str
    response: Any
    created_at: datetime
    expires_at: datetime
    status: str = "completed"


class IdempotencyManager:
    """
    Ensures operations are idempotent using request fingerprinting.
    """
    
    def __init__(
        self,
        redis_client=None,
        config: IdempotencyConfig = None
    ):
        self.redis = redis_client
        self.config = config or IdempotencyConfig()
        self._memory_store: Dict[str, IdempotencyRecord] = {}
    
    def generate_key(
        self,
        operation: str,
        params: Dict[str, Any],
        user_id: str = None
    ) -> str:
        """Generate idempotency key from operation parameters."""
        key_data = {
            "operation": operation,
            "params": params,
            "user_id": user_id
        }
        
        serialized = json.dumps(key_data, sort_keys=True, default=str)
        
        if self.config.hash_algorithm == "sha256":
            hash_value = hashlib.sha256(serialized.encode()).hexdigest()
        else:
            hash_value = hashlib.md5(serialized.encode()).hexdigest()
        
        return f"idempotency:{operation}:{hash_value}"
    
    async def get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response for idempotency key."""
        if self.redis:
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
        else:
            record = self._memory_store.get(key)
            if record and record.expires_at > datetime.now():
                return record.response
        
        return None
    
    async def cache_response(self, key: str, response: Any) -> None:
        """Cache response for idempotency key."""
        ttl = self.config.key_ttl_seconds
        
        if self.redis:
            await self.redis.setex(key, ttl, json.dumps(response, default=str))
        else:
            self._memory_store[key] = IdempotencyRecord(
                key=key,
                request_hash=key.split(":")[-1],
                response=response,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=ttl)
            )
    
    async def is_duplicate(self, key: str) -> bool:
        """Check if request is a duplicate."""
        return await self.get_cached_response(key) is not None
    
    def idempotent(self, operation: str, key_params: List[str] = None):
        """
        Decorator for making operations idempotent.
        
        Usage:
            @idempotency.idempotent("create_user", key_params=["email"])
            async def create_user(email: str, name: str):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract key parameters
                if key_params:
                    params = {k: kwargs.get(k) for k in key_params if k in kwargs}
                else:
                    params = kwargs
                
                key = self.generate_key(operation, params)
                
                # Check for cached response
                cached = await self.get_cached_response(key)
                if cached is not None:
                    logger.info(f"Returning cached response for {operation}")
                    return cached
                
                # Execute operation
                result = await func(*args, **kwargs)
                
                # Cache response
                await self.cache_response(key, result)
                
                return result
            return wrapper
        return decorator
    
    @asynccontextmanager
    async def idempotent_operation(self, key: str):
        """
        Context manager for idempotent operations.
        
        Usage:
            async with idempotency.idempotent_operation(key) as cached:
                if cached is not None:
                    return cached
                result = await do_work()
                return result
        """
        cached = await self.get_cached_response(key)
        
        class IdempotencyContext:
            def __init__(self, cached_response, manager, key):
                self.cached = cached_response
                self.manager = manager
                self.key = key
                self.result = None
            
            async def set_result(self, result):
                self.result = result
                await self.manager.cache_response(self.key, result)
        
        context = IdempotencyContext(cached, self, key)
        yield context


# ============================================================================
# Saga Pattern
# ============================================================================

class SagaStepStatus(str, Enum):
    """Status of a saga step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """A step in a saga."""
    name: str
    action: Callable[..., Awaitable[Any]]
    compensation: Callable[..., Awaitable[None]]
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Any = None
    error: Optional[str] = None


@dataclass
class SagaContext:
    """Context passed through saga steps."""
    saga_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)


class SagaOrchestrator:
    """
    Orchestrates distributed transactions using the Saga pattern.
    
    Executes a series of steps, and if any step fails,
    compensates by rolling back previous steps in reverse order.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []
        self.completed_steps: List[SagaStep] = []
    
    def add_step(
        self,
        name: str,
        action: Callable[[SagaContext], Awaitable[Any]],
        compensation: Callable[[SagaContext], Awaitable[None]]
    ) -> "SagaOrchestrator":
        """Add a step to the saga."""
        self.steps.append(SagaStep(
            name=name,
            action=action,
            compensation=compensation
        ))
        return self
    
    async def execute(self, initial_data: Dict[str, Any] = None) -> SagaContext:
        """
        Execute the saga.
        
        Returns the saga context with results from all steps.
        Raises exception if saga fails after compensation.
        """
        saga_id = str(uuid.uuid4())
        context = SagaContext(
            saga_id=saga_id,
            data=initial_data or {}
        )
        
        logger.info(f"Starting saga '{self.name}' [{saga_id}]")
        self.completed_steps = []
        
        try:
            for step in self.steps:
                step.status = SagaStepStatus.RUNNING
                logger.info(f"Executing step: {step.name}")
                
                try:
                    result = await step.action(context)
                    step.result = result
                    step.status = SagaStepStatus.COMPLETED
                    context.step_results[step.name] = result
                    self.completed_steps.append(step)
                    
                except Exception as e:
                    step.status = SagaStepStatus.FAILED
                    step.error = str(e)
                    logger.error(f"Step '{step.name}' failed: {e}")
                    raise
            
            logger.info(f"Saga '{self.name}' completed successfully")
            return context
            
        except Exception as e:
            # Compensate in reverse order
            logger.warning(f"Compensating saga '{self.name}'")
            await self._compensate(context)
            raise SagaFailedException(
                f"Saga '{self.name}' failed: {e}",
                completed_steps=[s.name for s in self.completed_steps]
            ) from e
    
    async def _compensate(self, context: SagaContext) -> None:
        """Compensate completed steps in reverse order."""
        for step in reversed(self.completed_steps):
            step.status = SagaStepStatus.COMPENSATING
            logger.info(f"Compensating step: {step.name}")
            
            try:
                await step.compensation(context)
                step.status = SagaStepStatus.COMPENSATED
            except Exception as e:
                step.status = SagaStepStatus.FAILED
                logger.error(f"Compensation for '{step.name}' failed: {e}")
                # Continue compensating other steps


class SagaFailedException(Exception):
    """Exception raised when a saga fails."""
    
    def __init__(self, message: str, completed_steps: List[str] = None):
        super().__init__(message)
        self.completed_steps = completed_steps or []


# ============================================================================
# Distributed Locks
# ============================================================================

@dataclass
class LockConfig:
    """Configuration for distributed locks."""
    default_ttl_seconds: int = 30
    retry_count: int = 3
    retry_delay_ms: int = 100
    extend_ttl_seconds: int = 10


class DistributedLock:
    """
    Distributed lock implementation using Redis.
    
    Features:
    - Automatic expiration to prevent deadlocks
    - Lock extension for long operations
    - Retry with backoff
    """
    
    def __init__(
        self,
        redis_client,
        config: LockConfig = None
    ):
        self.redis = redis_client
        self.config = config or LockConfig()
        self._held_locks: Dict[str, str] = {}  # lock_key -> lock_value
    
    async def acquire(
        self,
        key: str,
        ttl_seconds: int = None,
        wait: bool = True
    ) -> bool:
        """
        Acquire a distributed lock.
        
        Args:
            key: Lock key
            ttl_seconds: Lock TTL (defaults to config)
            wait: Whether to wait and retry if lock is held
        
        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = f"lock:{key}"
        lock_value = str(uuid.uuid4())
        ttl = ttl_seconds or self.config.default_ttl_seconds
        
        delay = self.config.retry_delay_ms / 1000
        attempts = self.config.retry_count if wait else 1
        
        for attempt in range(attempts):
            # Try to acquire lock using SET NX EX
            acquired = await self.redis.set(
                lock_key,
                lock_value,
                nx=True,
                ex=ttl
            )
            
            if acquired:
                self._held_locks[lock_key] = lock_value
                logger.debug(f"Acquired lock: {key}")
                return True
            
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
                delay *= 1.5  # Backoff
        
        logger.debug(f"Failed to acquire lock: {key}")
        return False
    
    async def release(self, key: str) -> bool:
        """
        Release a distributed lock.
        
        Only releases if we hold the lock (prevents releasing someone else's lock).
        """
        lock_key = f"lock:{key}"
        lock_value = self._held_locks.get(lock_key)
        
        if not lock_value:
            return False
        
        # Lua script for atomic check-and-delete
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        released = await self.redis.eval(script, 1, lock_key, lock_value)
        
        if released:
            del self._held_locks[lock_key]
            logger.debug(f"Released lock: {key}")
            return True
        
        return False
    
    async def extend(self, key: str, ttl_seconds: int = None) -> bool:
        """
        Extend the TTL of a held lock.
        """
        lock_key = f"lock:{key}"
        lock_value = self._held_locks.get(lock_key)
        
        if not lock_value:
            return False
        
        ttl = ttl_seconds or self.config.extend_ttl_seconds
        
        # Lua script for atomic check-and-extend
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        extended = await self.redis.eval(script, 1, lock_key, lock_value, ttl)
        return bool(extended)
    
    @asynccontextmanager
    async def lock(
        self,
        key: str,
        ttl_seconds: int = None,
        extend_interval: int = None
    ):
        """
        Context manager for distributed locking.
        
        Usage:
            async with lock.lock("resource:123"):
                await do_exclusive_work()
        """
        acquired = await self.acquire(key, ttl_seconds)
        if not acquired:
            raise LockAcquisitionError(f"Failed to acquire lock: {key}")
        
        extend_task = None
        
        try:
            if extend_interval:
                # Auto-extend lock while holding
                async def auto_extend():
                    while True:
                        await asyncio.sleep(extend_interval)
                        await self.extend(key)
                
                extend_task = asyncio.create_task(auto_extend())
            
            yield
            
        finally:
            if extend_task:
                extend_task.cancel()
                try:
                    await extend_task
                except asyncio.CancelledError:
                    pass
            
            await self.release(key)
    
    async def is_locked(self, key: str) -> bool:
        """Check if a resource is locked."""
        lock_key = f"lock:{key}"
        return await self.redis.exists(lock_key)
    
    async def get_lock_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get information about a lock."""
        lock_key = f"lock:{key}"
        
        value = await self.redis.get(lock_key)
        if not value:
            return None
        
        ttl = await self.redis.ttl(lock_key)
        
        return {
            "key": key,
            "locked": True,
            "ttl_seconds": ttl,
            "held_by_us": lock_key in self._held_locks
        }


class LockAcquisitionError(Exception):
    """Raised when lock acquisition fails."""
    pass


# ============================================================================
# Optimistic Locking
# ============================================================================

@dataclass
class VersionedEntity(Generic[T]):
    """Entity with version for optimistic locking."""
    data: T
    version: int
    updated_at: datetime


class OptimisticLockManager:
    """
    Manages optimistic locking using version numbers.
    """
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def update_with_version(
        self,
        table: str,
        id_column: str,
        id_value: Any,
        updates: Dict[str, Any],
        current_version: int
    ) -> bool:
        """
        Update a record only if version matches.
        
        Returns True if update succeeded, False if version conflict.
        """
        # Build UPDATE query with version check
        set_clauses = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(updates.keys()))
        
        query = f"""
            UPDATE {table}
            SET {set_clauses}, version = version + 1, updated_at = NOW()
            WHERE {id_column} = $1 AND version = $2
            RETURNING version
        """
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                id_value,
                current_version,
                *updates.values()
            )
        
        if result is None:
            logger.warning(f"Optimistic lock conflict on {table}[{id_value}]")
            return False
        
        return True
    
    async def update_with_retry(
        self,
        table: str,
        id_column: str,
        id_value: Any,
        update_fn: Callable[[VersionedEntity], Dict[str, Any]],
        max_retries: int = 3
    ) -> bool:
        """
        Update with automatic retry on version conflict.
        
        update_fn receives current entity and returns dict of updates.
        """
        for attempt in range(max_retries):
            # Fetch current version
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT *, version FROM {table} WHERE {id_column} = $1",
                    id_value
                )
            
            if not row:
                raise ValueError(f"Entity not found: {table}[{id_value}]")
            
            entity = VersionedEntity(
                data=dict(row),
                version=row['version'],
                updated_at=row.get('updated_at', datetime.now())
            )
            
            updates = update_fn(entity)
            
            if await self.update_with_version(
                table, id_column, id_value, updates, entity.version
            ):
                return True
            
            # Wait before retry
            await asyncio.sleep(0.1 * (attempt + 1))
        
        return False


# ============================================================================
# Consistency Middleware
# ============================================================================

class ConsistencyMiddleware:
    """
    FastAPI middleware for ensuring request consistency.
    
    Features:
    - Idempotency key handling
    - Request deduplication
    - Correlation ID propagation
    """
    
    def __init__(
        self,
        app,
        idempotency_manager: IdempotencyManager = None
    ):
        self.app = app
        self.idempotency = idempotency_manager
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract headers
        headers = dict(scope.get("headers", []))
        
        # Get or generate correlation ID
        correlation_id = headers.get(b"x-correlation-id", b"").decode() or str(uuid.uuid4())
        
        # Get idempotency key
        idempotency_key = headers.get(b"x-idempotency-key", b"").decode()
        
        # Store in scope for access in handlers
        scope["correlation_id"] = correlation_id
        scope["idempotency_key"] = idempotency_key
        
        await self.app(scope, receive, send)


# FastAPI integration
def setup_consistency_routes(app, lock: DistributedLock = None):
    """Add consistency management endpoints to FastAPI app."""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/consistency", tags=["consistency"])
    
    @router.get("/locks/{key}")
    async def get_lock_status(key: str):
        """Get lock status."""
        if not lock:
            return {"error": "Locking not configured"}
        
        info = await lock.get_lock_info(key)
        return info or {"key": key, "locked": False}
    
    app.include_router(router)
