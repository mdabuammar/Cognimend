# Docker Setup Guide

## Install Docker Desktop for Windows

1. **Download Docker Desktop:**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Download "Docker Desktop for Windows"
   - File size: ~500MB

2. **Install:**
   - Run the installer
   - Follow the installation wizard
   - **Important:** Enable "Use WSL 2 instead of Hyper-V" if prompted (recommended)
   - Restart your computer if required

3. **Start Docker Desktop:**
   - Launch Docker Desktop from Start Menu
   - Wait for it to fully start (whale icon in system tray)
   - You'll see "Docker Desktop is running" when ready

4. **Verify Installation:**
   ```powershell
   docker --version
   docker compose version
   ```

5. **Start Your Services:**
   ```powershell
   cd D:\Project\backend
   docker compose up -d
   docker ps
   ```

## Alternative: Test Without Docker (Advanced)

If you can't install Docker right now, you can manually set up the services:

### PostgreSQL
- Download and install PostgreSQL from https://www.postgresql.org/download/windows/
- Create database: `cognimend`
- Update `backend/.env` with your PostgreSQL connection details

### Qdrant
- Download Qdrant from https://qdrant.tech/documentation/guides/installation/
- Run Qdrant locally or use Qdrant Cloud (free tier available)

### Redis (Optional)
- Redis is not currently used in the code, so you can skip this for now

**Note:** Manual setup is more complex. Docker is the recommended approach.
