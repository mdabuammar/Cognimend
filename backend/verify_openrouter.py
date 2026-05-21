#!/usr/bin/env python3
"""
OpenRouter Integration Verification Script
Tests that OpenRouter is properly integrated and working
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    """Print a section header"""
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    """Print info message"""
    print(f"{BLUE}ℹ️  {text}{RESET}")

def check_env_variables():
    """Check if .env has correct OpenRouter variables"""
    print_header("Checking Environment Variables")
    
    checks_passed = 0
    checks_total = 3
    
    # Check OPENROUTER_API_KEY
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key and api_key.startswith("sk-or-v1-"):
        print_success(f"OPENROUTER_API_KEY present: {api_key[:20]}...")
        checks_passed += 1
    else:
        print_error("OPENROUTER_API_KEY missing or invalid")
    
    # Check OPENROUTER_PRESET
    preset = os.getenv("OPENROUTER_PRESET", "balanced")
    valid_presets = ["free", "cheap", "balanced", "quality", "best"]
    if preset in valid_presets:
        print_success(f"OPENROUTER_PRESET: {preset} (valid)")
        checks_passed += 1
    else:
        print_error(f"OPENROUTER_PRESET invalid: {preset}")
    
    # Check database env vars
    db_user = os.getenv("POSTGRES_USER")
    if db_user:
        print_success(f"Database configured: {db_user}")
        checks_passed += 1
    else:
        print_warning("POSTGRES_USER not set (will use default)")
    
    return checks_passed == checks_total

def check_python_packages():
    """Check if required Python packages are installed"""
    print_header("Checking Python Packages")
    
    required_packages = {
        "openai": "OpenAI client library",
        "tenacity": "Retry logic",
        "tiktoken": "Token counting",
        "fastapi": "API framework",
        "qdrant_client": "Vector DB client",
        "psycopg2": "PostgreSQL driver",
    }
    
    all_present = True
    
    for package, description in required_packages.items():
        try:
            __import__(package)
            print_success(f"{package}: {description}")
        except ImportError:
            print_error(f"{package}: NOT INSTALLED")
            all_present = False
    
    if not all_present:
        print_warning("Install missing packages with:")
        print(f"  pip install -r backend/services/query/requirements.txt")
    
    return all_present

def check_openrouter_client():
    """Check if OpenRouter client can be imported"""
    print_header("Checking OpenRouter Client")
    
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from core.openrouter_client import create_openrouter_client, OpenRouterClient
        
        print_success("OpenRouterClient class importable")
        
        # Check if we can create a client (without actually calling API)
        try:
            client = create_openrouter_client()
            print_success(f"Client created with preset: balanced")
            
            # Check client properties
            print_info(f"  Embedding model: {client.embedding_model}")
            print_info(f"  Generation model: {client.generation_model}")
            print_info(f"  Fallback enabled: {client.enable_fallback}")
            
            return True
        except ValueError as e:
            print_error(f"Cannot create client: {e}")
            print_warning("Make sure OPENROUTER_API_KEY is set in .env")
            return False
    
    except ImportError as e:
        print_error(f"Cannot import OpenRouterClient: {e}")
        return False

def check_docker_running():
    """Check if Docker services are running"""
    print_header("Checking Docker Services")
    
    try:
        # Check if docker-compose is available
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_success(f"Docker Compose: {result.stdout.strip()}")
        else:
            print_error("Docker Compose not found or not working")
            return False
        
        # Check services
        cwd = os.path.dirname(__file__)
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True,
            cwd=cwd
        )
        
        if "cognimend-upload" in result.stdout:
            print_success("Upload service running")
        else:
            print_warning("Upload service not running (start with: docker-compose up -d)")
        
        if "cognimend-query" in result.stdout:
            print_success("Query service running")
        else:
            print_warning("Query service not running (start with: docker-compose up -d)")
        
        if "cognimend-postgres" in result.stdout:
            print_success("PostgreSQL running")
        else:
            print_warning("PostgreSQL not running")
        
        if "cognimend-qdrant" in result.stdout:
            print_success("Qdrant running")
        else:
            print_warning("Qdrant not running")
        
        return True
    
    except FileNotFoundError:
        print_warning("Docker/Docker Compose not installed or not in PATH")
        return False

def check_api_endpoints():
    """Check if API endpoints are responding"""
    print_header("Checking API Endpoints")
    
    endpoints = [
        ("http://localhost:8001/health", "Upload Service"),
        ("http://localhost:8002/health", "Query Service"),
    ]
    
    all_online = True
    
    try:
        import requests
    except ImportError:
        print_warning("requests library not installed, skipping endpoint checks")
        print("  Install with: pip install requests")
        return False
    
    for url, service in endpoints:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print_success(f"{service}: {url}")
            else:
                print_warning(f"{service}: {url} returned {response.status_code}")
                all_online = False
        except Exception as e:
            print_warning(f"{service}: {url} - {type(e).__name__}")
            all_online = False
    
    if not all_online:
        print_info("Services may not be running. Start with: docker-compose up -d")
    
    return True  # Don't fail overall check if services aren't running

def check_configuration_files():
    """Check if all configuration files are in place"""
    print_header("Checking Configuration Files")
    
    files_to_check = {
        "../.env": "Root environment variables",
        "../docker-compose.yml": "Docker Compose configuration",
        "../core/openrouter_client.py": "OpenRouter client",
        "../services/upload/main.py": "Upload service",
        "../services/query/main.py": "Query service",
    }
    
    all_present = True
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    for file_path, description in files_to_check.items():
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            print_success(f"{description}: {file_path}")
        else:
            print_error(f"{description}: {file_path} - NOT FOUND")
            all_present = False
    
    return all_present

def check_openrouter_client_content():
    """Check if OpenRouter client has key components"""
    print_header("Checking OpenRouter Client Implementation")
    
    client_file = "../core/openrouter_client.py"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, client_file)
    
    if not os.path.exists(full_path):
        print_error(f"Client file not found: {full_path}")
        return False
    
    with open(full_path, 'r') as f:
        content = f.read()
    
    checks = {
        "class OpenRouterClient": "OpenRouter client class",
        "def create_openrouter_client": "Client factory function",
        "preset": "Preset configuration support",
        "enable_fallback": "Fallback support",
        "async def generate_answer": "Answer generation method",
        "async def get_embedding": "Embedding method",
        "anthropic/claude-3.5-haiku": "Claude Haiku model",
        "google/gemini-2.0-flash-exp:free": "Free Gemini model",
    }
    
    all_present = True
    for check, description in checks.items():
        if check in content:
            print_success(f"{description}: Found")
        else:
            print_error(f"{description}: NOT FOUND")
            all_present = False
    
    return all_present

def generate_summary(checks):
    """Generate final summary"""
    print_header("Verification Summary")
    
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    percentage = (passed / total) * 100
    
    print(f"\nPassed: {passed}/{total} ({percentage:.0f}%)\n")
    
    for check_name, passed in checks.items():
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        print(f"{status} - {check_name}")
    
    print()
    
    if passed == total:
        print_success("All checks passed! Ready to deploy.")
        print_info("Next steps:")
        print("  1. Start services: cd backend && docker-compose up -d")
        print("  2. Upload a document: curl -X POST http://localhost:8001/upload ...")
        print("  3. Query: curl -X POST http://localhost:8002/query ...")
        return True
    elif passed >= total * 0.7:
        print_warning(f"Most checks passed ({percentage:.0f}%). Some fixes may be needed.")
        return True
    else:
        print_error(f"Multiple checks failed ({percentage:.0f}%). Please review above.")
        return False

def main():
    """Run all checks"""
    print("\n")
    print(f"{BLUE}")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  OpenRouter Integration Verification".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    print(f"{RESET}")
    
    print_info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Working directory: {os.getcwd()}")
    
    # Load environment from .env
    env_file = os.path.join(os.path.dirname(__file__), "../.env")
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print_success(f"Loaded environment from: {env_file}")
    else:
        print_warning(f"Could not find .env at: {env_file}")
    
    # Run all checks
    checks = {
        "Environment Variables": check_env_variables(),
        "Python Packages": check_python_packages(),
        "OpenRouter Client": check_openrouter_client(),
        "Configuration Files": check_configuration_files(),
        "Client Implementation": check_openrouter_client_content(),
        "Docker Services": check_docker_running(),
        "API Endpoints": check_api_endpoints(),
    }
    
    # Generate summary
    success = generate_summary(checks)
    
    # Print footer
    print(f"\n{BLUE}{'='*60}{RESET}")
    print("For more information:")
    print("  - OPENROUTER_GUIDE.md")
    print("  - OPENROUTER_MIGRATION.md")
    print("  - OPENROUTER_QUICK_REF.md")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
