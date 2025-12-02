# Docker Deployment Guide

## 🐳 Quick Start dengan Docker Compose

### 1. Build dan Start Services
```bash
# Build dan start semua services (API + Redis)
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f pdf-extraction-api
```

### 2. Test API
```bash
# Health check
curl http://localhost:3111/health

# Worker stats
curl http://localhost:3111/workers

# Upload PDF (contoh)
curl -X POST "http://localhost:3111/upload" \
     -F "file=@sample.pdf"
```

### 3. Stop Services
```bash
# Stop services
docker-compose down

# Stop dan hapus volumes
docker-compose down -v
```

## 🔨 Manual Docker Build

### 1. Build Image
```bash
# Build image dengan tag
docker build -t pdf-extraction-api:latest .

# Build dengan specific tag
docker build -t pdf-extraction-api:v2.0 .
```

### 2. Run dengan External Redis
```bash
# Start Redis container terlebih dahulu
docker run -d --name redis-server redis:7-alpine

# Run PDF extraction API
docker run -d \
  --name pdf-api \
  --link redis-server:redis \
  -p 3111:3111 \
  -e REDIS_HOST=redis \
  -e API_PORT=3111 \
  -e WORKER_COUNT=3 \
  pdf-extraction-api:latest
```

### 3. Run Standalone (tanpa Redis external)
```bash
# Jika Redis sudah running di host
docker run -d \
  --name pdf-api \
  --network host \
  -e REDIS_HOST=localhost \
  -e API_PORT=3111 \
  pdf-extraction-api:latest
```

## ⚙️ Environment Variables untuk Docker

```bash
# API Configuration
API_HOST=0.0.0.0          # Host binding (tetap 0.0.0.0 untuk Docker)
API_PORT=3111             # Port internal container

# Redis Configuration
REDIS_HOST=redis          # Redis hostname (service name di compose)
REDIS_PORT=6379           # Redis port
REDIS_DB=0                # Redis database number

# Worker Configuration
WORKER_COUNT=3            # Jumlah worker (sesuaikan dengan CPU)
ENABLE_WORKERS=true       # Enable worker system
WORKER_POLL_INTERVAL=2.0  # Polling interval
MAX_QUEUE_SIZE=100        # Max queue size

# Upload Configuration
MAX_FILE_SIZE=52428800    # Max file size (50MB)

# Debug
DEBUG=false               # Set ke true untuk development
```

## 📊 Production Deployment

### 1. Multi-stage Build (Optimized)
```dockerfile
# Dockerfile dengan multi-stage untuk production
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 3111
CMD ["python3", "main.py"]
```

### 2. Production Docker Compose
```yaml
version: '3.8'
services:
  pdf-api:
    build: .
    ports:
      - "3111:3111"
    environment:
      - WORKER_COUNT=5
      - MAX_QUEUE_SIZE=200
      - WORKER_POLL_INTERVAL=1.0
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    restart: always
```

### 3. Load Balancer (Nginx)
```nginx
upstream pdf_api {
    server localhost:3111;
    server localhost:3112;  # Jika multiple instances
}

server {
    listen 80;
    location / {
        proxy_pass http://pdf_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 50M;  # Sesuai MAX_FILE_SIZE
    }
}
```

## 🔍 Monitoring dan Logs

### 1. View Logs
```bash
# Logs semua services
docker-compose logs -f

# Logs specific service
docker-compose logs -f pdf-extraction-api
docker-compose logs -f redis

# Logs dengan timestamp
docker-compose logs -f --timestamps pdf-extraction-api
```

### 2. Monitor Resources
```bash
# Resource usage
docker stats

# Container info
docker inspect pdf-extraction-api

# Execute command di container
docker-compose exec pdf-extraction-api curl localhost:3111/health
```

### 3. Health Checks
```bash
# Manual health check
curl http://localhost:3111/health

# Worker statistics
curl http://localhost:3111/workers

# Queue information
curl http://localhost:3111/queue
```

## 🐛 Troubleshooting Docker

### 1. Container Won't Start
```bash
# Check container logs
docker-compose logs pdf-extraction-api

# Check if Redis is running
docker-compose logs redis

# Restart services
docker-compose restart
```

### 2. Connection Issues
```bash
# Check network
docker network ls
docker network inspect pdf-extraction_default

# Test Redis connection from API container
docker-compose exec pdf-extraction-api redis-cli -h redis ping
```

### 3. Performance Issues
```bash
# Increase worker count
docker-compose up -d --scale pdf-extraction-api=2

# Monitor resources
docker stats

# Check queue size
curl http://localhost:3111/queue
```

## 🚀 Deployment Tips

1. **Resource Allocation**: Set memory limits sesuai kebutuhan
2. **Worker Count**: 1-2x CPU cores untuk optimal performance  
3. **Queue Size**: Monitor dan adjust sesuai traffic
4. **Health Checks**: Enable untuk automatic restart
5. **Logging**: Mount volume untuk persistent logs
6. **Security**: Use non-root user di production