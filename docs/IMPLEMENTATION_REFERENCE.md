# Implementation Reference - Universal MCP Client

**Project:** Universal MCP Client with LangGraph + PostgreSQL
**Last Updated:** January 2025

---

## Quick Reference

### Start Application
```bash
# 1. Start Postgres
docker compose up -d

# 2. Initialize database
uv run python scripts/init_db.py

# 3. Start backend
./run_backend.sh

# 4. Start frontend
cd frontend && npm run dev
```

### Access
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## Project Structure

```
universal-mcp-client/
├── src/
│   ├── api/
│   │   └── server.py          # FastAPI server with WebSocket
│   ├── llm/
│   │   └── azure_openai.py    # Azure OpenAI client
│   ├── mcp/
│   │   └── client.py          # MCP client (multi-server)
│   ├── orchestration/
│   │   ├── agent.py           # LangGraph agent with @task/@entrypoint
│   │   ├── state.py           # TypedDict state definitions
│   │   └── checkpointer.py    # PostgreSQL checkpointer
│   └── storage/
│       ├── models.py          # SQLAlchemy models
│       └── database.py        # Database manager
├── config/
│   └── mcp_servers.json       # MCP server configurations
├── frontend/                  # React + TypeScript UI
├── docs/                      # Documentation (local reference)
│   ├── LANGGRAPH_FUNCTIONAL_API.md
│   ├── MCP_PROTOCOL.md
│   └── IMPLEMENTATION_REFERENCE.md
├── scripts/
│   └── init_db.py            # Database initialization
├── docker-compose.yml         # Postgres container
└── .env                       # Environment variables
```

---

## Core Components

### 1. LangGraph Agent (src/orchestration/agent.py)

**Key Functions:**

```python
# Initialize clients at startup
initialize_clients(mcp_client, llm_client, db_manager)

# Main agent (invoked via .ainvoke())
@entrypoint(checkpointer=_get_checkpointer)
async def chat_agent(
    inputs: Dict[str, Any],
    *,
    previous: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]

# LLM task
@task
async def call_llm_task(state: ChatState) -> ChatState

# Tool execution task
@task
async def execute_tools_task(state: ChatState) -> ChatState
```

**Invocation Pattern:**
```python
config = {"configurable": {"thread_id": session_id}}
result = await chat_agent.ainvoke(
    {
        "user_message": "Hello",
        "conversation_history": [...],
        "session_id": session_id
    },
    config=config
)
```

**State Management:**
- Uses `ChatState` TypedDict internally
- `previous` parameter provides saved state from checkpoint
- `entrypoint.final(value=..., save=...)` separates return vs save

### 2. PostgreSQL Checkpointer (src/orchestration/checkpointer.py)

```python
class PostgresCheckpointSaver(BaseCheckpointSaver):
    async def aget(config) -> Optional[Checkpoint]
    async def aput(config, checkpoint, metadata) -> Dict
    async def alist(config, limit) -> list[Checkpoint]
```

**Database Table:** `langgraph_checkpoints`
- Stores workflow state by session_id (thread_id)
- Enables resumable conversations
- Automatic state persistence

### 3. Database Manager (src/storage/database.py)

```python
class DatabaseManager:
    # Chat history
    async def get_conversation_history(session_id: str) -> List[Dict]
    async def save_message(session_id, role, content, ...) -> ConversationMessage
    async def clear_conversation(session_id: str) -> int

    # MCP servers
    async def get_mcp_servers(enabled_only=False) -> List[MCPServer]
    async def create_mcp_server(...) -> MCPServer
    async def update_mcp_server(server_id, **kwargs) -> Optional[MCPServer]
    async def delete_mcp_server(server_id) -> bool

    # Checkpoints
    async def save_checkpoint(...) -> LangGraphCheckpoint
    async def get_latest_checkpoint(session_id) -> Optional[LangGraphCheckpoint]
```

### 4. MCP Client (src/mcp/client.py)

```python
class MCPClient:
    async def load_servers()                              # Load from config
    async def call_tool(tool_name: str, arguments: dict)  # Execute tool
    def get_tools_for_llm() -> List[Dict]                # Get OpenAI format tools
    async def close()                                     # Cleanup
```

**Tool Naming:** `{server_name}_{tool_name}` (e.g., `filesystem_read_file`)

### 5. FastAPI Server (src/api/server.py)

**Endpoints:**

```python
# Health & Info
GET  /                           # Root
GET  /health                     # Health check
GET  /tools                      # List all tools

# Chat
POST /chat                       # REST chat endpoint
POST /chat/reset?session_id=X    # Clear history
GET  /chat/history/{session_id}  # Get history
WS   /ws/chat                    # WebSocket chat
```

---

## Database Schema

### Tables

```sql
-- Chat history
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls JSONB,
    tool_call_id VARCHAR(255),
    name VARCHAR(255),
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_session_id ON conversations(session_id);

-- MCP servers
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    command VARCHAR(255) NOT NULL,
    args JSONB,
    env JSONB,
    transport_type VARCHAR(50) DEFAULT 'stdio',
    url VARCHAR(512),
    enabled BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(50) DEFAULT 'unknown',
    last_health_check TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- LangGraph checkpoints
CREATE TABLE langgraph_checkpoints (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_checkpoint_id VARCHAR(255),
    state JSONB NOT NULL,
    checkpoint_metadata JSONB,
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_checkpoint_session ON langgraph_checkpoints(session_id);
```

---

## Configuration

### Environment Variables (.env)

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://mcp_user:mcp_pass@localhost:5432/mcp_chat

# App
DEBUG=true
LOG_LEVEL=INFO
```

### MCP Servers (config/mcp_servers.json)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "transport": "stdio"
    }
  }
}
```

---

## Common Operations

### Add New MCP Server

```python
# Via API (future)
POST /servers
{
  "name": "github",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {"GITHUB_TOKEN": "..."}
}

# Via database
await db_manager.create_mcp_server(
    name="github",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={"GITHUB_TOKEN": "..."}
)
```

### Query Chat History

```python
# Get conversation
history = await db_manager.get_conversation_history("user-123")

# Clear conversation
deleted = await db_manager.clear_conversation("user-123")
```

### Check Checkpoint State

```python
# Get latest checkpoint
checkpoint = await db_manager.get_latest_checkpoint("user-123")
print(f"State: {checkpoint.state}")
print(f"Created: {checkpoint.created_at}")
```

---

## API Usage Examples

### REST API

```bash
# Send message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "user-1"}'

# Get history
curl http://localhost:8000/chat/history/user-1

# Reset conversation
curl -X POST "http://localhost:8000/chat/reset?session_id=user-1"

# List tools
curl http://localhost:8000/tools
```

### WebSocket API

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({
    message: "Hello",
    session_id: "user-1"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.response);
};
```

---

## Testing

### Test Database Connection

```bash
uv run python -c "
from src.storage.database import get_db_manager
import asyncio

async def test():
    db = get_db_manager()
    history = await db.get_conversation_history('test')
    print(f'✅ Connection OK! Found {len(history)} messages')

asyncio.run(test())
"
```

### Test MCP Server

```bash
uv run python -c "
from src.mcp.client import MCPClient
import asyncio

async def test():
    client = MCPClient()
    await client.load_servers()
    tools = client.get_tools_for_llm()
    print(f'✅ Found {len(tools)} tools')
    await client.close()

asyncio.run(test())
"
```

### Test Agent

```bash
uv run python -c "
from src.orchestration.agent import chat_agent
import asyncio

async def test():
    config = {'configurable': {'thread_id': 'test'}}
    result = await chat_agent.ainvoke(
        {'user_message': 'Hello', 'session_id': 'test'},
        config=config
    )
    print(f'✅ Response: {result[\"response\"][:50]}...')

asyncio.run(test())
"
```

---

## Troubleshooting

### Issue: "Database not initialized"
```bash
# Solution: Initialize database
uv run python scripts/init_db.py
```

### Issue: "MCP client not initialized"
```bash
# Solution: Check config/mcp_servers.json exists
cat config/mcp_servers.json

# Restart backend
./run_backend.sh
```

### Issue: "Postgres connection refused"
```bash
# Solution: Start Postgres
docker compose up -d

# Check status
docker compose ps
```

### Issue: "LangGraph TypeError"
```bash
# Solution: Ensure correct invocation pattern
config = {"configurable": {"thread_id": session_id}}
result = await chat_agent.ainvoke(inputs, config=config)  # ✅
result = await chat_agent(inputs)  # ❌ Wrong!
```

---

## Development Workflow

### 1. Code Changes
- Edit files in `src/`
- Backend auto-reloads (via `--reload`)
- Frontend hot-reloads (via Vite)

### 2. Database Changes
```bash
# Update models in src/storage/models.py
# Recreate tables
docker compose down -v  # WARNING: Deletes data!
docker compose up -d
uv run python scripts/init_db.py
```

### 3. Add New Tool
- Update MCP server config
- Restart backend
- Tools auto-discovered

### 4. Testing
```bash
# Run backend tests (when implemented)
uv run pytest

# Check code style
uv run ruff check src/

# Format code
uv run ruff format src/
```

---

## Performance Tuning

### Database
```python
# Connection pool settings (database.py)
pool_size=5          # Normal connections
max_overflow=10      # Burst connections
pool_pre_ping=True   # Health checks
```

### Checkpointing
- Checkpoints saved after each @task execution
- Balance: persistence vs performance
- Clean up old checkpoints periodically

### Caching
- MCP tools cached after discovery
- Conversation history cached in Postgres
- Consider Redis for session caching (future)

---

## Security Considerations

1. **API Keys:** Store in `.env`, never commit
2. **Database:** Use strong passwords, enable SSL
3. **MCP Servers:** Validate tool arguments
4. **CORS:** Configure `allow_origins` for production
5. **Rate Limiting:** Add rate limiting (future)

---

## Next Steps

### Phase 3 Features
- StateGraph for complex workflows
- Human-in-the-loop approval system
- Arize Phoenix observability
- User authentication
- Multi-user support
- Server management UI

### Optimization
- Response streaming
- Tool result caching
- Connection pooling optimization
- Database query optimization

---

## Key Learnings

### LangGraph Functional API
- ✅ Use `@entrypoint(checkpointer=func)` not lambda
- ✅ Include `previous` parameter (keyword-only)
- ✅ Use `entrypoint.final(value=..., save=...)`
- ✅ Invoke with `.ainvoke(inputs, config)`
- ✅ Pass `thread_id` in config for checkpointing

### MCP Integration
- ✅ Use server prefix in tool names
- ✅ Store MCP client contexts
- ✅ Handle stdio cleanup properly
- ✅ Support multiple servers simultaneously

### Database Design
- ✅ Separate tables for history, servers, checkpoints
- ✅ JSON columns for flexible data
- ✅ Indexes on session_id for fast lookups
- ✅ Async operations throughout

---

## Documentation References

- **Local Docs:**
  - `docs/LANGGRAPH_FUNCTIONAL_API.md` - Complete LangGraph reference
  - `docs/MCP_PROTOCOL.md` - Complete MCP protocol reference
  - `docs/IMPLEMENTATION_REFERENCE.md` - This file

- **External Docs:**
  - LangGraph: https://langchain-ai.github.io/langgraph/
  - MCP: https://modelcontextprotocol.io/
  - FastAPI: https://fastapi.tiangolo.com/
  - SQLAlchemy: https://docs.sqlalchemy.org/

---

## Support

For issues or questions:
1. Check local documentation first
2. Review error logs in terminal
3. Check database connectivity
4. Verify MCP server configuration
5. Test with simplified inputs

**Remember:** Documentation is local and always available offline!
