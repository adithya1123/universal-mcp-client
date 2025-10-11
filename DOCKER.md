# Docker Deployment Guide

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- `.env` file configured (copy from `.env.example`)

### One-Command Startup

```bash
./docker-start.sh
```

This will:
1. Build all Docker images
2. Start PostgreSQL, Backend, and Frontend
3. Wait for services to be healthy
4. Display access URLs

## Manual Docker Commands

### Start All Services

```bash
docker compose up -d
```

### Stop All Services

```bash
docker compose down
```

### Rebuild and Restart

```bash
docker compose up -d --build
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

## Services

### PostgreSQL (port 5432)
- **Container:** `mcp-postgres`
- **Database:** `mcp_chat`
- **User:** `mcp_user`
- **Password:** `mcp_pass`
- **Data:** Persisted in Docker volume `postgres_data`

### Backend API (port 8000)
- **Container:** `mcp-backend`
- **Health Check:** http://localhost:8000/health
- **API Docs:** http://localhost:8000/docs
- **Technology:** FastAPI + Python 3.13

### Frontend (port 5173)
- **Container:** `mcp-frontend`
- **URL:** http://localhost:5173
- **Technology:** React + TypeScript + Nginx

## Architecture

```
┌─────────────┐
│   Frontend  │  Port 5173 (Nginx)
│   (React)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │  Port 8000 (FastAPI)
│   (Python)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  PostgreSQL │  Port 5432
│  (Database) │
└─────────────┘
```

## Environment Variables

The backend requires these environment variables (set in `.env`):

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Database (auto-configured in Docker)
DATABASE_URL=postgresql+asyncpg://mcp_user:mcp_pass@postgres:5432/mcp_chat
```

## Networking

All services run in an isolated Docker network (`mcp-network`):

- Services can communicate using container names
- Frontend proxies API requests to `backend:8000`
- Backend connects to database at `postgres:5432`

## Volumes

### Persistent Data

- `postgres_data`: PostgreSQL database files (persists across restarts)

### Mounted Volumes

- `./config:/app/config:ro` - MCP server configuration (read-only)
- `/tmp:/tmp` - Shared temp directory for MCP filesystem server

## Health Checks

All services include health checks:

- **Postgres:** `pg_isready` every 10s
- **Backend:** HTTP GET `/health` every 30s
- **Frontend:** HTTP GET `/` every 30s

## Development vs Production

### Development (Current Setup)

- Frontend built and served by Nginx
- Backend runs with auto-reload disabled
- Logs to stdout/stderr
- Ports exposed for direct access

### Production Recommendations

1. **Use SSL/TLS**
   - Add reverse proxy (Traefik/Nginx)
   - Configure certificates

2. **Security**
   - Change database passwords
   - Use secrets management
   - Enable CORS restrictions

3. **Scaling**
   - Use orchestration (Kubernetes/Swarm)
   - Add load balancer
   - Configure replicas

4. **Monitoring**
   - Add Prometheus/Grafana
   - Configure alerts
   - Log aggregation

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker compose ps

# View logs
docker compose logs backend

# Restart specific service
docker compose restart backend
```

### Database Connection Issues

```bash
# Check if Postgres is ready
docker compose exec postgres pg_isready -U mcp_user

# Connect to database
docker compose exec postgres psql -U mcp_user -d mcp_chat
```

### Port Conflicts

If ports are already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Use different host port
```

### Clean Rebuild

```bash
# Stop and remove everything
docker compose down -v

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

## Maintenance

### Update Dependencies

```bash
# Rebuild with latest packages
docker compose build --no-cache backend
docker compose up -d
```

### Database Backup

```bash
# Backup
docker compose exec postgres pg_dump -U mcp_user mcp_chat > backup.sql

# Restore
docker compose exec -T postgres psql -U mcp_user mcp_chat < backup.sql
```

### View Resource Usage

```bash
docker stats
```

## Stopping and Cleanup

### Stop Services (Keep Data)

```bash
docker compose down
```

### Stop and Remove Volumes (Delete Data)

```bash
docker compose down -v
```

### Remove Unused Images

```bash
docker system prune -a
```

## Next Steps

1. Configure your `.env` file with Azure OpenAI credentials
2. Run `./docker-start.sh`
3. Open http://localhost:5173 in your browser
4. Start chatting with your AI assistant!

For local development without Docker, see the "Local Development Setup" section in [README.md](README.md).
