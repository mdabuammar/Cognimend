#!/usr/bin/env python
"""
Startup script for all backend services
"""
import subprocess
import time
import sys

print("Starting All Backend Services...")
print("=" * 50)

services = [
    ("auth-service", r"D:\Project\backend\services\auth", "8000", "main:app"),
    ("upload-service", r"D:\Project\backend\services\upload", "8001", "main:app"),
    ("query-service", r"D:\Project\backend\services\query", "8002", "main:app"),
    ("telemetry-service", r"D:\Project\backend\services\telemetry", "8003", "main:app"),
    ("drift-detector", r"D:\Project\backend\services\drift_detector", "8004", "main:app"),
    ("controller-service", r"D:\Project\backend\services\controller", "8005", "main:app"),
    ("evaluation-service", r"D:\Project\backend\services\evaluation", "8006", "main:app"),
    ("api-gateway", r"D:\Project\backend\services\gateway", "8080", "main:app"),
]

procs = []

for name, cwd, port, app in services:
    print(f"Starting {name} on port {port}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", app, "--host", "127.0.0.1", "--port", port],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True
    )
    procs.append((name, proc))

print("\nWaiting 5 seconds for services to start...")
time.sleep(5)

print("\nServices should be running!")
print("Gateway is at http://localhost:8080")
print("\nPress Ctrl+C to stop all services")

try:
    for _, proc in procs:
        proc.wait()
except KeyboardInterrupt:
    print("\n\nStopping services...")
    for _, proc in procs:
        proc.terminate()
    for _, proc in procs:
        proc.wait()
    print("Services stopped!")
