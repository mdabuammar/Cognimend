"""
Endpoint Tests for All Services
Tests core functionality of each microservice endpoint.

Run with: pytest services/tests/test_endpoints.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))


# ===== FIXTURES =====

@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {'id': 1}
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_db_manager(mock_db_connection):
    """Create a mock database manager."""
    mock_manager = Mock()
    mock_manager.get_connection.return_value = mock_db_connection
    mock_manager.return_connection = Mock()
    return mock_manager


# ===== UPLOAD SERVICE TESTS =====

class TestUploadService:
    """Tests for the Upload Service endpoints."""
    
    @pytest.fixture
    def upload_client(self, mock_db_manager):
        """Create test client for upload service."""
        with patch('services.upload.main.db_manager', mock_db_manager):
            with patch('services.upload.main.qdrant_client', None):
                from services.upload.main import app
                return TestClient(app)
    
    def test_health_check(self, upload_client):
        """Test health check endpoint returns valid response."""
        response = upload_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert data["service"] == "upload"
    
    def test_list_documents_empty(self, upload_client, mock_db_manager):
        """Test listing documents when none exist."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = upload_client.get("/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
    
    def test_upload_unsupported_file_type(self, upload_client):
        """Test upload rejects unsupported file types."""
        from io import BytesIO
        
        response = upload_client.post(
            "/upload",
            files={"file": ("test.xyz", BytesIO(b"test content"), "application/octet-stream")}
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]


# ===== QUERY SERVICE TESTS =====

class TestQueryService:
    """Tests for the Query Service endpoints."""
    
    @pytest.fixture
    def query_client(self, mock_db_manager):
        """Create test client for query service."""
        with patch('services.query.main.db_manager', mock_db_manager):
            with patch('services.query.main.qdrant_client', None):
                from services.query.main import app
                return TestClient(app)
    
    def test_health_check(self, query_client):
        """Test health check endpoint."""
        response = query_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
    
    def test_query_without_documents(self, query_client):
        """Test query when no documents are indexed."""
        response = query_client.post(
            "/query",
            json={"question": "What is AI?", "top_k": 3}
        )
        # Should return 404 or 503 when no documents/qdrant unavailable
        assert response.status_code in [404, 503, 500]
    
    def test_metrics_endpoint(self, query_client, mock_db_manager):
        """Test metrics endpoint returns valid structure."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchone.return_value = {
            'total_queries': 100,
            'avg_confidence': 75.5,
            'avg_latency_ms': 250,
            'cache_hits': 80,
            'last_query_at': None
        }
        
        response = query_client.get("/metrics")
        assert response.status_code == 200


# ===== DRIFT DETECTOR SERVICE TESTS =====

class TestDriftDetectorService:
    """Tests for the Drift Detector Service endpoints."""
    
    @pytest.fixture
    def drift_client(self, mock_db_manager):
        """Create test client for drift detector service."""
        with patch('services.drift_detector.main.db_manager', mock_db_manager):
            from services.drift_detector.main import app
            return TestClient(app)
    
    def test_health_check(self, drift_client):
        """Test health check endpoint."""
        response = drift_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "registered_detectors" in data
    
    def test_list_detectors(self, drift_client):
        """Test listing registered drift detectors."""
        response = drift_client.get("/detectors")
        assert response.status_code == 200
        data = response.json()
        assert "detectors" in data
        assert len(data["detectors"]) >= 3  # data, retrieval, performance
    
    def test_get_status(self, drift_client, mock_db_manager):
        """Test get drift status."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = drift_client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "data_drift" in data
        assert "retrieval_drift" in data
        assert "performance_drift" in data
    
    def test_get_history(self, drift_client, mock_db_manager):
        """Test get drift history."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = drift_client.get("/history")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data


# ===== CONTROLLER SERVICE TESTS =====

class TestControllerService:
    """Tests for the Controller Service endpoints."""
    
    @pytest.fixture
    def controller_client(self, mock_db_manager):
        """Create test client for controller service."""
        with patch('services.controller.main.db_manager', mock_db_manager):
            from services.controller.main import app
            return TestClient(app)
    
    def test_health_check(self, controller_client):
        """Test health check endpoint."""
        response = controller_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
    
    def test_get_config_not_found(self, controller_client, mock_db_manager):
        """Test getting non-existent config returns 404."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchone.return_value = None
        
        response = controller_client.get("/config/nonexistent")
        assert response.status_code == 404
    
    def test_get_actions(self, controller_client, mock_db_manager):
        """Test getting recent actions."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = controller_client.get("/actions")
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
    
    def test_invalid_trigger_action(self, controller_client):
        """Test triggering invalid action returns error."""
        response = controller_client.post("/trigger-action?action_type=invalid_action")
        assert response.status_code == 400


# ===== EVALUATION SERVICE TESTS =====

class TestEvaluationService:
    """Tests for the Evaluation Service endpoints."""
    
    @pytest.fixture
    def eval_client(self, mock_db_manager):
        """Create test client for evaluation service."""
        try:
            import aiohttp  # Check if dependency is available
        except ImportError:
            pytest.skip("aiohttp not installed - skipping evaluation service tests")
        
        with patch('services.evaluation.main.db_manager', mock_db_manager):
            from services.evaluation.main import app
            return TestClient(app)
    
    def test_health_check(self, eval_client):
        """Test health check endpoint."""
        response = eval_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
    
    def test_get_questions(self, eval_client, mock_db_manager):
        """Test getting evaluation questions."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = eval_client.get("/questions")
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
    
    def test_get_benchmark(self, eval_client, mock_db_manager):
        """Test getting benchmark data."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = eval_client.get("/benchmark")
        assert response.status_code == 200
        data = response.json()
        assert "benchmark" in data


# ===== TELEMETRY SERVICE TESTS =====

class TestTelemetryService:
    """Tests for the Telemetry Service endpoints."""
    
    @pytest.fixture
    def telemetry_client(self, mock_db_manager):
        """Create test client for telemetry service."""
        with patch('services.telemetry.main.db_manager', mock_db_manager):
            from services.telemetry.main import app
            return TestClient(app)
    
    def test_health_check(self, telemetry_client):
        """Test health check endpoint."""
        response = telemetry_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_get_recent_queries(self, telemetry_client, mock_db_manager):
        """Test getting recent queries."""
        mock_cursor = mock_db_manager.get_connection().cursor()
        mock_cursor.fetchall.return_value = []
        
        response = telemetry_client.get("/dashboard/recent-queries")
        assert response.status_code == 200
        data = response.json()
        assert "queries" in data


# ===== INTEGRATION TESTS =====

class TestServiceIntegration:
    """Integration tests across services."""
    
    def test_exception_hierarchy(self):
        """Test custom exception hierarchy is properly defined."""
        from services.shared.exceptions import (
            ServiceException,
            DatabaseError,
            QueryError,
            EmbeddingError,
            SearchError,
            DocumentError,
            VectorStoreError
        )
        
        # Test inheritance
        assert issubclass(DatabaseError, ServiceException)
        assert issubclass(QueryError, ServiceException)
        assert issubclass(EmbeddingError, QueryError)
        assert issubclass(SearchError, QueryError)
        assert issubclass(DocumentError, ServiceException)
        assert issubclass(VectorStoreError, ServiceException)
    
    def test_drift_detector_registry(self):
        """Test drift detector registry functionality."""
        from services.drift_detector.main import drift_registry, DriftDetector
        
        # Test listing detectors
        detectors = drift_registry.list_detectors()
        assert len(detectors) >= 3
        
        detector_names = [d['name'] for d in detectors]
        assert 'data_drift' in detector_names
        assert 'retrieval_drift' in detector_names
        assert 'performance_drift' in detector_names
    
    def test_database_manager_pattern(self):
        """Test DatabaseManager pattern is consistently used."""
        import importlib
        
        services = [
            'services.upload.main',
            'services.query.main',
            'services.drift_detector.main',
            'services.controller.main',
            'services.evaluation.main',
            'services.telemetry.main'
        ]
        
        for service_name in services:
            try:
                module = importlib.import_module(service_name)
                assert hasattr(module, 'db_manager'), f"{service_name} missing db_manager"
                assert hasattr(module, 'get_db'), f"{service_name} missing get_db"
                assert hasattr(module, 'return_db'), f"{service_name} missing return_db"
            except ImportError:
                pytest.skip(f"Could not import {service_name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
