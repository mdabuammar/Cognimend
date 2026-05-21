"""
Unit tests for the Controller Service.

Tests cover:
- Autonomous operations orchestration
- Service health monitoring
- Auto-scaling decisions
- Healing actions execution
- Workflow coordination
- State management

Coverage target: >80%
"""

import os
import sys
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# =============================================================================
# Service Health Monitoring Tests
# =============================================================================

class TestServiceHealthMonitoring:
    """Tests for service health monitoring."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_all_services_health(self):
        """Test checking health of all services."""
        from services.controller.health import check_all_services
        
        with patch('services.controller.health.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            results = await check_all_services()
            
            assert isinstance(results, dict)
            for service in ['upload', 'query', 'telemetry', 'drift_detector', 'evaluation']:
                assert service in results
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_service_health_success(self):
        """Test checking health of a single service."""
        from services.controller.health import check_service_health
        
        with patch('services.controller.health.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await check_service_health('upload', 'http://localhost:8001')
            
            assert result['healthy'] is True
            assert result['service'] == 'upload'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_service_health_failure(self):
        """Test handling unhealthy service."""
        from services.controller.health import check_service_health
        
        with patch('services.controller.health.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            
            result = await check_service_health('upload', 'http://localhost:8001')
            
            assert result['healthy'] is False
            assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check with timeout."""
        from services.controller.health import check_service_health
        
        with patch('services.controller.health.httpx.AsyncClient') as mock_client:
            import asyncio
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            
            result = await check_service_health('upload', 'http://localhost:8001', timeout=1)
            
            assert result['healthy'] is False
            assert 'timeout' in result.get('error', '').lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_aggregate_health_status(self):
        """Test aggregating health status across services."""
        from services.controller.health import aggregate_health
        
        service_health = {
            'upload': {'healthy': True, 'latency_ms': 50},
            'query': {'healthy': True, 'latency_ms': 45},
            'telemetry': {'healthy': False, 'error': 'Connection refused'},
            'drift_detector': {'healthy': True, 'latency_ms': 60},
        }
        
        aggregate = aggregate_health(service_health)
        
        assert aggregate['overall_healthy'] is False  # One service is down
        assert aggregate['healthy_count'] == 3
        assert aggregate['unhealthy_count'] == 1


# =============================================================================
# Auto-Scaling Tests
# =============================================================================

class TestAutoScaling:
    """Tests for auto-scaling functionality."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_scaling_needs_scale_up(self):
        """Test evaluation recommends scale up under high load."""
        from services.controller.scaling import evaluate_scaling_needs
        
        metrics = {
            'cpu_utilization': 85,  # High CPU
            'memory_utilization': 70,
            'request_rate': 1000,
            'latency_p99': 2000,
        }
        
        decision = await evaluate_scaling_needs(metrics)
        
        assert decision['action'] == 'scale_up'
        assert decision['replicas'] > 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_scaling_needs_scale_down(self):
        """Test evaluation recommends scale down under low load."""
        from services.controller.scaling import evaluate_scaling_needs
        
        metrics = {
            'cpu_utilization': 15,  # Low CPU
            'memory_utilization': 20,
            'request_rate': 10,
            'latency_p99': 100,
        }
        
        decision = await evaluate_scaling_needs(metrics)
        
        assert decision['action'] in ['scale_down', 'no_action']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_evaluate_scaling_needs_no_action(self):
        """Test evaluation recommends no action under normal load."""
        from services.controller.scaling import evaluate_scaling_needs
        
        metrics = {
            'cpu_utilization': 50,
            'memory_utilization': 50,
            'request_rate': 500,
            'latency_p99': 500,
        }
        
        decision = await evaluate_scaling_needs(metrics)
        
        assert decision['action'] == 'no_action'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scale_service_up(self):
        """Test scaling a service up."""
        from services.controller.scaling import scale_service
        
        with patch('services.controller.scaling.kubernetes_client') as mock_k8s:
            mock_k8s.scale_deployment = AsyncMock(return_value=True)
            
            result = await scale_service('query', replicas=3)
            
            assert result['success'] is True
            assert result['new_replicas'] == 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scale_service_respects_limits(self):
        """Test scaling respects min/max replica limits."""
        from services.controller.scaling import scale_service
        
        with patch('services.controller.scaling.kubernetes_client') as mock_k8s:
            # Try to scale beyond max
            result = await scale_service('query', replicas=100, max_replicas=10)
            
            # Should cap at max
            assert result['new_replicas'] <= 10
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scaling_cooldown(self):
        """Test scaling respects cooldown period."""
        from services.controller.scaling import can_scale, record_scaling_action
        
        # Record a recent scaling action
        await record_scaling_action('query', 'scale_up')
        
        # Should be in cooldown
        can = await can_scale('query', cooldown_minutes=5)
        
        assert can is False


# =============================================================================
# Healing Actions Tests
# =============================================================================

class TestHealingActions:
    """Tests for auto-healing actions."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_restart_unhealthy_service(self):
        """Test restarting an unhealthy service."""
        from services.controller.healing import restart_service
        
        with patch('services.controller.healing.kubernetes_client') as mock_k8s:
            mock_k8s.rollout_restart = AsyncMock(return_value=True)
            
            result = await restart_service('query')
            
            assert result['action'] == 'restart'
            assert result['success'] is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_clear_cache_action(self):
        """Test cache clearing healing action."""
        from services.controller.healing import clear_cache
        
        with patch('services.controller.healing.redis_client') as mock_redis:
            mock_redis.flushdb = AsyncMock(return_value=True)
            
            result = await clear_cache()
            
            assert result['action'] == 'cache_clear'
            assert result['success'] is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reindex_documents_action(self):
        """Test document reindexing healing action."""
        from services.controller.healing import trigger_reindex
        
        with patch('services.controller.healing.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await trigger_reindex(document_ids=['doc-123'])
            
            assert result['action'] == 'reindex'
            assert result['status'] == 'initiated'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rollback_deployment(self):
        """Test deployment rollback action."""
        from services.controller.healing import rollback_deployment
        
        with patch('services.controller.healing.kubernetes_client') as mock_k8s:
            mock_k8s.rollback_deployment = AsyncMock(return_value={'success': True, 'revision': 5})
            
            result = await rollback_deployment('query')
            
            assert result['action'] == 'rollback'
            assert result['success'] is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_healing_plan(self):
        """Test executing a multi-step healing plan."""
        from services.controller.healing import execute_healing_plan
        
        plan = [
            {'action': 'cache_clear', 'service': 'query'},
            {'action': 'restart', 'service': 'query'},
        ]
        
        with patch('services.controller.healing.clear_cache', new=AsyncMock(return_value={'success': True})), \
             patch('services.controller.healing.restart_service', new=AsyncMock(return_value={'success': True})):
            
            results = await execute_healing_plan(plan)
            
            assert len(results) == 2
            assert all(r['success'] for r in results)


# =============================================================================
# Workflow Coordination Tests
# =============================================================================

class TestWorkflowCoordination:
    """Tests for workflow coordination."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_orchestrate_document_processing(self):
        """Test orchestrating document processing workflow."""
        from services.controller.workflows import orchestrate_document_processing
        
        with patch('services.controller.workflows.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'completed'}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await orchestrate_document_processing('doc-123')
            
            assert result['status'] in ['completed', 'processing']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_orchestrate_drift_response(self):
        """Test orchestrating response to drift detection."""
        from services.controller.workflows import orchestrate_drift_response
        
        drift_alert = {
            'alert_id': 'alert-123',
            'severity': 'high',
            'drift_type': 'confidence',
            'recommended_action': 'reindex'
        }
        
        with patch('services.controller.workflows.execute_healing_plan', new=AsyncMock(return_value=[{'success': True}])):
            result = await orchestrate_drift_response(drift_alert)
            
            assert 'healing_executed' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self):
        """Test workflow state is persisted."""
        from services.controller.workflows import save_workflow_state, get_workflow_state
        
        workflow_id = 'wf-123'
        state = {
            'step': 2,
            'status': 'in_progress',
            'started_at': datetime.utcnow().isoformat()
        }
        
        with patch('services.controller.workflows.redis_client') as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.get = AsyncMock(return_value=json.dumps(state))
            
            await save_workflow_state(workflow_id, state)
            retrieved = await get_workflow_state(workflow_id)
            
            assert retrieved['step'] == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_workflow_failure_handling(self):
        """Test handling workflow step failures."""
        from services.controller.workflows import handle_workflow_failure
        
        failure = {
            'workflow_id': 'wf-123',
            'step': 'reindex',
            'error': 'Connection timeout'
        }
        
        with patch('services.controller.workflows.send_notification', new=AsyncMock()):
            result = await handle_workflow_failure(failure, retry=True)
            
            assert 'retry_scheduled' in result or 'escalated' in result


# =============================================================================
# State Management Tests
# =============================================================================

class TestStateManagement:
    """Tests for controller state management."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_system_state(self, mock_redis_client, mock_db_connection):
        """Test getting overall system state."""
        from services.controller.state import get_system_state
        
        conn, cursor = mock_db_connection
        
        with patch('services.controller.state.redis_client', mock_redis_client), \
             patch('services.controller.state.get_db_connection', return_value=conn):
            
            state = await get_system_state()
            
            assert 'services' in state
            assert 'last_updated' in state
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_system_state(self, mock_redis_client):
        """Test updating system state."""
        from services.controller.state import update_system_state
        
        new_state = {
            'mode': 'maintenance',
            'reason': 'Scheduled maintenance'
        }
        
        with patch('services.controller.state.redis_client', mock_redis_client):
            result = await update_system_state(new_state)
            
            assert result['success'] is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_state_history_tracking(self, mock_db_connection):
        """Test that state changes are tracked in history."""
        from services.controller.state import record_state_change
        
        conn, cursor = mock_db_connection
        
        change = {
            'from_state': 'healthy',
            'to_state': 'degraded',
            'reason': 'High latency detected'
        }
        
        with patch('services.controller.state.get_db_connection', return_value=conn):
            await record_state_change(change)
            
            cursor.execute.assert_called()


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestControllerAPI:
    """Tests for controller API endpoints."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                
                assert response.status_code == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_system_status(self, mock_redis_client, mock_db_connection):
        """Test getting system status."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            conn, cursor = mock_db_connection
            
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/status")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert 'status' in data
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trigger_healing_action(self, mock_redis_client):
        """Test manually triggering healing action."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.healing.restart_service', new=AsyncMock(return_value={'success': True})):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/heal", json={
                        "action": "restart",
                        "service": "query"
                    })
                    
                    assert response.status_code in [200, 202]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scale_service_endpoint(self, mock_redis_client):
        """Test scaling service via API."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.scaling.scale_service', new=AsyncMock(return_value={'success': True, 'new_replicas': 3})):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/scale", json={
                        "service": "query",
                        "replicas": 3
                    })
                    
                    assert response.status_code in [200, 202]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test getting all service health status."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            with patch('services.controller.health.check_all_services', new=AsyncMock(return_value={
                'upload': {'healthy': True},
                'query': {'healthy': True},
            })):
                
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/services/health")
                    
                    assert response.status_code == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_maintenance_mode(self, mock_redis_client):
        """Test setting maintenance mode."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.controller.main import app
            
            with patch('services.controller.main.redis_client', mock_redis_client):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/maintenance", json={
                        "enabled": True,
                        "reason": "Scheduled maintenance"
                    })
                    
                    assert response.status_code in [200, 204]


# =============================================================================
# Background Task Tests
# =============================================================================

class TestBackgroundTasks:
    """Tests for background monitoring tasks."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_periodic_health_check_task(self):
        """Test periodic health check background task."""
        from services.controller.tasks import periodic_health_check
        
        with patch('services.controller.tasks.check_all_services', new=AsyncMock(return_value={
            'upload': {'healthy': True},
            'query': {'healthy': True},
        })):
            result = await periodic_health_check()
            
            assert 'checked_at' in result
            assert 'services' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_periodic_scaling_evaluation(self):
        """Test periodic scaling evaluation task."""
        from services.controller.tasks import periodic_scaling_evaluation
        
        with patch('services.controller.tasks.collect_metrics', new=AsyncMock(return_value={
            'cpu_utilization': 50,
            'memory_utilization': 60,
        })), \
             patch('services.controller.tasks.evaluate_scaling_needs', new=AsyncMock(return_value={'action': 'no_action'})):
            
            result = await periodic_scaling_evaluation()
            
            assert 'evaluated_at' in result
            assert 'decision' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_drift_monitoring_task(self):
        """Test drift monitoring background task."""
        from services.controller.tasks import monitor_drift
        
        with patch('services.controller.tasks.check_drift_detector', new=AsyncMock(return_value={
            'drift_detected': False,
            'last_check': datetime.utcnow().isoformat()
        })):
            result = await monitor_drift()
            
            assert 'drift_status' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_stale_workflows(self, mock_db_connection):
        """Test cleanup of stale workflows."""
        from services.controller.tasks import cleanup_stale_workflows
        
        conn, cursor = mock_db_connection
        cursor.rowcount = 5  # 5 workflows cleaned up
        
        with patch('services.controller.tasks.get_db_connection', return_value=conn):
            result = await cleanup_stale_workflows(max_age_hours=24)
            
            assert result['cleaned_count'] == 5
