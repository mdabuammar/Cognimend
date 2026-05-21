"""
Scalable Qdrant client with connection pooling, load balancing, and failover
"""
import os
import asyncio
import random
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class QdrantNode:
    """Single Qdrant node configuration"""
    host: str
    http_port: int = 6333
    grpc_port: int = 6334
    weight: float = 1.0
    healthy: bool = True
    last_check: float = 0


@dataclass
class CollectionConfig:
    """Collection configuration for optimal performance"""
    name: str
    vector_size: int
    distance: str = "Cosine"  # Cosine, Euclid, Dot
    
    # Sharding
    shard_number: int = 4
    replication_factor: int = 2
    
    # Indexing
    hnsw_m: int = 16
    hnsw_ef_construct: int = 100
    
    # Quantization
    enable_quantization: bool = True
    quantization_type: str = "scalar"  # scalar, product
    
    # On-disk settings
    on_disk_payload: bool = True
    on_disk_vectors: bool = True


class ScalableQdrantClient:
    """
    Production-ready Qdrant client with:
    - Connection pooling
    - Load balancing across cluster nodes
    - Automatic failover
    - Health checks
    - Retry logic
    """
    
    def __init__(
        self,
        nodes: Optional[List[QdrantNode]] = None,
        prefer_grpc: bool = True,
        timeout: float = 30.0,
        max_retries: int = 3,
        health_check_interval: float = 30.0,
    ):
        self.prefer_grpc = prefer_grpc
        self.timeout = timeout
        self.max_retries = max_retries
        self.health_check_interval = health_check_interval
        
        # Initialize nodes from environment or parameters
        if nodes:
            self.nodes = nodes
        else:
            self.nodes = self._nodes_from_env()
        
        self._clients: Dict[str, Any] = {}
        self._healthy_nodes: List[QdrantNode] = list(self.nodes)
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
    
    def _nodes_from_env(self) -> List[QdrantNode]:
        """Load nodes from environment variables"""
        qdrant_url = os.environ.get('QDRANT_URL', 'http://localhost:6333')
        qdrant_hosts = os.environ.get('QDRANT_HOSTS', '')
        
        nodes = []
        
        if qdrant_hosts:
            # Multiple hosts: host1:6333,host2:6333
            for host_port in qdrant_hosts.split(','):
                parts = host_port.strip().split(':')
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 6333
                nodes.append(QdrantNode(host=host, http_port=port))
        else:
            # Single URL
            from urllib.parse import urlparse
            parsed = urlparse(qdrant_url)
            nodes.append(QdrantNode(
                host=parsed.hostname or 'localhost',
                http_port=parsed.port or 6333,
            ))
        
        return nodes
    
    async def _get_client(self, node: QdrantNode):
        """Get or create client for node"""
        key = f"{node.host}:{node.http_port}"
        
        if key not in self._clients:
            async with self._lock:
                if key not in self._clients:
                    try:
                        from qdrant_client import AsyncQdrantClient
                        
                        self._clients[key] = AsyncQdrantClient(
                            host=node.host,
                            port=node.grpc_port if self.prefer_grpc else node.http_port,
                            prefer_grpc=self.prefer_grpc,
                            timeout=self.timeout,
                        )
                    except ImportError:
                        logger.warning("qdrant-client not installed")
                        return None
        
        return self._clients.get(key)
    
    def _select_node(self) -> QdrantNode:
        """Select node using weighted random selection"""
        if not self._healthy_nodes:
            if self.nodes:
                # Fall back to all nodes if none healthy
                self._healthy_nodes = list(self.nodes)
            else:
                raise RuntimeError("No Qdrant nodes configured")
        
        total_weight = sum(n.weight for n in self._healthy_nodes)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for node in self._healthy_nodes:
            cumulative += node.weight
            if r <= cumulative:
                return node
        
        return self._healthy_nodes[-1]
    
    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute operation with retry and failover"""
        last_error = None
        tried_nodes = set()
        
        for attempt in range(self.max_retries):
            node = self._select_node()
            node_key = f"{node.host}:{node.http_port}"
            
            # Avoid retrying same failed node
            while node_key in tried_nodes and len(tried_nodes) < len(self._healthy_nodes):
                node = self._select_node()
                node_key = f"{node.host}:{node.http_port}"
            
            tried_nodes.add(node_key)
            
            try:
                client = await self._get_client(node)
                if client is None:
                    raise RuntimeError("Client not available")
                    
                result = await operation(client, *args, **kwargs)
                node.healthy = True
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Qdrant operation failed on {node.host}: {e}, "
                    f"attempt {attempt + 1}/{self.max_retries}"
                )
                
                # Mark node as unhealthy
                node.healthy = False
                if node in self._healthy_nodes:
                    self._healthy_nodes.remove(node)
                
                # Schedule health check
                asyncio.create_task(self._check_node_health(node))
        
        raise last_error or RuntimeError("All Qdrant nodes failed")
    
    async def _check_node_health(self, node: QdrantNode):
        """Check node health and restore if healthy"""
        import time
        await asyncio.sleep(30)
        
        try:
            client = await self._get_client(node)
            if client:
                await client.get_collections()
                
                node.healthy = True
                node.last_check = time.time()
                
                if node not in self._healthy_nodes:
                    self._healthy_nodes.append(node)
                    logger.info(f"Qdrant node {node.host} restored to healthy pool")
        
        except Exception as e:
            logger.warning(f"Qdrant node {node.host} still unhealthy: {e}")
            asyncio.create_task(self._check_node_health(node))
    
    async def start_health_checks(self):
        """Start periodic health checks"""
        async def _health_loop():
            while True:
                await asyncio.sleep(self.health_check_interval)
                for node in self.nodes:
                    if not node.healthy:
                        await self._check_node_health(node)
        
        self._health_check_task = asyncio.create_task(_health_loop())
    
    async def stop_health_checks(self):
        """Stop health checks"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
    
    async def create_collection(self, config: CollectionConfig):
        """Create optimized collection for scale"""
        
        async def _create(client):
            from qdrant_client.http import models
            
            # Check if exists
            collections = await client.get_collections()
            if any(c.name == config.name for c in collections.collections):
                logger.info(f"Collection {config.name} already exists")
                return
            
            # Quantization config
            quantization = None
            if config.enable_quantization:
                quantization = models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                )
            
            # Create collection
            await client.create_collection(
                collection_name=config.name,
                vectors_config=models.VectorParams(
                    size=config.vector_size,
                    distance=getattr(models.Distance, config.distance.upper()),
                    on_disk=config.on_disk_vectors,
                ),
                shard_number=config.shard_number,
                replication_factor=config.replication_factor,
                hnsw_config=models.HnswConfigDiff(
                    m=config.hnsw_m,
                    ef_construct=config.hnsw_ef_construct,
                    on_disk=True,
                ),
                quantization_config=quantization,
                on_disk_payload=config.on_disk_payload,
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20000,
                    memmap_threshold=50000,
                ),
            )
            
            logger.info(f"Created collection {config.name}")
        
        await self._execute_with_retry(_create)
    
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict] = None,
        with_payload: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search with automatic load balancing"""
        
        async def _search(client):
            from qdrant_client.http import models
            
            # Build filter
            query_filter = None
            if filter_conditions:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                        for key, value in filter_conditions.items()
                    ]
                )
            
            results = await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=with_payload,
                search_params=models.SearchParams(
                    hnsw_ef=128,
                    exact=False,
                ),
            )
            
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "payload": r.payload,
                }
                for r in results
            ]
        
        return await self._execute_with_retry(_search)
    
    async def upsert(
        self,
        collection_name: str,
        points: List[Dict[str, Any]],
        batch_size: int = 100,
    ):
        """Batch upsert with parallel processing"""
        
        async def _upsert_batch(client, batch):
            from qdrant_client.http import models
            
            qdrant_points = [
                models.PointStruct(
                    id=p.get('id'),
                    vector=p.get('vector'),
                    payload=p.get('payload', {}),
                )
                for p in batch
            ]
            
            await client.upsert(
                collection_name=collection_name,
                points=qdrant_points,
                wait=True,
            )
        
        # Process in batches
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            await self._execute_with_retry(_upsert_batch, batch)
    
    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter_conditions: Optional[Dict] = None,
    ):
        """Delete points by ID or filter"""
        
        async def _delete(client):
            from qdrant_client.http import models
            
            if ids:
                await client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=ids),
                )
            elif filter_conditions:
                await client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key=key,
                                    match=models.MatchValue(value=value)
                                )
                                for key, value in filter_conditions.items()
                            ]
                        )
                    ),
                )
        
        await self._execute_with_retry(_delete)
    
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get collection statistics"""
        
        async def _get_info(client):
            info = await client.get_collection(collection_name)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "status": str(info.status),
                "optimizer_status": str(info.optimizer_status),
            }
        
        return await self._execute_with_retry(_get_info)
    
    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster status"""
        
        async def _get_cluster(client):
            info = await client.get_cluster_info()
            return {
                "status": str(info.status),
                "peer_id": info.peer_id,
                "peers": {
                    str(k): str(v) for k, v in (info.peers or {}).items()
                },
            }
        
        try:
            return await self._execute_with_retry(_get_cluster)
        except Exception as e:
            return {"error": str(e), "healthy_nodes": len(self._healthy_nodes)}
    
    async def close(self):
        """Close all client connections"""
        await self.stop_health_checks()
        
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:
                pass
        
        self._clients.clear()


# Global instance
_qdrant_client: Optional[ScalableQdrantClient] = None


async def get_qdrant_client() -> ScalableQdrantClient:
    """Get global Qdrant client instance"""
    global _qdrant_client
    
    if _qdrant_client is None:
        _qdrant_client = ScalableQdrantClient()
        await _qdrant_client.start_health_checks()
    
    return _qdrant_client


async def close_qdrant_client():
    """Close global Qdrant client"""
    global _qdrant_client
    
    if _qdrant_client:
        await _qdrant_client.close()
        _qdrant_client = None
