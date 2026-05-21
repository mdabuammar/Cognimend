"""
Unit tests for the Drift Detector Service.

Tests cover:
- Drift detection algorithms
- Statistical analysis
- Alert generation
- Threshold management
- Auto-healing triggers
- Anomaly detection

Coverage target: >80%
"""

import os
import sys
import pytest
import json
import statistics
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# =============================================================================
# Drift Detection Algorithm Tests
# =============================================================================

class TestDriftDetectionAlgorithms:
    """Tests for drift detection algorithms."""
    
    @pytest.mark.unit
    def test_calculate_mean_shift(self, sample_drift_data):
        """Test mean shift calculation between time windows."""
        from services.drift_detector.algorithms import calculate_mean_shift
        
        baseline = sample_drift_data['baseline_confidence']
        recent = sample_drift_data['recent_confidence']
        
        shift = calculate_mean_shift(baseline, recent)
        
        assert isinstance(shift, float)
        assert shift != 0  # There should be a noticeable shift in our sample data
    
    @pytest.mark.unit
    def test_calculate_variance_change(self, sample_drift_data):
        """Test variance change detection."""
        from services.drift_detector.algorithms import calculate_variance_change
        
        baseline = sample_drift_data['baseline_confidence']
        recent = sample_drift_data['recent_confidence']
        
        variance_change = calculate_variance_change(baseline, recent)
        
        assert isinstance(variance_change, float)
    
    @pytest.mark.unit
    def test_population_stability_index(self, sample_drift_data):
        """Test Population Stability Index (PSI) calculation."""
        from services.drift_detector.algorithms import calculate_psi
        
        baseline = sample_drift_data['baseline_confidence']
        recent = sample_drift_data['recent_confidence']
        
        psi = calculate_psi(baseline, recent)
        
        assert isinstance(psi, float)
        assert psi >= 0  # PSI is always non-negative
    
    @pytest.mark.unit
    @pytest.mark.parametrize("baseline,recent,expected_drift", [
        ([0.9, 0.9, 0.9, 0.9, 0.9], [0.9, 0.9, 0.9, 0.9, 0.9], False),  # No drift
        ([0.9, 0.9, 0.9, 0.9, 0.9], [0.5, 0.4, 0.5, 0.4, 0.5], True),   # Clear drift
        ([0.8, 0.85, 0.82, 0.87, 0.83], [0.78, 0.82, 0.80, 0.84, 0.81], False),  # Minor variation
    ])
    def test_detect_drift(self, baseline, recent, expected_drift):
        """Test drift detection with various scenarios."""
        from services.drift_detector.algorithms import detect_drift
        
        result = detect_drift(baseline, recent, threshold=0.1)
        
        assert result['drift_detected'] == expected_drift
    
    @pytest.mark.unit
    def test_detect_drift_empty_data(self):
        """Test drift detection with empty data."""
        from services.drift_detector.algorithms import detect_drift
        
        with pytest.raises((ValueError, ZeroDivisionError)):
            detect_drift([], [])
    
    @pytest.mark.unit
    def test_detect_drift_single_value(self):
        """Test drift detection with single values."""
        from services.drift_detector.algorithms import detect_drift
        
        # Should handle gracefully or raise appropriate error
        try:
            result = detect_drift([0.9], [0.5])
            assert 'drift_detected' in result
        except (ValueError, ZeroDivisionError):
            pass  # Acceptable to raise error for insufficient data
    
    @pytest.mark.unit
    def test_kolmogorov_smirnov_test(self, sample_drift_data):
        """Test Kolmogorov-Smirnov statistical test."""
        from services.drift_detector.algorithms import ks_test
        
        baseline = sample_drift_data['baseline_confidence']
        recent = sample_drift_data['recent_confidence']
        
        statistic, p_value = ks_test(baseline, recent)
        
        assert 0 <= statistic <= 1
        assert 0 <= p_value <= 1


# =============================================================================
# Latency Drift Tests
# =============================================================================

class TestLatencyDrift:
    """Tests for latency-based drift detection."""
    
    @pytest.mark.unit
    def test_detect_latency_drift(self, sample_drift_data):
        """Test latency drift detection."""
        from services.drift_detector.algorithms import detect_latency_drift
        
        baseline = sample_drift_data['baseline_latency']
        recent = sample_drift_data['recent_latency']
        
        result = detect_latency_drift(baseline, recent)
        
        assert 'drift_detected' in result
        assert 'mean_increase_percent' in result
    
    @pytest.mark.unit
    @pytest.mark.parametrize("baseline,recent,expected_drift", [
        ([1000, 1000, 1000], [1000, 1000, 1000], False),  # No drift
        ([1000, 1000, 1000], [2000, 2000, 2000], True),   # 100% increase
        ([1000, 1000, 1000], [1100, 1100, 1100], False),  # 10% increase (within threshold)
    ])
    def test_latency_drift_scenarios(self, baseline, recent, expected_drift):
        """Test latency drift with various scenarios."""
        from services.drift_detector.algorithms import detect_latency_drift
        
        result = detect_latency_drift(baseline, recent, threshold_percent=20)
        
        assert result['drift_detected'] == expected_drift
    
    @pytest.mark.unit
    def test_latency_percentile_analysis(self, sample_drift_data):
        """Test percentile-based latency analysis."""
        from services.drift_detector.algorithms import analyze_latency_percentiles
        
        latencies = sample_drift_data['recent_latency']
        
        result = analyze_latency_percentiles(latencies)
        
        assert 'p50' in result
        assert 'p90' in result
        assert 'p99' in result
        assert result['p90'] >= result['p50']


# =============================================================================
# Anomaly Detection Tests
# =============================================================================

class TestAnomalyDetection:
    """Tests for anomaly detection functionality."""
    
    @pytest.mark.unit
    def test_detect_outliers_zscore(self):
        """Test outlier detection using z-score method."""
        from services.drift_detector.anomaly import detect_outliers_zscore
        
        data = [10, 11, 10, 12, 11, 10, 100, 10, 11]  # 100 is an outlier
        
        outliers = detect_outliers_zscore(data, threshold=2.0)
        
        assert 100 in outliers or 6 in outliers  # Either value or index
    
    @pytest.mark.unit
    def test_detect_outliers_iqr(self):
        """Test outlier detection using IQR method."""
        from services.drift_detector.anomaly import detect_outliers_iqr
        
        data = [10, 11, 10, 12, 11, 10, 100, 10, 11]
        
        outliers = detect_outliers_iqr(data)
        
        assert len(outliers) > 0  # Should detect at least one outlier
    
    @pytest.mark.unit
    def test_no_outliers_normal_data(self):
        """Test that normal data has no outliers."""
        from services.drift_detector.anomaly import detect_outliers_zscore
        
        data = [10, 10.5, 11, 10.2, 10.8, 11.1, 10.3]
        
        outliers = detect_outliers_zscore(data, threshold=3.0)
        
        assert len(outliers) == 0
    
    @pytest.mark.unit
    def test_anomaly_score_calculation(self):
        """Test anomaly score calculation."""
        from services.drift_detector.anomaly import calculate_anomaly_score
        
        baseline_mean = 0.85
        baseline_std = 0.05
        current_value = 0.5
        
        score = calculate_anomaly_score(current_value, baseline_mean, baseline_std)
        
        assert score > 2.0  # Should be more than 2 standard deviations


# =============================================================================
# Alert Generation Tests
# =============================================================================

class TestAlertGeneration:
    """Tests for alert generation."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_drift_alert(self):
        """Test drift alert generation."""
        from services.drift_detector.alerts import generate_alert
        
        drift_result = {
            'drift_detected': True,
            'drift_type': 'confidence',
            'severity': 'high',
            'mean_shift': -0.15,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        alert = await generate_alert(drift_result)
        
        assert 'alert_id' in alert
        assert 'severity' in alert
        assert 'message' in alert
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_alert_when_no_drift(self):
        """Test that no alert is generated when there's no drift."""
        from services.drift_detector.alerts import generate_alert
        
        drift_result = {
            'drift_detected': False,
            'drift_type': 'confidence',
            'mean_shift': -0.02,
        }
        
        alert = await generate_alert(drift_result)
        
        assert alert is None or alert.get('severity') == 'info'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.parametrize("severity,expected_priority", [
        ("critical", 1),
        ("high", 2),
        ("medium", 3),
        ("low", 4),
    ])
    async def test_alert_priority_mapping(self, severity, expected_priority):
        """Test alert priority based on severity."""
        from services.drift_detector.alerts import get_alert_priority
        
        priority = get_alert_priority(severity)
        
        assert priority == expected_priority
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_alert_contains_required_fields(self):
        """Test that alerts contain all required fields."""
        from services.drift_detector.alerts import generate_alert
        
        drift_result = {
            'drift_detected': True,
            'drift_type': 'latency',
            'severity': 'medium',
            'mean_increase_percent': 45,
        }
        
        alert = await generate_alert(drift_result)
        
        required_fields = ['alert_id', 'timestamp', 'severity', 'message', 'drift_type']
        for field in required_fields:
            assert field in alert, f"Missing required field: {field}"


# =============================================================================
# Threshold Management Tests
# =============================================================================

class TestThresholdManagement:
    """Tests for threshold configuration and management."""
    
    @pytest.mark.unit
    def test_get_default_thresholds(self):
        """Test getting default threshold values."""
        from services.drift_detector.thresholds import get_default_thresholds
        
        thresholds = get_default_thresholds()
        
        assert 'confidence_drift' in thresholds
        assert 'latency_drift_percent' in thresholds
        assert 'error_rate' in thresholds
    
    @pytest.mark.unit
    def test_update_thresholds(self):
        """Test updating threshold values."""
        from services.drift_detector.thresholds import update_threshold, get_threshold
        
        update_threshold('confidence_drift', 0.15)
        
        assert get_threshold('confidence_drift') == 0.15
    
    @pytest.mark.unit
    def test_invalid_threshold_raises_error(self):
        """Test that invalid threshold values raise errors."""
        from services.drift_detector.thresholds import update_threshold
        
        with pytest.raises(ValueError):
            update_threshold('confidence_drift', -0.5)  # Negative not allowed
    
    @pytest.mark.unit
    def test_unknown_threshold_raises_error(self):
        """Test that unknown threshold names raise errors."""
        from services.drift_detector.thresholds import get_threshold
        
        with pytest.raises(KeyError):
            get_threshold('unknown_threshold')


# =============================================================================
# Auto-Healing Trigger Tests
# =============================================================================

class TestAutoHealingTriggers:
    """Tests for auto-healing trigger functionality."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trigger_auto_healing_on_drift(self):
        """Test that auto-healing is triggered on critical drift."""
        from services.drift_detector.healing import should_trigger_healing
        
        drift_result = {
            'drift_detected': True,
            'severity': 'critical',
            'drift_type': 'confidence',
            'mean_shift': -0.25,
        }
        
        should_heal = should_trigger_healing(drift_result)
        
        assert should_heal is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_healing_on_minor_drift(self):
        """Test that minor drift doesn't trigger healing."""
        from services.drift_detector.healing import should_trigger_healing
        
        drift_result = {
            'drift_detected': True,
            'severity': 'low',
            'drift_type': 'confidence',
            'mean_shift': -0.05,
        }
        
        should_heal = should_trigger_healing(drift_result)
        
        assert should_heal is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_healing_action_reindex(self):
        """Test reindex healing action."""
        from services.drift_detector.healing import get_healing_action
        
        drift_result = {
            'drift_detected': True,
            'severity': 'high',
            'drift_type': 'embedding_quality',
        }
        
        action = get_healing_action(drift_result)
        
        assert action['type'] in ['reindex', 'cache_clear', 'model_refresh', 'scale_up']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_healing_cooldown(self):
        """Test that healing has a cooldown period."""
        from services.drift_detector.healing import is_in_cooldown, set_cooldown
        
        # Set cooldown
        set_cooldown('reindex', timedelta(minutes=30))
        
        # Should be in cooldown immediately after setting
        in_cooldown = is_in_cooldown('reindex')
        
        assert in_cooldown is True


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestDriftDetectorAPI:
    """Tests for drift detector API endpoints."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.drift_detector.main import app
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                
                assert response.status_code == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_drift_endpoint(self, mock_db_connection):
        """Test drift detection endpoint."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.drift_detector.main import app
            
            conn, cursor = mock_db_connection
            # Return sample query logs
            cursor.fetchall.return_value = [
                ("qry-1", 0.85, 1000, datetime.utcnow()),
                ("qry-2", 0.87, 1100, datetime.utcnow()),
            ]
            
            with patch('services.drift_detector.main.get_db_connection', return_value=conn):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/detect")
                    
                    assert response.status_code in [200, 202]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_drift_status(self, mock_db_connection):
        """Test getting current drift status."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.drift_detector.main import app
            
            conn, cursor = mock_db_connection
            
            with patch('services.drift_detector.main.get_db_connection', return_value=conn):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/status")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert 'status' in data
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_alerts(self, mock_db_connection):
        """Test getting drift alerts."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.drift_detector.main import app
            
            conn, cursor = mock_db_connection
            cursor.fetchall.return_value = []
            
            with patch('services.drift_detector.main.get_db_connection', return_value=conn):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/alerts")
                    
                    assert response.status_code == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_thresholds_endpoint(self, mock_db_connection):
        """Test updating thresholds via API."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            from services.drift_detector.main import app
            
            conn, cursor = mock_db_connection
            
            with patch('services.drift_detector.main.get_db_connection', return_value=conn):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.put("/thresholds", json={
                        "confidence_drift": 0.12,
                        "latency_drift_percent": 25
                    })
                    
                    assert response.status_code in [200, 204]


# =============================================================================
# Integration with Telemetry Tests
# =============================================================================

class TestTelemetryIntegration:
    """Tests for integration with telemetry service."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_telemetry_data(self, mock_db_connection):
        """Test fetching telemetry data for analysis."""
        from services.drift_detector.telemetry import fetch_recent_metrics
        
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            (0.85, 1000, datetime.utcnow()),
            (0.87, 1100, datetime.utcnow()),
        ]
        
        with patch('services.drift_detector.telemetry.get_db_connection', return_value=conn):
            metrics = await fetch_recent_metrics(hours=24)
            
            assert 'confidence' in metrics
            assert 'latency' in metrics
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_aggregate_telemetry_by_time_window(self, sample_telemetry_logs):
        """Test aggregating telemetry by time windows."""
        from services.drift_detector.telemetry import aggregate_by_window
        
        aggregated = aggregate_by_window(sample_telemetry_logs, window_hours=1)
        
        assert isinstance(aggregated, list)
        for window in aggregated:
            assert 'mean_confidence' in window
            assert 'mean_latency' in window
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_compare_time_windows(self):
        """Test comparing baseline vs recent time windows."""
        from services.drift_detector.telemetry import compare_windows
        
        baseline = {'mean_confidence': 0.88, 'mean_latency': 1000}
        recent = {'mean_confidence': 0.72, 'mean_latency': 1500}
        
        comparison = compare_windows(baseline, recent)
        
        assert 'confidence_change' in comparison
        assert 'latency_change' in comparison
        assert comparison['confidence_change'] < 0  # Decreased
        assert comparison['latency_change'] > 0  # Increased
