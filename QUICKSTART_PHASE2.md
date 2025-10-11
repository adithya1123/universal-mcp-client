# Quick Start Guide - Phase 2 (With Postgres & LangGraph)

This guide will get you up and running with the Phase 2 version, which includes:
- ✅ Postgres persistence for chat history
- ✅ LangGraph Functional API with @entrypoint/@task
- ✅ Full conversation context management
- ✅ Database checkpointing support

---

## Prerequisites

- **Python 3.10+**
- **UV** package manager ([install](https://docs.astral.sh/uv/))
- **Node.js 18+** (for frontend)
- **Postgres 15+** (via Docker or local install)
- **Azure OpenAI** account with API key

---

## Step 1: Clone & Install

```bash
# Navigate to project
cd universal-mcp-client

# Install Python dependencies (UV handles everything)
uv sync
```

---

## Step 2: Set up Postgres

### Option A: Docker (Recommended)

```bash
# Start Postgres container
docker compose up -d

# Check it's running
docker compose ps

# View logs
docker compose logs postgres
```

The container runs on `localhost:5432` with:
- **Database:** mcp_chat
- **User:** mcp_user
- **Password:** mcp_pass

### Option B: Local Postgres

See `POSTGRES_SETUP.md` for local installation instructions.

---

## Step 3: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Azure OpenAI credentials
nano .env
```

**Required environment variables:**
```env
# Azure OpenAI (replace with your values)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Postgres (default values for Docker setup)
DATABASE_URL=postgresql+asyncpg://mcp_user:mcp_pass@localhost:5432/mcp_chat

# App Config
DEBUG=true
LOG_LEVEL=INFO
```

---

## Step 4: Initialize Database

```bash
# Create tables
uv run python scripts/init_db.py
```

Expected output:
```
INFO: Initializing database...
INFO: Database tables created successfully
INFO: Database initialized successfully!
```

---

## Step 5: Start Backend

```bash
# Make script executable (first time only)
chmod +x run_backend.sh

# Start server
./run_backend.sh
```

Expected output:
```
INFO: 🚀 Starting Universal MCP Client...
INFO: Initializing database...
INFO: ✅ Database initialized
INFO: Loading MCP servers...
INFO: ✅ Connected to 1 MCP server(s)
INFO: Initializing Azure OpenAI client...
INFO: ✅ Azure OpenAI client initialized
INFO: ✅ LangGraph agent initialized
INFO: ✅ All systems ready!
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## Step 6: Start Frontend

```bash
# In a new terminal
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

Frontend runs on: **http://localhost:5173**

---

## Step 7: Test the System

### 1. Open Browser
Navigate to **http://localhost:5173**

### 2. Send a Test Message
```
"Hello! Can you list the files in the current directory?"
```

The assistant will:
1. Use the `filesystem_list_directory` tool
2. Return the list of files
3. All interactions saved to Postgres!

### 3. Verify Persistence
```bash
# In a new terminal, check the database
docker exec -it mcp-postgres psql -U mcp_user -d mcp_chat

# Run SQL query
SELECT session_id, role, LEFT(content, 50) as content_preview, created_at
FROM conversations
ORDER BY created_at DESC
LIMIT 10;

# Exit psql
\q
```

### 4. Test API Endpoints

**Get Chat History:**
```bash
curl http://localhost:8000/chat/history/default | jq
```

**Health Check:**
```bash
curl http://localhost:8000/health | jq
```

**List Tools:**
```bash
curl http://localhost:8000/tools | jq
```

**Reset Conversation:**
```bash
curl -X POST "http://localhost:8000/chat/reset?session_id=default"
```

---

## Architecture Overview

```
┌─────────────┐
│   Browser   │
│  (React UI) │
└─────┬───────┘
      │ WebSocket
      ↓
┌─────────────────────────────────────┐
│         FastAPI Server              │
│  ┌──────────────────────────────┐   │
│  │   LangGraph Agent            │   │
│  │   @entrypoint / @task        │   │
│  └────────┬─────────────────────┘   │
│           │                          │
│    ┌──────┴──────┐                  │
│    │             │                  │
│    ↓             ↓                  │
│  Azure        MCP Client            │
│  OpenAI       (Filesystem)          │
└────┬────────────┬─────────────────┬─┘
     │            │                 │
     │            │         ┌───────┴────────┐
     │            │         │   PostgreSQL   │
     │            │         │  - conversations│
     │            │         │  - checkpoints │
     │            │         └────────────────┘
     │            ↓
     │    Local Filesystem
     │    (MCP Server)
     ↓
  gpt-4o
```

---

## Common Issues & Solutions

### Issue: "Database not initialized"
**Solution:**
```bash
# Check Postgres is running
docker compose ps

# Reinitialize database
uv run python scripts/init_db.py
```

### Issue: "Connection refused" to Postgres
**Solution:**
```bash
# Restart Postgres
docker compose restart postgres

# Check logs
docker compose logs postgres
```

### Issue: "Azure OpenAI API error"
**Solution:**
1. Verify your API key in `.env`
2. Check your deployment name matches your Azure resource
3. Ensure your Azure OpenAI instance is in a supported region

### Issue: MCP server not found
**Solution:**
```bash
# Check MCP servers config
cat config/mcp_servers.json

# Restart backend
./run_backend.sh
```

---

## Development Workflow

### 1. Make Code Changes
Edit files in `src/` directory

### 2. Backend Auto-Reloads
The `run_backend.sh` script uses `--reload` flag

### 3. Frontend Hot-Reload
Vite automatically reloads on file changes

### 4. Check Logs
Backend logs appear in terminal where you ran `run_backend.sh`

### 5. Database Changes
```bash
# After modifying models, recreate tables
uv run python scripts/init_db.py

# Or use migrations (future)
# uv run alembic revision --autogenerate -m "description"
# uv run alembic upgrade head
```

---

## Useful Commands

### Database

```bash
# Connect to database
docker exec -it mcp-postgres psql -U mcp_user -d mcp_chat

# Backup database
docker exec mcp-postgres pg_dump -U mcp_user mcp_chat > backup.sql

# Restore database
cat backup.sql | docker exec -i mcp-postgres psql -U mcp_user -d mcp_chat

# Reset database (DELETE ALL DATA)
docker compose down -v
docker compose up -d
uv run python scripts/init_db.py
```

### Server

```bash
# Start server in debug mode
DEBUG=true uv run python -m uvicorn src.api.server:app --reload --log-level debug

# Run tests (when implemented)
uv run pytest

# Check code style
uv run ruff check src/

# Format code
uv run ruff format src/
```

### Docker

```bash
# Stop all containers
docker compose down

# View container logs
docker compose logs -f postgres

# Remove volumes (deletes data!)
docker compose down -v
```

---

## Next Steps

### Explore the Code
- `src/storage/` - Database models and operations
- `src/orchestration/` - LangGraph agent logic
- `src/api/` - FastAPI endpoints
- `frontend/src/` - React UI components

### Add More MCP Servers
Edit `config/mcp_servers.json` to add more servers

### Customize the Agent
Modify `src/orchestration/agent.py` to change agent behavior

### Build New Features
See `ROADMAP.md` for planned features

---

## Documentation

- **PHASE2_SUMMARY.md** - Detailed Phase 2 implementation
- **POSTGRES_SETUP.md** - Postgres installation guide
- **ROADMAP.md** - Full project roadmap
- **README.md** - Main project README

---

## Getting Help

### Check Logs
Backend logs show detailed error messages

### Database Status
```bash
curl http://localhost:8000/health
```

### Test Database Connection
```bash
uv run python -c "
from src.storage.database import get_db_manager
import asyncio

async def test():
    db = get_db_manager()
    history = await db.get_conversation_history('test')
    print(f'Connection OK! Found {len(history)} messages')

asyncio.run(test())
"
```

---

## Success Indicators

✅ Backend starts without errors
✅ Frontend loads in browser
✅ Can send and receive messages
✅ Database shows conversation records
✅ Conversation persists after page reload
✅ Tools execute successfully

---

**You're all set! Start chatting with your AI assistant. 🚀**
