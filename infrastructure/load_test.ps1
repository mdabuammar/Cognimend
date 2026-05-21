# DriftGuard Load Testing Script
# Validates system capacity for 10K+ concurrent users

param(
    [Parameter(Mandatory=$false)]
    [int]$Concurrency = 100,
    
    [Parameter(Mandatory=$false)]
    [int]$Duration = 60,
    
    [Parameter(Mandatory=$false)]
    [string]$BaseUrl = "http://localhost:8000",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("smoke", "load", "stress", "spike")]
    [string]$TestType = "load"
)

$ErrorActionPreference = "Stop"

Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                 🔥 DriftGuard Load Testing                   ║
║            Capacity Validation for 10K+ Users                ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# Test configuration based on type
$testConfigs = @{
    "smoke" = @{ Concurrency = 10; Duration = 30; RampUp = 5 }
    "load" = @{ Concurrency = 100; Duration = 60; RampUp = 30 }
    "stress" = @{ Concurrency = 500; Duration = 120; RampUp = 60 }
    "spike" = @{ Concurrency = 1000; Duration = 30; RampUp = 5 }
}

$config = $testConfigs[$TestType]
if ($Concurrency -ne 100) { $config.Concurrency = $Concurrency }
if ($Duration -ne 60) { $config.Duration = $Duration }

Write-Host "Test Configuration:" -ForegroundColor Yellow
Write-Host "  Type: $TestType"
Write-Host "  Concurrency: $($config.Concurrency) virtual users"
Write-Host "  Duration: $($config.Duration) seconds"
Write-Host "  Ramp-up: $($config.RampUp) seconds"
Write-Host "  Target: $BaseUrl"
Write-Host ""

# Check if Python and required packages are available
Write-Host "Checking dependencies..." -ForegroundColor Yellow

$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonCheck" -ForegroundColor Green

# Create load test script
$loadTestScript = @'
"""
DriftGuard Load Test - Python Implementation
Uses asyncio and aiohttp for high-concurrency testing
"""

import asyncio
import aiohttp
import time
import statistics
import random
import sys
import json
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime

@dataclass
class RequestResult:
    endpoint: str
    status_code: int
    latency_ms: float
    success: bool
    timestamp: float
    error: str = ""

@dataclass 
class LoadTestResults:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)
    start_time: float = 0
    end_time: float = 0
    requests_per_endpoint: Dict[str, int] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def rps(self) -> float:
        if self.duration > 0:
            return self.total_requests / self.duration
        return 0
    
    @property
    def success_rate(self) -> float:
        if self.total_requests > 0:
            return (self.successful_requests / self.total_requests) * 100
        return 0
    
    @property
    def p50(self) -> float:
        if self.latencies:
            return statistics.median(self.latencies)
        return 0
    
    @property
    def p95(self) -> float:
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            idx = int(len(sorted_latencies) * 0.95)
            return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
        return 0
    
    @property
    def p99(self) -> float:
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            idx = int(len(sorted_latencies) * 0.99)
            return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
        return 0


class LoadTester:
    def __init__(self, base_url: str, concurrency: int, duration: int, ramp_up: int):
        self.base_url = base_url.rstrip('/')
        self.concurrency = concurrency
        self.duration = duration
        self.ramp_up = ramp_up
        self.results = LoadTestResults()
        self.running = True
        
        # Test endpoints with weights (higher = more frequent)
        self.endpoints = [
            ("GET", "/health", 20),
            ("GET", "/api/v1/documents", 15),
            ("POST", "/api/v1/query", 30),
            ("GET", "/api/v1/collections", 10),
            ("POST", "/api/v1/search", 25),
        ]
        
        # Sample queries for POST requests
        self.sample_queries = [
            "What is machine learning?",
            "Explain neural networks",
            "How does RAG work?",
            "Compare transformers and RNNs",
            "What is semantic search?",
            "Explain vector embeddings",
            "How to fine-tune LLMs?",
            "What is prompt engineering?",
        ]
    
    def get_weighted_endpoint(self):
        """Select endpoint based on weight"""
        total = sum(w for _, _, w in self.endpoints)
        r = random.uniform(0, total)
        cumulative = 0
        for method, path, weight in self.endpoints:
            cumulative += weight
            if r <= cumulative:
                return method, path
        return self.endpoints[0][0], self.endpoints[0][1]
    
    def get_request_body(self, path: str) -> dict:
        """Generate request body for POST endpoints"""
        if "query" in path or "search" in path:
            return {
                "query": random.choice(self.sample_queries),
                "top_k": random.randint(3, 10),
            }
        return {}
    
    async def make_request(self, session: aiohttp.ClientSession) -> RequestResult:
        """Make a single request and record result"""
        method, path = self.get_weighted_endpoint()
        url = f"{self.base_url}{path}"
        
        start_time = time.time()
        try:
            if method == "GET":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    await response.read()
                    latency_ms = (time.time() - start_time) * 1000
                    return RequestResult(
                        endpoint=path,
                        status_code=response.status,
                        latency_ms=latency_ms,
                        success=response.status < 400,
                        timestamp=start_time
                    )
            else:
                body = self.get_request_body(path)
                async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    await response.read()
                    latency_ms = (time.time() - start_time) * 1000
                    return RequestResult(
                        endpoint=path,
                        status_code=response.status,
                        latency_ms=latency_ms,
                        success=response.status < 400,
                        timestamp=start_time
                    )
        except asyncio.TimeoutError:
            return RequestResult(
                endpoint=path,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                timestamp=start_time,
                error="timeout"
            )
        except Exception as e:
            return RequestResult(
                endpoint=path,
                status_code=0,
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                timestamp=start_time,
                error=str(e)[:50]
            )
    
    async def worker(self, session: aiohttp.ClientSession, worker_id: int):
        """Worker that continuously makes requests"""
        # Ramp-up delay
        ramp_delay = (worker_id / self.concurrency) * self.ramp_up
        await asyncio.sleep(ramp_delay)
        
        while self.running:
            result = await self.make_request(session)
            
            # Record results
            self.results.total_requests += 1
            self.results.latencies.append(result.latency_ms)
            
            if result.success:
                self.results.successful_requests += 1
            else:
                self.results.failed_requests += 1
                error_key = result.error if result.error else f"http_{result.status_code}"
                self.results.errors[error_key] = self.results.errors.get(error_key, 0) + 1
            
            self.results.requests_per_endpoint[result.endpoint] = \
                self.results.requests_per_endpoint.get(result.endpoint, 0) + 1
            
            # Small delay between requests per worker
            await asyncio.sleep(random.uniform(0.01, 0.1))
    
    async def progress_reporter(self):
        """Report progress during test"""
        start = time.time()
        while self.running:
            await asyncio.sleep(5)
            elapsed = time.time() - start
            current_rps = self.results.total_requests / elapsed if elapsed > 0 else 0
            print(f"  ⏱️  {elapsed:.0f}s | Requests: {self.results.total_requests} | "
                  f"RPS: {current_rps:.1f} | Success: {self.results.success_rate:.1f}% | "
                  f"P95: {self.results.p95:.0f}ms")
    
    async def run(self):
        """Run the load test"""
        print(f"\n🚀 Starting load test with {self.concurrency} virtual users...")
        print(f"   Ramp-up: {self.ramp_up}s | Duration: {self.duration}s\n")
        
        connector = aiohttp.TCPConnector(limit=self.concurrency * 2, limit_per_host=self.concurrency)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            self.results.start_time = time.time()
            
            # Create workers
            workers = [self.worker(session, i) for i in range(self.concurrency)]
            workers.append(self.progress_reporter())
            
            # Run for duration
            try:
                await asyncio.wait_for(
                    asyncio.gather(*workers),
                    timeout=self.duration + self.ramp_up
                )
            except asyncio.TimeoutError:
                pass
            finally:
                self.running = False
                self.results.end_time = time.time()
        
        return self.results
    
    def print_results(self):
        """Print formatted test results"""
        r = self.results
        
        print("\n" + "=" * 60)
        print("                    📊 LOAD TEST RESULTS")
        print("=" * 60)
        
        print(f"""
┌────────────────────────────────────────────────────────────┐
│  📈 Summary                                                │
├────────────────────────────────────────────────────────────┤
│  Total Requests:     {r.total_requests:>8,}                              │
│  Successful:         {r.successful_requests:>8,}                              │
│  Failed:             {r.failed_requests:>8,}                              │
│  Success Rate:       {r.success_rate:>7.2f}%                             │
│  Duration:           {r.duration:>7.1f}s                              │
│  Throughput:         {r.rps:>7.1f} req/s                          │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  ⏱️  Latency Distribution                                   │
├────────────────────────────────────────────────────────────┤
│  Min:                {min(r.latencies):>7.1f} ms                           │
│  P50 (Median):       {r.p50:>7.1f} ms                           │
│  P95:                {r.p95:>7.1f} ms                           │
│  P99:                {r.p99:>7.1f} ms                           │
│  Max:                {max(r.latencies):>7.1f} ms                           │
│  Avg:                {statistics.mean(r.latencies):>7.1f} ms                           │
└────────────────────────────────────────────────────────────┘
""")
        
        if r.errors:
            print("┌────────────────────────────────────────────────────────────┐")
            print("│  ❌ Error Distribution                                      │")
            print("├────────────────────────────────────────────────────────────┤")
            for error, count in sorted(r.errors.items(), key=lambda x: -x[1])[:5]:
                print(f"│  {error[:30]:30} {count:>6}                   │")
            print("└────────────────────────────────────────────────────────────┘\n")
        
        print("┌────────────────────────────────────────────────────────────┐")
        print("│  🎯 Endpoint Distribution                                   │")
        print("├────────────────────────────────────────────────────────────┤")
        for endpoint, count in sorted(r.requests_per_endpoint.items(), key=lambda x: -x[1]):
            pct = (count / r.total_requests) * 100
            print(f"│  {endpoint:25} {count:>6} ({pct:>5.1f}%)           │")
        print("└────────────────────────────────────────────────────────────┘\n")
        
        # Performance assessment
        print("┌────────────────────────────────────────────────────────────┐")
        print("│  🏆 Performance Assessment                                  │")
        print("├────────────────────────────────────────────────────────────┤")
        
        if r.success_rate >= 99 and r.p95 < 500:
            print("│  ✅ EXCELLENT - Ready for 10K+ users                       │")
        elif r.success_rate >= 95 and r.p95 < 1000:
            print("│  ✅ GOOD - Can handle significant load                     │")
        elif r.success_rate >= 90 and r.p95 < 2000:
            print("│  ⚠️  ACCEPTABLE - Some optimization needed                 │")
        else:
            print("│  ❌ NEEDS IMPROVEMENT - Performance issues detected        │")
        
        print("└────────────────────────────────────────────────────────────┘\n")
        
        # Save results to JSON
        results_file = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'config': {
                    'concurrency': self.concurrency,
                    'duration': self.duration,
                    'base_url': self.base_url
                },
                'results': {
                    'total_requests': r.total_requests,
                    'successful_requests': r.successful_requests,
                    'failed_requests': r.failed_requests,
                    'success_rate': r.success_rate,
                    'rps': r.rps,
                    'latency': {
                        'p50': r.p50,
                        'p95': r.p95,
                        'p99': r.p99,
                        'min': min(r.latencies),
                        'max': max(r.latencies),
                        'avg': statistics.mean(r.latencies)
                    },
                    'errors': r.errors,
                    'endpoint_distribution': r.requests_per_endpoint
                }
            }, f, indent=2)
        print(f"📁 Results saved to: {results_file}")


async def main():
    # Parse command line args
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    ramp_up = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    
    tester = LoadTester(base_url, concurrency, duration, ramp_up)
    await tester.run()
    tester.print_results()


if __name__ == "__main__":
    asyncio.run(main())
'@

# Save Python script
$pythonScriptPath = Join-Path $PSScriptRoot "load_test_runner.py"
$loadTestScript | Out-File -FilePath $pythonScriptPath -Encoding utf8

Write-Host "✅ Load test script created: $pythonScriptPath" -ForegroundColor Green

# Install aiohttp if needed
Write-Host "`nChecking for aiohttp..." -ForegroundColor Yellow
$aioCheck = pip show aiohttp 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing aiohttp..." -ForegroundColor Yellow
    pip install aiohttp --quiet
}
Write-Host "✅ aiohttp ready" -ForegroundColor Green

# Run the test
Write-Host "`n" -ForegroundColor White
Write-Host "🔥 Starting Load Test..." -ForegroundColor Magenta
Write-Host ("=" * 60)

python $pythonScriptPath $BaseUrl $($config.Concurrency) $($config.Duration) $($config.RampUp)

Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                   🏁 Load Test Complete!                      ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Green
