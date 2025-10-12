# Universal MCP Client

A production-ready web-based AI chat assistant that acts as a universal MCP (Model Context Protocol) client. Built with Azure OpenAI, LangGraph, FastAPI, React, and PostgreSQL.

## Features

- **Universal MCP Client**: Connect to multiple MCP servers simultaneously (STDIO transport)
- **Agentic Workflows**: LangGraph Functional API with @entrypoint decorators and PostgreSQL checkpointing
- **Persistent Conversations**: PostgreSQL-backed chat history and state management
- **Real-time Chat**: WebSocket and REST API endpoints
- **Automatic Tool Discovery**: Dynamically discover and use tools from connected MCP servers
- **Azure OpenAI Integration**: Powered by Azure OpenAI GPT-4o for intelligent responses
- **Docker Deployment**: Complete containerized stack with multi-stage builds

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│              http://localhost:5173                   │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket / REST
┌──────────────────────▼──────────────────────────────┐
│              Backend (FastAPI)                       │
│              http://localhost:8000                   │
│  ┌────────────────────────────────────────────┐    │
│  │  LangGraph Agent (Functional API)          │    │
│  │  - @entrypoint with checkpointing          │    │
│  │  - @task for modular operations            │    │
│  └────────────────────────────────────────────┘    │
└───┬────────────┬────────────┬────────────┬─────────┘
    │            │            │            │
    ▼            ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐
│ Azure  │  │  MCP   │  │  MCP     │  │ Postgres │
│ OpenAI │  │ Server │  │  Server  │  │ Database │
│        │  │ (FS)   │  │  (SQL)   │  │          │
└────────┘  └────────┘  └──────────┘  └──────────┘
```

## Tech Stack

**Backend:**
- **FastAPI** - Async web framework with WebSocket support
- **LangGraph Functional API** - Agentic orchestration with @entrypoint/@task decorators
- **Azure OpenAI** - GPT-4o for LLM capabilities
- **MCP SDK** - Model Context Protocol client implementation
- **PostgreSQL** - Conversation history and LangGraph checkpointing
- **SQLAlchemy** - Async ORM with psycopg driver
- **Alembic** - Database migrations
- **UV** - Fast Python package manager

**Frontend:**
- **React 18** - UI framework
- **TypeScript** - Type-safe development
- **Vite** - Lightning-fast build tool
- **WebSocket** - Real-time communication

**Infrastructure:**
- **Docker & Docker Compose** - Containerized deployment
- **PostgreSQL 15** - Database server
- **Nginx** - Frontend web server

## Quick Start with Docker (Recommended)

### Prerequisites

- Docker and Docker Compose
- Azure OpenAI account with API access

### 1. Clone and Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd universal-mcp-client

# Copy and configure environment
cp .env.example .env
```

Edit `.env` with your Azure OpenAI credentials:

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Database (Docker default - change credentials in docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://db_user:db_password@postgres:5432/mcp_chat
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** on port 5432
- **Backend** on port 8000
- **Frontend** on port 5173

### 3. Access the Application

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Verify Status

```bash
# Check running containers
docker-compose ps

# View logs
docker-compose logs backend
docker-compose logs frontend

# Check MCP servers and tools
curl http://localhost:8000/health
```

## Local Development Setup

### Prerequisites

- Python 3.13+
- Node.js 20+
- UV package manager
- PostgreSQL 15+
- npm/npx for MCP servers

### 1. Database Setup

```bash
# Start PostgreSQL (or use Docker)
docker run -d \
  --name postgres \
  -e POSTGRES_USER=your_db_user \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=mcp_chat \
  -p 5432:5432 \
  postgres:15-alpine
```

### 2. Backend Setup

```bash
# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start backend
./run_backend.sh
# OR
PYTHONPATH=. uv run uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173

## MCP Server Configuration

Configure MCP servers in `config/mcp_servers.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "description": "Local filesystem access MCP server",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "enabled": true
    },
    {
      "name": "PostgreSql",
      "description": "PostgreSQL data access MCP server",
      "transport": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql+asyncpg://db_user:db_password@postgres:5432/mcp_chat"
      ],
      "enabled": true
    }
  ]
}
```

**Note for Docker:** Use service name `postgres` instead of `localhost` in connection strings.

## API Endpoints

### REST Endpoints

- `GET /` - API status
- `GET /health` - Health check with MCP servers and tool count
- `GET /tools` - List all available MCP tools
- `POST /chat` - Send chat message (returns response)
- `POST /chat/reset` - Clear conversation history for a session
- `GET /chat/history/{session_id}` - Get conversation history

### WebSocket Endpoint

- `WS /ws/chat` - Real-time bidirectional chat communication

**Example WebSocket message:**
```json
{
  "message": "List files in /tmp",
  "session_id": "user123"
}
```

## Project Structure

```
universal-mcp-client/
├── src/                          # Backend Python code
│   ├── api/                      # FastAPI server and endpoints
│   │   └── server.py            # Main server with lifespan management
│   ├── mcp/                      # MCP client implementation
│   │   └── client.py            # Universal MCP client
│   ├── orchestration/            # LangGraph workflows
│   │   ├── agent.py             # Main agent with @entrypoint
│   │   ├── checkpointer.py      # PostgreSQL checkpointer
│   │   └── state.py             # State type definitions
│   ├── llm/                      # LLM integrations
│   │   └── azure_openai.py      # Azure OpenAI client
│   └── storage/                  # Database layer
│       ├── database.py          # Database manager
│       └── models.py            # SQLAlchemy models
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/          # React components
│   │   │   └── Chat.tsx        # Main chat interface
│   │   ├── App.tsx              # Root component
│   │   └── main.tsx             # Entry point
│   ├── Dockerfile               # Frontend Docker build
│   └── nginx.conf               # Nginx configuration
├── config/                       # Configuration files
│   └── mcp_servers.json         # MCP server definitions
├── alembic/                      # Database migrations
│   ├── versions/                # Migration files
│   └── env.py                   # Alembic configuration
├── docs/                         # Documentation
│   ├── LANGGRAPH_FUNCTIONAL_API.md
│   ├── MCP_PROTOCOL.md
│   └── IMPLEMENTATION_REFERENCE.md
├── docker-compose.yml            # Docker orchestration
├── Dockerfile                    # Backend Docker build
├── .env                          # Environment variables
└── README.md                     # This file
```

## Current Status

### ✅ Completed (Phase 1 & 2)

- [x] Project setup with UV package manager
- [x] MCP client with STDIO transport
- [x] Multi-server MCP support (filesystem, PostgreSQL)
- [x] Azure OpenAI GPT-4o integration
- [x] LangGraph Functional API with @entrypoint/@task
- [x] PostgreSQL conversation persistence
- [x] LangGraph PostgreSQL checkpointing
- [x] FastAPI backend with REST + WebSocket
- [x] React + TypeScript frontend
- [x] Docker Compose deployment
- [x] Database migrations with Alembic
- [x] 15 MCP tools available (filesystem + SQL operations)

### 🚧 Phase 3: Advanced Features (Next)

- [ ] Enhanced frontend UI/UX
- [ ] Streaming responses with real-time tool execution display
- [ ] Multi-session management
- [ ] Tool execution approval flow (human-in-the-loop)
- [ ] Additional MCP transports (SSE, HTTP)
- [ ] Server management UI
- [ ] Observability and debugging tools
- [ ] Authentication & authorization
- [ ] Rate limiting and usage tracking

## Development Commands

### Backend

```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "description"

# Start server with hot reload
uv run uvicorn src.api.server:app --reload

# Run backend directly
./run_backend.sh
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Rebuild after code changes
docker-compose up -d --build

# Stop all services
docker-compose down

# Clean volumes (removes database data)
docker-compose down -v
```

## Troubleshooting

### Backend Won't Start

1. Check environment variables in `.env`
2. Ensure PostgreSQL is running and accessible
3. Verify Azure OpenAI credentials
4. Check logs: `docker-compose logs backend`

### Database Connection Issues

```bash
# For Docker: Use service name 'postgres' not 'localhost'
DATABASE_URL=postgresql+asyncpg://db_user:db_password@postgres:5432/mcp_chat

# For local dev: Use localhost
DATABASE_URL=postgresql+asyncpg://db_user:db_password@localhost:5432/mcp_chat
```

### MCP Server Connection Failures

1. Verify `config/mcp_servers.json` has correct paths
2. For Docker: Use Docker-compatible paths and service names
3. Check MCP server logs in backend container
4. Ensure npx is available in the container

### Frontend Can't Connect to Backend

1. Check backend is running on port 8000
2. Verify CORS settings in `src/api/server.py`
3. Check browser console for errors
4. Ensure WebSocket connection is established

## Documentation

- [LangGraph Functional API Reference](docs/LANGGRAPH_FUNCTIONAL_API.md)
- [MCP Protocol Documentation](docs/MCP_PROTOCOL.md)
- [Implementation Reference](docs/IMPLEMENTATION_REFERENCE.md)
- [Docker Deployment Guide](DOCKER.md)
- [Claude Code Instructions](CLAUDE.md)

## Contributing

This is a personal project built as a universal MCP client demonstration. Contributions, issues, and feature requests are welcome!

## License

MIT

---

**Built with:**
- LangGraph Functional API for agentic workflows
- Model Context Protocol for tool integration
- Azure OpenAI for intelligent responses
- Docker for easy deployment
