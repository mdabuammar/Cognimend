# Cognimend Production NGINX & HTTPS Guide

This guide outlines how to deploy Cognimend in a production environment using NGINX as a reverse proxy with SSL/TLS encryption via Let's Encrypt.

## Prerequisites
- A Linux server (Ubuntu 22.04 LTS recommended)
- Docker and Docker Compose installed
- A domain name (e.g., `cognimend.ai`) with DNS records pointing to your server:
  - `cognimend.ai` (Frontend)
  - `api.cognimend.ai` (API Gateway)

## 1. Install NGINX and Certbot

Install NGINX and Certbot for automatic SSL certificate generation:

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

## 2. Configure NGINX Server Blocks

Create a configuration file for the API Gateway:

```bash
sudo nano /etc/nginx/sites-available/api.cognimend.ai
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name api.cognimend.ai;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Increase max body size for document uploads (e.g., 50MB)
        client_max_body_size 50M;
    }
}
```

Create a configuration file for the Frontend:

```bash
sudo nano /etc/nginx/sites-available/cognimend.ai
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name cognimend.ai www.cognimend.ai;

    location / {
        proxy_pass http://localhost:80; # Assuming frontend docker binds to 80
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable the sites:

```bash
sudo ln -s /etc/nginx/sites-available/api.cognimend.ai /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/cognimend.ai /etc/nginx/sites-enabled/
```

Test the configuration and restart NGINX:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

## 3. Enable HTTPS with Let's Encrypt

Run Certbot to automatically configure SSL/TLS:

```bash
sudo certbot --nginx -d cognimend.ai -d www.cognimend.ai
sudo certbot --nginx -d api.cognimend.ai
```

Certbot will ask if you want to redirect HTTP to HTTPS. It is highly recommended to select **Option 2 (Redirect)**.

## 4. Run Cognimend Production Stack

Ensure your `.env` file has the correct production URLs:

```env
# .env
CORS_ORIGINS=https://cognimend.ai,https://www.cognimend.ai
FRONTEND_URL=https://cognimend.ai
AUTH_SERVICE_URL=http://auth-service:8000
UPLOAD_SERVICE_URL=http://upload-service:8001
QUERY_SERVICE_URL=http://query-service:8002
TELEMETRY_SERVICE_URL=http://telemetry-service:8003
DRIFT_DETECTOR_URL=http://drift-detector:8004
CONTROLLER_URL=http://controller-service:8005
EVALUATION_URL=http://evaluation-service:8006
```

Start the production stack:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

## Security Best Practices
1. **Firewall (UFW):** Ensure only ports 80, 443, and 22 are open.
   ```bash
   sudo ufw allow 'Nginx Full'
   sudo ufw allow OpenSSH
   sudo ufw enable
   ```
2. **Internal Communication:** The microservices inside docker-compose communicate securely via the internal `cognimend-network` Docker bridge. Only the `api-gateway` and `frontend` are exposed to the host network.
3. **Internal Trust Token:** Ensure `INTERNAL_SERVICE_TOKEN` in your `.env` is set to a long, random, secure string.
4. **Database Passwords:** Ensure all default passwords (e.g., PostgreSQL, Redis, RabbitMQ) are changed in `.env`.
