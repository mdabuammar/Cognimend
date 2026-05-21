# Quick Start Guide

## Docker Commands (PowerShell)

Since Docker isn't in your PATH, use one of these methods:

### Method 1: Add to PATH each session
```powershell
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
docker ps
```

### Method 2: Use the wrapper script
```powershell
cd D:\Project\backend
.\docker.ps1 ps
.\docker.ps1 compose up -d
.\docker.ps1 compose down
```

### Method 3: Create an alias (add to PowerShell profile)
```powershell
# Add this to your PowerShell profile: $PROFILE
Set-Alias docker "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

## Current Status

✅ **Docker containers are running:**
- PostgreSQL (port 5432) - healthy
- Redis (port 6379) - healthy  
- Qdrant (ports 6333-6334) - starting

## Next Steps

1. **Start Upload Service** (new terminal):
   ```powershell
   cd D:\Project\backend\services\upload
   pip install -r requirements.txt
   python main.py
   ```

2. **Start Query Service** (another terminal):
   ```powershell
   cd D:\Project\backend\services\query
   pip install -r requirements.txt
   python main.py
   ```

3. **Test the services** (see TESTING_GUIDE.md)

## Useful Docker Commands

```powershell
# Check containers (after adding Docker to PATH)
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
docker ps

# View logs
docker compose logs -f

# Stop services
docker compose down

# Restart services
docker compose restart
```
