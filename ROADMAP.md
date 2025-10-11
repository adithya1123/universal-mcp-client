# Universal MCP Client - Development Roadmap

## ✅ Phase 1: MVP (COMPLETED)

### What's Built
- [x] Project setup with UV package manager
- [x] MCP client (STDIO transport) - connects to filesystem server
- [x] Azure OpenAI integration (gpt-4o)
- [x] Basic agentic workflow (async functions, no LangGraph decorators)
- [x] FastAPI backend with WebSocket support
- [x] React + TypeScript frontend with chat UI
- [x] In-memory conversation history
- [x] Tool discovery and execution (14 filesystem tools)
- [x] Error handling and conversation reset

### Current Status
✅ **Fully functional chat assistant** that can:
- Chat with Azure OpenAI
- Discover tools from MCP servers
- Execute tools dynamically based on LLM requests
- Maintain conversation context in memory
- Handle errors gracefully

---

## ✅ Phase 2: Persistence & Multi-Server (IN PROGRESS)

### Goals
Add database persistence and support for multiple MCP servers

### Tasks

#### 2.1 Postgres Integration ✅ COMPLETED
- [x] Set up Postgres database (Docker or local) - Docker Compose configured
- [x] Add asyncpg and SQLAlchemy dependencies: `uv add asyncpg sqlalchemy[asyncio] alembic greenlet`
- [x] Create `src/storage/` directory with models and DB helpers
- [x] Create schema for chat history, MCP servers, and LangGraph checkpoints
- [x] Update `src/api/server.py` to use Postgres instead of in-memory dict
- [x] Add connection pooling and error handling
- [x] Add Alembic for database migrations
- [x] Create database initialization script (`scripts/init_db.py`)

#### 2.2 LangGraph Functional API with Checkpointing ✅ COMPLETED
- [x] Define State schema with TypedDict (`src/orchestration/state.py`)
- [x] Implement PostgreSQL checkpointer (`src/orchestration/checkpointer.py`)
- [x] Convert agent to use `@entrypoint` and `@task` decorators properly
- [x] Update call signature to use proper LangGraph patterns with `previous` parameter
- [x] Add checkpoint/resume functionality using `entrypoint.final(value=..., save=...)`
- [x] Test workflow persistence and recovery
- [x] Created local documentation (docs/LANGGRAPH_FUNCTIONAL_API.md, docs/MCP_PROTOCOL.md, docs/IMPLEMENTATION_REFERENCE.md)
- [x] Updated CLAUDE.md with documentation standards

**Note:** Start with Functional API. StateGraph will be added in Phase 3 if needed for complex workflows.

#### 2.3 Multi-Server Support ⚠️ PARTIALLY COMPLETED
- [x] Update `config/mcp_servers.json` to support multiple servers
- [x] MCP client already handles multiple simultaneous connections
- [x] Tool naming already uses server prefix (e.g., `filesystem_read_file`)
- [ ] Add server health monitoring
- [ ] Test with multiple servers (filesystem, github, slack, etc.)

#### 2.4 Server Management UI 🔄 PENDING
- [ ] Create frontend component for server configuration
- [ ] Add/remove servers dynamically
- [ ] Enable/disable servers
- [ ] View server status and available tools

#### 2.5 Additional Transports 🔄 PENDING
- [ ] Add Streamable HTTP transport for all web-based integrations remote MCP servers
- [ ] Update `src/mcp/client.py` to handle different transports

---

## 🔧 Phase 3: Advanced Features

### 3.1 Complex Workflows (StateGraph)
- [ ] Implement LangGraph StateGraph for branching workflows
- [ ] Add conditional routing based on tool results
- [ ] Support parallel tool execution
- [ ] Create specialized nodes for different tasks
- [ ] Add graph visualization

**When to use StateGraph:**
- Multi-agent coordination
- Complex decision trees
- Workflows with loops and conditions
- When Functional API is too limiting

### 3.2 Human-in-the-Loop
- [ ] Add approval system for sensitive operations
- [ ] Implement breakpoints in workflows
- [ ] Create approval UI in frontend

### 3.3 Observability
- [ ] Add Arize Phoenix integration for tracing
- [ ] Implement detailed logging
- [ ] Create debugging dashboard
- [ ] Add performance metrics

### 3.4 Security & Auth
- [ ] Add user authentication
- [ ] Implement API key management
- [ ] Add rate limiting
- [ ] Secure MCP server credentials

---

## 📝 Technical Debt & Improvements

### Code Quality
- [ ] Add unit tests (pytest)
- [ ] Add integration tests
- [ ] Add type hints everywhere
- [ ] Improve error messages

### Performance
- [ ] Implement response streaming for LLM
- [ ] Add caching for tool results
- [ ] Optimize tool discovery

### Developer Experience
- [ ] Add development mode with hot reload
- [ ] Create Docker setup
- [ ] Add CI/CD pipeline
- [ ] Improve documentation

---

## 🐛 Known Issues & Fixes

### Resolved
- ✅ Tool naming with colons (Azure OpenAI compatibility) - fixed with underscores
- ✅ MCP stdio connection closing - fixed by storing context
- ✅ Incomplete tool call sequences - fixed with history validation
- ✅ LangGraph @entrypoint errors - removed decorators for Phase 1

### To Address
- [ ] MCP server cleanup errors (cosmetic, doesn't affect functionality)
- [ ] Better error messages for tool failures
- [ ] Validate tool arguments before execution

---

## 📚 Phase 2 Implementation Guide

### Step 1: Set up Postgres
```bash
# Install Postgres locally or use Docker
docker run -d \
  --name mcp-postgres \
  -e POSTGRES_DB=mcp_chat \
  -e POSTGRES_USER=mcp_user \
  -e POSTGRES_PASSWORD=mcp_pass \
  -p 5432:5432 \
  postgres:15

# Update .env (use asyncpg driver for SQLAlchemy async)
DATABASE_URL=postgresql+asyncpg://mcp_user:mcp_pass@localhost:5432/mcp_chat

# Add dependencies
uv add asyncpg sqlalchemy[asyncio] alembic
```

### Step 2: Create Models
```python
# src/storage/models.py
from sqlalchemy import Column, String, Text, TIMESTAMP, JSON, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class ConversationMessage(Base):
    __tablename__ = 'conversations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text)
    tool_calls = Column(JSON)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

# src/storage/postgres.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

engine = create_async_engine(os.getenv("DATABASE_URL"))
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_conversation_history(session_id: str) -> List[Dict]:
    async with async_session() as session:
        result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content, "tool_calls": m.tool_calls} for m in messages]
```

### Step 3: Add LangGraph Functional API with State
```python
# src/orchestration/agent.py
from typing import TypedDict, List, Dict, Any
from langgraph.func import entrypoint, task
from langgraph.checkpoint.postgres import PostgresSaver

class ChatInput(TypedDict):
    user_message: str
    conversation_history: List[Dict[str, Any]]
    session_id: str

@task
async def call_llm(messages: List[Dict], tools: List[Dict]) -> Dict:
    # LLM call with checkpointing
    pass

@task
async def execute_tool(tool_name: str, arguments: str) -> Dict:
    # Tool execution with checkpointing
    pass

@entrypoint(checkpointer=PostgresSaver(...))
async def chat_agent(input: ChatInput) -> Dict[str, Any]:
    # Agent logic using input dict instead of kwargs
    user_message = input["user_message"]
    history = input["conversation_history"]
    # ... rest of logic
    return {"response": ..., "conversation_history": ...}
```

**Phase 3: Add StateGraph for complex workflows**
```python
# src/orchestration/complex_agent.py
from langgraph.graph import StateGraph, START, END

class ComplexState(TypedDict):
    messages: List[Dict]
    next_action: str

workflow = StateGraph(ComplexState)
workflow.add_node("analyze", analyze_intent)
workflow.add_node("execute", execute_tools)
workflow.add_edge(START, "analyze")
workflow.add_conditional_edges("analyze", route_next)
graph = workflow.compile(checkpointer=PostgresSaver(...))
```

### Step 4: Update Server
```python
# src/api/server.py - Replace in-memory storage
from src.storage.postgres import get_conversation_history, save_message

# In websocket handler
conversation_history = await get_conversation_history(session_id)
# ... process ...
await save_message(session_id, result)
```

---

## 🎯 Success Criteria

### Phase 2 Complete When:
- [ ] All conversations persist to Postgres
- [ ] Can connect to 3+ MCP servers simultaneously
- [ ] LangGraph checkpointing works (can resume interrupted chats)
- [ ] UI can add/remove servers without restart
- [ ] Support both local (STDIO) and remote (SSE) servers

### Phase 3 Complete When:
- [ ] Complex multi-step workflows execute correctly
- [ ] Human approval works for sensitive operations
- [ ] Full observability with LangSmith
- [ ] Production-ready security

---

## 📖 Reference Files

### Key Implementation Files
- `src/mcp/client.py` - MCP client logic
- `src/llm/azure_openai.py` - Azure OpenAI integration
- `src/orchestration/agent.py` - Agent workflow
- `src/api/server.py` - FastAPI endpoints
- `frontend/src/components/Chat.tsx` - Chat UI

### Configuration
- `config/mcp_servers.json` - MCP server definitions
- `.env` - Environment variables
- `pyproject.toml` - Python dependencies

### Documentation
- `README.md` - Setup and usage
- `QUICKSTART.md` - Quick start guide
- `IMPLEMENTATION_SUMMARY.md` - Phase 1 details
- `ROADMAP.md` - This file

---

## 💡 Architecture Decisions

### Why No LangGraph Decorators in Phase 1?
- Simplified implementation
- Easier debugging
- No complex State management needed
- Will add in Phase 2 with proper Postgres checkpointing

### Why UV Package Manager?
- Faster than pip/poetry
- Better dependency resolution
- Native virtual environment handling

### Why Azure OpenAI?
- Enterprise-grade
- Regional deployment options
- Compatible with OpenAI API

### Why FastAPI?
- Async support (critical for MCP)
- WebSocket support
- Auto-generated docs
- Type safety

---

## 🔗 Useful Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
