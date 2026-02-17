"""
Production Uvicorn Configuration for High-Performance Location Tracking
Optimized for thousands of concurrent WebSocket connections
"""

# uvicorn_config.py
import multiprocessing

# Server Configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1  # Optimal worker count
worker_class = "uvicorn.workers.UvicornWorker"

# WebSocket Configuration
websocket_ping_interval = 20  # Send ping every 20 seconds
websocket_ping_timeout = 60  # Close connection if no pong in 60 seconds
websocket_max_size = 1024 * 1024  # 1MB max message size

# Performance Tuning
keepalive = 5
max_requests = 10000  # Restart worker after 10k requests (prevent memory leaks)
max_requests_jitter = 1000
timeout = 120  # 2 minutes timeout for long-running requests
graceful_timeout = 30

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"

# Production startup command:
# uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --ws ping-interval 20 --ws ping-timeout 60

# Docker Compose example:
"""
version: '3.8'
services:
  location-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - MAPBOX_TOKEN=${MAPBOX_TOKEN}
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --ws ping-interval 20
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
"""

# Nginx reverse proxy configuration for WebSocket support:
"""
upstream location_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    
    location /api/location/ws/ {
        proxy_pass http://location_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;  # 24 hours
    }
    
    location /api/ {
        proxy_pass http://location_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
"""

# Redis Configuration for Production:
"""
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB snapshots for performance
appendonly no  # Disable AOF for performance (location data is ephemeral)
tcp-backlog 511
timeout 0
tcp-keepalive 300
"""

# Environment Variables:
"""
# .env
REDIS_URL=redis://localhost:6379
MAPBOX_TOKEN=pk.eyJ1IjoieW91cnVzZXIiLCJhIjoiY2x4eHh4eHh4In0.xxxxxxxxx
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
SECRET_KEY=your-secret-key
"""
