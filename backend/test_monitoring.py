#!/usr/bin/env python3
"""
Monitoring System Test & Verification
Tests all monitoring endpoints and features
"""

import requests
import json
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8002"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def test_health():
    """Test health endpoint"""
    print_header("Testing Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        
        status = "✅" if data["status"] == "healthy" else "❌"
        print(f"{status} Service Status: {data['status']}")
        print(f"   Version: {data.get('version', 'N/A')}")
        print(f"   Circuit Breaker: {data.get('circuit_breaker', 'N/A')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_detailed_health():
    """Test detailed health check"""
    print_header("Testing Detailed Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health/detailed")
        data = response.json()
        
        overall = "✅" if data["status"] == "healthy" else "❌"
        print(f"{overall} Overall Status: {data['status']}")
        print(f"\n   Component Status:")
        
        for component, check in data["checks"].items():
            status_icon = "✅" if check["status"] == "healthy" else "❌"
            latency = check.get("latency_ms", "N/A")
            print(f"   {status_icon} {component:12} - {latency}ms")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_sample_query():
    """Send a sample query to generate metrics"""
    print_header("Testing Sample Query")
    
    try:
        payload = {
            "question": "What is a RAG system?",
            "top_k": 3
        }
        
        print(f"📝 Sending query: '{payload['question']}'")
        response = requests.post(f"{BASE_URL}/query", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Query successful!")
            print(f"   Latency: {data.get('latency_ms', 'N/A')}ms")
            print(f"   Confidence: {data.get('confidence', 'N/A')}%")
            print(f"   Cost: ${data.get('cost_usd', 'N/A'):.6f}")
            print(f"   Tokens: {data.get('tokens_used', 'N/A')}")
            print(f"   Cache Hit: {data.get('cache_hit', False)}")
            return True
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"   {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_metrics_summary():
    """Test metrics summary endpoint"""
    print_header("Testing Metrics Summary")
    
    try:
        response = requests.get(f"{BASE_URL}/metrics/summary")
        data = response.json()
        
        print(f"📊 Overview:")
        overview = data.get("overview", {})
        print(f"   Total Queries: {overview.get('total_queries', 0)}")
        print(f"   Successful: {overview.get('successful', 0)}")
        print(f"   Failed: {overview.get('failed', 0)}")
        print(f"   Success Rate: {overview.get('success_rate', 0)}%")
        
        print(f"\n⏱️  Performance:")
        perf = data.get("performance", {})
        print(f"   Avg Latency: {perf.get('avg_latency_ms', 0):.2f}ms")
        print(f"   P50: {perf.get('p50_latency_ms', 0)}ms")
        print(f"   P95: {perf.get('p95_latency_ms', 0)}ms")
        print(f"   P99: {perf.get('p99_latency_ms', 0)}ms")
        
        print(f"\n💾 Cache:")
        cache = data.get("cache", {})
        print(f"   Hit Rate: {cache.get('hit_rate', 0)}%")
        print(f"   Hits: {cache.get('hits', 0)}")
        print(f"   Misses: {cache.get('misses', 0)}")
        
        print(f"\n💰 Costs:")
        costs = data.get("costs", {})
        print(f"   Total: ${costs.get('total_usd', 0):.4f}")
        print(f"   Avg/Query: ${costs.get('avg_per_query', 0):.6f}")
        print(f"   Total Tokens: {costs.get('total_tokens', 0)}")
        
        print(f"\n🎯 SLO Compliance:")
        slo = data.get("slo_compliance", {})
        for metric, status in slo.items():
            icon = "✅" if status.get("met") else "❌"
            current = status.get("current", "N/A")
            target = status.get("target", "N/A")
            print(f"   {icon} {metric}: {current} (target: {target})")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_prometheus_metrics():
    """Test Prometheus format metrics"""
    print_header("Testing Prometheus Metrics")
    
    try:
        response = requests.get(f"{BASE_URL}/metrics/prometheus")
        
        if response.status_code == 200:
            lines = response.text.split('\n')
            print(f"✅ Prometheus format working!")
            print(f"   Lines: {len([l for l in lines if l and not l.startswith('#')])}")
            print(f"\n   Sample metrics:")
            
            for line in lines[:15]:
                if line and not line.startswith('#'):
                    print(f"   {line[:70]}")
            
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_profile():
    """Test performance profiler"""
    print_header("Testing Performance Profiler")
    
    try:
        response = requests.get(f"{BASE_URL}/profile/query_documents")
        data = response.json()
        
        if "error" in data:
            print(f"⚠️  No profiles yet (first run): {data['error']}")
            return True
        
        print(f"✅ Profile data available!")
        print(f"   Operation: {data.get('operation', 'N/A')}")
        print(f"   Count: {data.get('count', 0)}")
        
        wall = data.get("wall_time", {})
        print(f"\n   Wall Time:")
        print(f"   - Min: {wall.get('min', 0)}ms")
        print(f"   - Avg: {wall.get('avg', 0):.2f}ms")
        print(f"   - P95: {wall.get('p95', 0)}ms")
        print(f"   - P99: {wall.get('p99', 0)}ms")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_alerts():
    """Test alert history"""
    print_header("Testing Alert System")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/history?limit=10")
        data = response.json()
        
        print(f"✅ Alert system working!")
        print(f"   Total Alerts: {data.get('total', 0)}")
        
        alerts = data.get("alerts", [])
        if alerts:
            print(f"\n   Recent Alerts:")
            for alert in alerts[-3:]:
                print(f"   - [{alert.get('severity')}] {alert.get('title')}")
        else:
            print(f"   ℹ️  No alerts yet (good sign!)")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n")
    print("🔍 Production MONITORING SYSTEM - TEST SUITE")
    print(f"📍 Target: {BASE_URL}")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    # Check if service is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
    except:
        print(f"\n❌ ERROR: Service not running at {BASE_URL}")
        print(f"   Start it with: python -m uvicorn main_production:app --port 8002")
        sys.exit(1)
    
    # Run tests
    tests = [
        ("Basic Health Check", test_health),
        ("Detailed Health Check", test_detailed_health),
        ("Sample Query", test_sample_query),
        ("Metrics Summary", test_metrics_summary),
        ("Prometheus Metrics", test_prometheus_metrics),
        ("Performance Profile", test_profile),
        ("Alert History", test_alerts),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append((name, False))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {name}")
    
    print(f"\n{'='*60}")
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All monitoring tests passed!")
        print("\n📊 You can now:")
        print("   1. Check metrics at /metrics/summary")
        print("   2. View health at /health/detailed")
        print("   3. Monitor alerts at /alerts/history")
        print("   4. Feed Prometheus from /metrics/prometheus")
        return 0
    else:
        print("❌ Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
