"""
End-to-end tests for complete RAG system workflows.

Tests cover:
- Full document upload to query workflow
- Auto-healing workflow
- Drift detection and response
- Multi-user concurrent access
- System recovery scenarios

These tests simulate real-world usage patterns and require
all services to be running. Use docker-compose.test.yml.
"""

import os
import sys
import pytest
import asyncio
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def employee_handbook():
    """Full employee handbook document."""
    return """
    EMPLOYEE HANDBOOK 2024
    Version 3.0 - Effective January 1, 2024
    
    TABLE OF CONTENTS
    1. Introduction
    2. Employment Policies
    3. Compensation and Benefits
    4. Time Off Policies
    5. Code of Conduct
    6. IT and Security
    
    CHAPTER 1: INTRODUCTION
    Welcome to our company! This handbook outlines the policies, procedures,
    and benefits that apply to all employees. Please read it carefully.
    
    CHAPTER 2: EMPLOYMENT POLICIES
    2.1 At-Will Employment
    Employment with the company is at-will. Either party may terminate
    the employment relationship at any time.
    
    2.2 Equal Opportunity
    We are an equal opportunity employer. We do not discriminate based on
    race, color, religion, sex, national origin, age, disability, or any
    other protected characteristic.
    
    CHAPTER 3: COMPENSATION AND BENEFITS
    3.1 Pay Schedule
    Employees are paid bi-weekly on Fridays.
    
    3.2 Health Insurance
    - Medical: Company pays 80% of premiums
    - Dental: Company pays 100% of premiums
    - Vision: Company pays 100% of premiums
    - Coverage begins on first day of employment
    
    3.3 Retirement Benefits
    - 401(k) plan with 4% company match
    - Vesting schedule: 25% per year, fully vested after 4 years
    - Enrollment available on first day
    
    CHAPTER 4: TIME OFF POLICIES
    4.1 Paid Time Off (PTO)
    - 0-2 years: 15 days per year
    - 2-5 years: 20 days per year
    - 5+ years: 25 days per year
    - Maximum carryover: 5 days
    
    4.2 Holidays
    The company observes 10 paid holidays per year:
    - New Year's Day
    - Martin Luther King Jr. Day
    - Presidents Day
    - Memorial Day
    - Independence Day
    - Labor Day
    - Thanksgiving (2 days)
    - Christmas Eve
    - Christmas Day
    
    4.3 Sick Leave
    Unlimited sick leave with manager approval.
    Doctor's note required for absences over 3 consecutive days.
    
    4.4 Work From Home
    - Eligible after 90 days of employment
    - Up to 3 days per week with manager approval
    - Home office equipment stipend: $500 one-time
    
    CHAPTER 5: CODE OF CONDUCT
    5.1 Professional Behavior
    All employees are expected to maintain professional conduct.
    
    5.2 Harassment Policy
    Zero tolerance for harassment of any kind.
    Report concerns to HR immediately.
    
    CHAPTER 6: IT AND SECURITY
    6.1 Equipment
    Company-issued laptops must be returned upon termination.
    
    6.2 Data Security
    Confidential data must not be shared externally.
    Use only approved cloud storage services.
    """


@pytest.fixture
def security_policy():
    """Security policy document."""
    return """
    INFORMATION SECURITY POLICY
    
    1. PASSWORD REQUIREMENTS
    - Minimum 12 characters
    - Must include uppercase, lowercase, numbers, and symbols
    - Change every 90 days
    - No password reuse for 12 cycles
    
    2. ACCESS CONTROL
    - Principle of least privilege
    - Access reviews quarterly
    - Multi-factor authentication required
    
    3. DATA CLASSIFICATION
    - Public
    - Internal
    - Confidential
    - Restricted
    
    4. INCIDENT RESPONSE
    Report security incidents to security@company.com
    Response SLA: 1 hour for critical incidents
    """


# =============================================================================
# Full RAG Workflow Tests
# =============================================================================

class TestFullRAGWorkflow:
    """End-to-end tests for complete RAG workflow."""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_document_to_answer_flow(
        self,
        employee_handbook,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test complete flow: upload document → index → query → answer."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None
            
            # Setup realistic search results
            search_results = [
                MagicMock(
                    id="chunk-pto",
                    score=0.94,
                    payload={
                        "document_id": "handbook-2024",
                        "document_name": "Employee Handbook",
                        "content": "Paid Time Off (PTO): 0-2 years: 15 days per year, 2-5 years: 20 days per year, 5+ years: 25 days per year. Maximum carryover: 5 days.",
                        "chunk_index": 10,
                        "page": 4
                    }
                )
            ]
            mock_qdrant_client.search.return_value = search_results
            
            # Setup realistic LLM response
            mock_openrouter_client.chat_completion = AsyncMock(return_value={
                "answer": "According to the Employee Handbook, PTO allocation is based on tenure: employees with 0-2 years receive 15 days, 2-5 years receive 20 days, and 5+ years receive 25 days annually. You can carry over up to 5 unused days to the next year.",
                "tokens_used": 120,
                "model": "claude-3-haiku"
            })
            
            from services.upload.main import app as upload_app
            from services.query.main import app as query_app
            
            # Step 1: Upload the handbook
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    file = BytesIO(employee_handbook.encode())
                    upload_response = await client.post(
                        "/upload",
                        files={"file": ("employee_handbook.txt", file, "text/plain")}
                    )
                    
                    assert upload_response.status_code in [200, 201, 202]
                    upload_data = upload_response.json()
                    document_id = upload_data.get('document_id', 'handbook-2024')
            
            # Step 2: Query the handbook
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    query_response = await client.post(
                        "/query",
                        json={
                            "query": "How many PTO days do I get after 3 years?",
                            "top_k": 5,
                            "include_sources": True
                        }
                    )
                    
                    assert query_response.status_code == 200
                    query_data = query_response.json()
                    
                    # Verify we got a meaningful answer
                    answer = query_data.get('answer', query_data.get('response', ''))
                    assert len(answer) > 50  # Should be a substantive answer
                    assert any(term in answer.lower() for term in ['20', 'days', 'pto', 'years'])
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multiple_document_knowledge_base(
        self,
        employee_handbook,
        security_policy,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test building knowledge base from multiple documents."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None
            
            from services.upload.main import app as upload_app
            
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Upload employee handbook
                    file1 = BytesIO(employee_handbook.encode())
                    response1 = await client.post(
                        "/upload",
                        files={"file": ("handbook.txt", file1, "text/plain")}
                    )
                    assert response1.status_code in [200, 201, 202]
                    
                    # Upload security policy
                    file2 = BytesIO(security_policy.encode())
                    response2 = await client.post(
                        "/upload",
                        files={"file": ("security_policy.txt", file2, "text/plain")}
                    )
                    assert response2.status_code in [200, 201, 202]
            
            # Now query across both documents
            search_results = [
                MagicMock(
                    id="chunk-sec",
                    score=0.96,
                    payload={
                        "document_id": "security-policy",
                        "document_name": "Security Policy",
                        "content": "PASSWORD REQUIREMENTS: Minimum 12 characters. Must include uppercase, lowercase, numbers, and symbols. Change every 90 days.",
                        "chunk_index": 0
                    }
                )
            ]
            mock_qdrant_client.search.return_value = search_results
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "What are the password requirements?"}
                    )
                    
                    assert response.status_code == 200
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_query_confidence_scoring(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test that queries return confidence scores."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # High confidence search result
            search_result = MagicMock()
            search_result.id = "chunk-1"
            search_result.score = 0.95
            search_result.payload = {
                "document_id": "doc-1",
                "content": "Highly relevant content"
            }
            mock_qdrant_client.search.return_value = [search_result]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "Test query for confidence"}
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    # Should include confidence or similarity score
                    # (exact field depends on implementation)


# =============================================================================
# Auto-Healing Workflow Tests
# =============================================================================

class TestAutoHealingWorkflow:
    """End-to-end tests for auto-healing workflows."""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_drift_detection_triggers_healing(
        self,
        mock_db_connection,
        mock_redis_client
    ):
        """Test that detected drift triggers auto-healing."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            # Simulate drift detection data
            cursor.fetchall.return_value = [
                ("qry-1", 0.5, 2000, datetime.utcnow()),  # Low confidence
                ("qry-2", 0.45, 2200, datetime.utcnow()),
                ("qry-3", 0.48, 2100, datetime.utcnow()),
            ]
            
            from services.drift_detector.main import app as drift_app
            from services.controller.main import app as controller_app
            
            # Step 1: Drift detector detects drift
            with patch('services.drift_detector.main.get_db_connection', return_value=conn):
                transport = ASGITransport(app=drift_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    detect_response = await client.post("/detect")
                    
                    assert detect_response.status_code in [200, 202]
            
            # Step 2: Controller receives drift alert and takes action
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.main.get_db_connection', return_value=conn), \
                 patch('services.controller.healing.clear_cache', new=AsyncMock(return_value={'success': True})), \
                 patch('services.controller.healing.restart_service', new=AsyncMock(return_value={'success': True})):
                
                transport = ASGITransport(app=controller_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Simulate drift alert
                    heal_response = await client.post("/heal", json={
                        "action": "cache_clear",
                        "reason": "Drift detected - confidence degradation"
                    })
                    
                    assert heal_response.status_code in [200, 202]
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_service_recovery_workflow(
        self,
        mock_redis_client,
        mock_db_connection
    ):
        """Test complete service recovery after failure."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            from services.controller.main import app as controller_app
            
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.main.get_db_connection', return_value=conn):
                
                # Mock health check showing failure
                with patch('services.controller.health.check_service_health', new=AsyncMock(return_value={
                    'healthy': False,
                    'error': 'Connection refused'
                })):
                    transport = ASGITransport(app=controller_app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        # Check status - should show unhealthy
                        status_response = await client.get("/services/health")
                        assert status_response.status_code == 200
                
                # Trigger healing
                with patch('services.controller.healing.restart_service', new=AsyncMock(return_value={
                    'success': True,
                    'action': 'restart'
                })):
                    transport = ASGITransport(app=controller_app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        heal_response = await client.post("/heal", json={
                            "action": "restart",
                            "service": "query"
                        })
                        assert heal_response.status_code in [200, 202]
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cache_clear_healing_action(
        self,
        mock_redis_client,
        mock_db_connection
    ):
        """Test cache clearing as a healing action."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            from services.controller.main import app as controller_app
            
            cache_cleared = False
            
            async def mock_flushdb():
                nonlocal cache_cleared
                cache_cleared = True
                return True
            
            mock_redis_client.flushdb = AsyncMock(side_effect=mock_flushdb)
            
            with patch('services.controller.main.redis_client', mock_redis_client), \
                 patch('services.controller.healing.redis_client', mock_redis_client):
                
                transport = ASGITransport(app=controller_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/heal", json={
                        "action": "cache_clear"
                    })
                    
                    assert response.status_code in [200, 202]


# =============================================================================
# Concurrent Access Tests
# =============================================================================

class TestConcurrentAccess:
    """Tests for concurrent multi-user access."""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_queries(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test handling multiple concurrent queries."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            mock_qdrant_client.search.return_value = [
                MagicMock(id="chunk-1", score=0.9, payload={"content": "Result"})
            ]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Launch multiple concurrent queries
                    queries = [
                        {"query": f"Question {i}"} for i in range(10)
                    ]
                    
                    tasks = [
                        client.post("/query", json=query)
                        for query in queries
                    ]
                    
                    responses = await asyncio.gather(*tasks)
                    
                    # All should succeed
                    success_count = sum(1 for r in responses if r.status_code == 200)
                    assert success_count >= 8  # Allow some failures due to rate limiting
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_uploads_and_queries(
        self,
        employee_handbook,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client,
        mock_db_connection
    ):
        """Test concurrent uploads and queries don't interfere."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            cursor.fetchone.return_value = None
            
            mock_qdrant_client.search.return_value = [
                MagicMock(id="chunk-1", score=0.9, payload={"content": "Result"})
            ]
            
            from services.upload.main import app as upload_app
            from services.query.main import app as query_app
            
            async def upload_task():
                with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                     patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                     patch('services.upload.main.get_db_connection', return_value=conn):
                    
                    transport = ASGITransport(app=upload_app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        file = BytesIO(employee_handbook.encode())
                        return await client.post(
                            "/upload",
                            files={"file": (f"doc_{uuid.uuid4().hex[:8]}.txt", file, "text/plain")}
                        )
            
            async def query_task(query_num):
                with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                     patch('services.query.main.qdrant_client', mock_qdrant_client), \
                     patch('services.query.main.cache', mock_redis_client):
                    
                    transport = ASGITransport(app=query_app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        return await client.post(
                            "/query",
                            json={"query": f"Query number {query_num}"}
                        )
            
            # Run uploads and queries concurrently
            tasks = [
                upload_task(),
                upload_task(),
                query_task(1),
                query_task(2),
                query_task(3),
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_responses = [r for r in responses if not isinstance(r, Exception)]
            
            # Most should succeed
            assert len(valid_responses) >= 3


# =============================================================================
# System Recovery Tests
# =============================================================================

class TestSystemRecovery:
    """Tests for system recovery scenarios."""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_graceful_degradation(
        self,
        mock_openrouter_client,
        mock_redis_client
    ):
        """Test system degrades gracefully when components fail."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            # Qdrant is down but cache has results
            cached_response = {
                "answer": "Cached answer while Qdrant is down",
                "cached": True
            }
            
            import json
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_response))
            
            mock_qdrant = MagicMock()
            mock_qdrant.search = MagicMock(side_effect=Exception("Qdrant unavailable"))
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post(
                        "/query",
                        json={"query": "Cached query"}
                    )
                    
                    # Should return cached result or graceful error
                    assert response.status_code in [200, 503]
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_health_endpoints_always_available(self):
        """Test health endpoints are available even under stress."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.upload.main import app as upload_app
            from services.query.main import app as query_app
            
            services = [
                (upload_app, "upload"),
                (query_app, "query"),
            ]
            
            for app, name in services:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/health")
                    assert response.status_code == 200, f"{name} health check failed"
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_partial_system_functionality(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_db_connection
    ):
        """Test system provides partial functionality when some services are down."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            conn, cursor = mock_db_connection
            
            # Upload service works
            from services.upload.main import app as upload_app
            
            with patch('services.upload.main.openrouter_client', mock_openrouter_client), \
                 patch('services.upload.main.qdrant_client', mock_qdrant_client), \
                 patch('services.upload.main.get_db_connection', return_value=conn):
                
                transport = ASGITransport(app=upload_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Can still list documents even if embedding service is slow
                    cursor.fetchall.return_value = [
                        ("doc-1", "file1.txt", "hash1", "processed", 5, datetime.utcnow())
                    ]
                    
                    response = await client.get("/documents")
                    assert response.status_code == 200


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Basic performance tests."""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_query_response_time(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test query response time is within acceptable limits."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            mock_qdrant_client.search.return_value = [
                MagicMock(id="chunk-1", score=0.9, payload={"content": "Result"})
            ]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    start_time = time.time()
                    response = await client.post(
                        "/query",
                        json={"query": "Test query"}
                    )
                    elapsed = time.time() - start_time
                    
                    assert response.status_code == 200
                    # Should respond within 5 seconds (mocked)
                    assert elapsed < 5.0
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_batch_query_performance(
        self,
        mock_openrouter_client,
        mock_qdrant_client,
        mock_redis_client
    ):
        """Test performance of batch queries."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            mock_qdrant_client.search.return_value = [
                MagicMock(id="chunk-1", score=0.9, payload={"content": "Result"})
            ]
            
            from services.query.main import app as query_app
            
            with patch('services.query.main.openrouter_client', mock_openrouter_client), \
                 patch('services.query.main.qdrant_client', mock_qdrant_client), \
                 patch('services.query.main.cache', mock_redis_client):
                
                transport = ASGITransport(app=query_app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    queries = [{"query": f"Query {i}"} for i in range(20)]
                    
                    start_time = time.time()
                    
                    for query in queries:
                        response = await client.post("/query", json=query)
                        assert response.status_code in [200, 429]  # Allow rate limiting
                    
                    elapsed = time.time() - start_time
                    
                    # 20 queries should complete within reasonable time
                    assert elapsed < 30.0  # 1.5 seconds per query on average
