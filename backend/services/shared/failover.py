"""
Automated Failover System
Provides automatic failover capabilities for high availability.

Features:
- Health-based automatic failover
- Primary/replica promotion
- Connection pool failover
- Service discovery integration
- Failover notifications

Usage:
    from services.shared.failover import FailoverManager, FailoverConfig
    
    manager = FailoverManager(config)
    manager.register_primary("database", primary_pool)
    manager.register_replica("database", replica_pool)
    
    # Get best available connection
    pool = await manager.get_connection("database")
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Awaitable, Set
import aiohttp

logger = logging.getLogger(__name__)


class NodeRole(str, Enum):
    """Role of a node in the cluster."""
    PRIMARY = "primary"
    REPLICA = "replica"
    STANDBY = "standby"
    ARBITER = "arbiter"


class NodeStatus(str, Enum):
    """Status of a node."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    PROMOTING = "promoting"
    DEMOTING = "demoting"


class FailoverReason(str, Enum):
    """Reason for failover."""
    HEALTH_CHECK_FAILED = "health_check_failed"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    SPLIT_BRAIN = "split_brain"


@dataclass
class FailoverConfig:
    """Configuration for failover management."""
    health_check_interval_seconds: float = 5.0
    health_check_timeout_seconds: float = 3.0
    failure_threshold: int = 3  # Failures before failover
    recovery_threshold: int = 2  # Successes before recovery
    min_failover_interval_seconds: float = 60.0  # Prevent flapping
    auto_failback: bool = False  # Automatically failback to primary when healthy
    notification_webhook: Optional[str] = None
    quorum_required: int = 1  # Minimum healthy nodes required


@dataclass
class NodeHealth:
    """Health information for a node."""
    node_id: str
    status: NodeStatus
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check: Optional[datetime] = None
    last_healthy: Optional[datetime] = None
    response_time_ms: float = 0
    error_message: Optional[str] = None


@dataclass
class FailoverEvent:
    """Record of a failover event."""
    event_id: str
    timestamp: datetime
    from_node: str
    to_node: str
    reason: FailoverReason
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class Node:
    """A node in the cluster."""
    node_id: str
    role: NodeRole
    endpoint: str
    connection: Any  # Connection pool or client
    health_check: Callable[[], Awaitable[bool]]
    priority: int = 0  # Higher = preferred for promotion
    metadata: Dict[str, Any] = field(default_factory=dict)


class FailoverManager:
    """
    Manages automatic failover for high availability.
    """
    
    def __init__(self, config: FailoverConfig = None):
        self.config = config or FailoverConfig()
        self.nodes: Dict[str, Dict[str, Node]] = {}  # service -> node_id -> Node
        self.health: Dict[str, Dict[str, NodeHealth]] = {}  # service -> node_id -> Health
        self.active_primaries: Dict[str, str] = {}  # service -> active primary node_id
        self.events: List[FailoverEvent] = []
        self.last_failover: Dict[str, datetime] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[FailoverEvent], Awaitable[None]]] = []
        self._running = False
    
    def register_node(
        self,
        service: str,
        node_id: str,
        role: NodeRole,
        endpoint: str,
        connection: Any,
        health_check: Callable[[], Awaitable[bool]],
        priority: int = 0
    ) -> None:
        """Register a node for a service."""
        if service not in self.nodes:
            self.nodes[service] = {}
            self.health[service] = {}
        
        node = Node(
            node_id=node_id,
            role=role,
            endpoint=endpoint,
            connection=connection,
            health_check=health_check,
            priority=priority
        )
        
        self.nodes[service][node_id] = node
        self.health[service][node_id] = NodeHealth(
            node_id=node_id,
            status=NodeStatus.UNKNOWN
        )
        
        # Set initial primary
        if role == NodeRole.PRIMARY and service not in self.active_primaries:
            self.active_primaries[service] = node_id
        
        logger.info(f"Registered node {node_id} ({role}) for service {service}")
    
    def register_primary(
        self,
        service: str,
        connection: Any,
        endpoint: str = "primary",
        health_check: Callable[[], Awaitable[bool]] = None
    ) -> None:
        """Convenience method to register primary node."""
        self.register_node(
            service=service,
            node_id=f"{service}_primary",
            role=NodeRole.PRIMARY,
            endpoint=endpoint,
            connection=connection,
            health_check=health_check or (lambda: asyncio.sleep(0) or True),
            priority=100
        )
    
    def register_replica(
        self,
        service: str,
        connection: Any,
        endpoint: str = "replica",
        health_check: Callable[[], Awaitable[bool]] = None,
        priority: int = 50
    ) -> None:
        """Convenience method to register replica node."""
        replica_count = sum(
            1 for n in self.nodes.get(service, {}).values()
            if n.role == NodeRole.REPLICA
        )
        
        self.register_node(
            service=service,
            node_id=f"{service}_replica_{replica_count + 1}",
            role=NodeRole.REPLICA,
            endpoint=endpoint,
            connection=connection,
            health_check=health_check or (lambda: asyncio.sleep(0) or True),
            priority=priority
        )
    
    async def start_monitoring(self) -> None:
        """Start health check monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started failover monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop health check monitoring."""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped failover monitoring")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_nodes()
                await asyncio.sleep(self.config.health_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(1)
    
    async def _check_all_nodes(self) -> None:
        """Check health of all registered nodes."""
        tasks = []
        
        for service, nodes in self.nodes.items():
            for node_id, node in nodes.items():
                tasks.append(self._check_node(service, node))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_node(self, service: str, node: Node) -> None:
        """Check health of a single node."""
        health = self.health[service][node.node_id]
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                node.health_check(),
                timeout=self.config.health_check_timeout_seconds
            )
            
            response_time = (time.time() - start_time) * 1000
            health.response_time_ms = response_time
            health.last_check = datetime.now()
            
            if result:
                health.consecutive_successes += 1
                health.consecutive_failures = 0
                health.last_healthy = datetime.now()
                health.error_message = None
                
                if health.consecutive_successes >= self.config.recovery_threshold:
                    if health.status != NodeStatus.HEALTHY:
                        logger.info(f"Node {node.node_id} recovered")
                    health.status = NodeStatus.HEALTHY
                    
                    # Check for auto-failback
                    if self.config.auto_failback and node.role == NodeRole.PRIMARY:
                        await self._check_failback(service)
            else:
                await self._handle_check_failure(service, node, health, "Health check returned false")
                
        except asyncio.TimeoutError:
            await self._handle_check_failure(service, node, health, "Health check timeout")
        except Exception as e:
            await self._handle_check_failure(service, node, health, str(e))
    
    async def _handle_check_failure(
        self,
        service: str,
        node: Node,
        health: NodeHealth,
        error: str
    ) -> None:
        """Handle a health check failure."""
        health.consecutive_failures += 1
        health.consecutive_successes = 0
        health.error_message = error
        health.last_check = datetime.now()
        
        if health.consecutive_failures >= self.config.failure_threshold:
            if health.status != NodeStatus.UNHEALTHY:
                logger.warning(f"Node {node.node_id} marked unhealthy: {error}")
            health.status = NodeStatus.UNHEALTHY
            
            # Check if this is the active primary
            if self.active_primaries.get(service) == node.node_id:
                await self._trigger_failover(service, FailoverReason.HEALTH_CHECK_FAILED)
        else:
            health.status = NodeStatus.DEGRADED
    
    async def _trigger_failover(self, service: str, reason: FailoverReason) -> bool:
        """Trigger failover for a service."""
        # Check minimum interval
        last = self.last_failover.get(service)
        if last:
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed < self.config.min_failover_interval_seconds:
                logger.warning(f"Failover for {service} blocked - too soon after last failover")
                return False
        
        current_primary = self.active_primaries.get(service)
        new_primary = await self._select_new_primary(service)
        
        if not new_primary:
            logger.error(f"No healthy replica available for failover in {service}")
            return False
        
        start_time = time.time()
        event = FailoverEvent(
            event_id=f"{service}_{int(time.time())}",
            timestamp=datetime.now(),
            from_node=current_primary or "none",
            to_node=new_primary,
            reason=reason,
            duration_ms=0,
            success=False
        )
        
        try:
            logger.warning(f"Failing over {service}: {current_primary} -> {new_primary}")
            
            # Update active primary
            self.active_primaries[service] = new_primary
            self.last_failover[service] = datetime.now()
            
            # Update node roles
            if current_primary and current_primary in self.nodes[service]:
                self.nodes[service][current_primary].role = NodeRole.REPLICA
            
            self.nodes[service][new_primary].role = NodeRole.PRIMARY
            self.health[service][new_primary].status = NodeStatus.PROMOTING
            
            event.success = True
            event.duration_ms = (time.time() - start_time) * 1000
            
            logger.info(f"Failover completed: {new_primary} is now primary for {service}")
            
            # Send notifications
            await self._notify_failover(event)
            
            return True
            
        except Exception as e:
            event.error = str(e)
            event.duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Failover failed: {e}")
            return False
        
        finally:
            self.events.append(event)
            for callback in self._callbacks:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Failover callback error: {e}")
    
    async def _select_new_primary(self, service: str) -> Optional[str]:
        """Select best replica to promote to primary."""
        candidates = []
        
        for node_id, node in self.nodes.get(service, {}).items():
            if node_id == self.active_primaries.get(service):
                continue  # Skip current primary
            
            health = self.health[service].get(node_id)
            if health and health.status == NodeStatus.HEALTHY:
                candidates.append((node, health))
        
        if not candidates:
            return None
        
        # Sort by priority (descending), then by response time (ascending)
        candidates.sort(key=lambda x: (-x[0].priority, x[1].response_time_ms))
        
        return candidates[0][0].node_id
    
    async def _check_failback(self, service: str) -> None:
        """Check if failback to original primary is possible."""
        original_primary = f"{service}_primary"
        current_primary = self.active_primaries.get(service)
        
        if current_primary == original_primary:
            return  # Already on original primary
        
        original_health = self.health[service].get(original_primary)
        if original_health and original_health.status == NodeStatus.HEALTHY:
            logger.info(f"Original primary {original_primary} is healthy, initiating failback")
            await self._trigger_failover(service, FailoverReason.SCHEDULED)
    
    async def _notify_failover(self, event: FailoverEvent) -> None:
        """Send failover notification."""
        if not self.config.notification_webhook:
            return
        
        payload = {
            "event": "failover",
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "from_node": event.from_node,
            "to_node": event.to_node,
            "reason": event.reason.value,
            "success": event.success,
            "duration_ms": event.duration_ms,
            "error": event.error
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.config.notification_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except Exception as e:
            logger.error(f"Failed to send failover notification: {e}")
    
    async def get_connection(self, service: str, prefer_primary: bool = True):
        """
        Get the best available connection for a service.
        
        Args:
            service: Service name
            prefer_primary: Whether to prefer primary over replicas
        
        Returns:
            Connection object or None
        """
        if service not in self.nodes:
            return None
        
        if prefer_primary:
            primary_id = self.active_primaries.get(service)
            if primary_id:
                health = self.health[service].get(primary_id)
                if health and health.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED):
                    return self.nodes[service][primary_id].connection
        
        # Fallback to any healthy node
        for node_id, health in self.health.get(service, {}).items():
            if health.status == NodeStatus.HEALTHY:
                return self.nodes[service][node_id].connection
        
        # Last resort: any degraded node
        for node_id, health in self.health.get(service, {}).items():
            if health.status == NodeStatus.DEGRADED:
                return self.nodes[service][node_id].connection
        
        return None
    
    async def get_read_connection(self, service: str):
        """Get connection suitable for read operations (prefers replicas)."""
        if service not in self.nodes:
            return None
        
        # Prefer healthy replicas
        for node_id, node in self.nodes.get(service, {}).items():
            if node.role == NodeRole.REPLICA:
                health = self.health[service].get(node_id)
                if health and health.status == NodeStatus.HEALTHY:
                    return node.connection
        
        # Fallback to primary
        return await self.get_connection(service, prefer_primary=True)
    
    async def manual_failover(self, service: str, target_node: str = None) -> bool:
        """
        Manually trigger failover.
        
        Args:
            service: Service to failover
            target_node: Specific node to promote (optional)
        
        Returns:
            True if failover succeeded
        """
        if target_node:
            # Verify target node exists and is healthy
            if target_node not in self.nodes.get(service, {}):
                raise ValueError(f"Node {target_node} not found")
            
            health = self.health[service].get(target_node)
            if not health or health.status != NodeStatus.HEALTHY:
                raise ValueError(f"Node {target_node} is not healthy")
            
            # Temporarily boost priority
            self.nodes[service][target_node].priority = 1000
        
        result = await self._trigger_failover(service, FailoverReason.MANUAL)
        
        if target_node:
            # Reset priority
            self.nodes[service][target_node].priority = 50
        
        return result
    
    def on_failover(self, callback: Callable[[FailoverEvent], Awaitable[None]]) -> None:
        """Register a callback for failover events."""
        self._callbacks.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all services and nodes."""
        status = {}
        
        for service in self.nodes:
            nodes_status = {}
            
            for node_id, node in self.nodes[service].items():
                health = self.health[service].get(node_id)
                nodes_status[node_id] = {
                    "role": node.role.value,
                    "endpoint": node.endpoint,
                    "status": health.status.value if health else "unknown",
                    "is_active_primary": self.active_primaries.get(service) == node_id,
                    "response_time_ms": health.response_time_ms if health else None,
                    "last_healthy": health.last_healthy.isoformat() if health and health.last_healthy else None
                }
            
            status[service] = {
                "active_primary": self.active_primaries.get(service),
                "nodes": nodes_status,
                "last_failover": self.last_failover.get(service, None)
            }
        
        return status
    
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent failover events."""
        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "from_node": e.from_node,
                "to_node": e.to_node,
                "reason": e.reason.value,
                "success": e.success,
                "duration_ms": e.duration_ms,
                "error": e.error
            }
            for e in sorted(self.events, key=lambda x: x.timestamp, reverse=True)[:limit]
        ]


# FastAPI integration
def setup_failover_routes(app, manager: FailoverManager):
    """Add failover management endpoints to FastAPI app."""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/failover", tags=["failover"])
    
    class ManualFailoverRequest(BaseModel):
        target_node: Optional[str] = None
    
    @router.get("/status")
    async def get_status():
        """Get failover status for all services."""
        return manager.get_status()
    
    @router.get("/status/{service}")
    async def get_service_status(service: str):
        """Get failover status for a specific service."""
        status = manager.get_status()
        if service not in status:
            raise HTTPException(404, f"Service not found: {service}")
        return status[service]
    
    @router.get("/events")
    async def get_events(limit: int = 10):
        """Get recent failover events."""
        return manager.get_recent_events(limit)
    
    @router.post("/trigger/{service}")
    async def trigger_failover(service: str, request: ManualFailoverRequest = None):
        """Manually trigger failover for a service."""
        try:
            target = request.target_node if request else None
            success = await manager.manual_failover(service, target)
            return {"success": success, "service": service}
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))
    
    @router.post("/start-monitoring")
    async def start_monitoring():
        """Start failover monitoring."""
        await manager.start_monitoring()
        return {"status": "monitoring started"}
    
    @router.post("/stop-monitoring")
    async def stop_monitoring():
        """Stop failover monitoring."""
        await manager.stop_monitoring()
        return {"status": "monitoring stopped"}
    
    app.include_router(router)
