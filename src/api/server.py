"""FastAPI server with WebSocket support for real-time chat and Postgres persistence."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.mcp.client import MCPClient
from src.llm.azure_openai import AzureOpenAIClient
from src.orchestration import agent as agent_module
from src.orchestration.approval import get_approval_manager
from src.storage.database import DatabaseManager, get_db_manager, init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
mcp_client: Optional[MCPClient] = None
llm_client: Optional[AzureOpenAIClient] = None
db_manager: Optional[DatabaseManager] = None
active_connections: List[WebSocket] = []


def read_config_file():
    """Read MCP servers configuration from JSON file."""
    from pathlib import Path
    config_path = Path("config/mcp_servers.json")
    with open(config_path, "r") as f:
        return json.load(f)


def write_config_file(config):
    """Write MCP servers configuration to JSON file."""
    from pathlib import Path
    config_path = Path("config/mcp_servers.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")  # Add trailing newline


async def sync_config_to_json(server, operation="create"):
    """Sync server changes to mcp_servers.json file.

    Args:
        server: MCPServer database model instance
        operation: "create", "update", or "delete"
    """
    try:
        config = read_config_file()
        servers = config.get("servers", [])

        if operation == "delete":
            # Remove server from config
            servers = [s for s in servers if s.get("name") != server.name]
            logger.info(f"Removed '{server.name}' from config file")
        else:
            # Convert database model to config format
            server_config = {
                "name": server.name,
                "description": server.description,
                "transport": server.transport_type,
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "url": server.url,
                "enabled": server.enabled
            }

            # Remove empty/None fields for cleaner JSON
            server_config = {k: v for k, v in server_config.items() if v is not None and v != ""}

            if operation == "create":
                # Add new server
                servers.append(server_config)
                logger.info(f"Added '{server.name}' to config file")
            elif operation == "update":
                # Update existing server
                servers = [server_config if s.get("name") == server.name else s for s in servers]
                logger.info(f"Updated '{server.name}' in config file")

        config["servers"] = servers
        write_config_file(config)

    except Exception as e:
        logger.error(f"Failed to sync config file: {e}", exc_info=True)
        raise


async def sync_mcp_servers_from_config():
    """Sync MCP servers from config/mcp_servers.json to database."""
    if not db_manager:
        logger.warning("Database not initialized, skipping server sync")
        return

    try:
        from pathlib import Path

        config_path = Path("config/mcp_servers.json")
        if not config_path.exists():
            logger.warning(f"MCP servers config not found at {config_path}")
            return

        config = read_config_file()
        servers = config.get("servers", [])
        logger.info(f"Syncing {len(servers)} servers from config to database...")

        synced_count = 0
        for server_config in servers:
            name = server_config.get("name")
            if not name:
                continue

            # Check if server already exists
            existing = await db_manager.get_mcp_servers(enabled_only=False)
            existing_names = {s.name for s in existing}

            if name in existing_names:
                logger.debug(f"Server '{name}' already exists, skipping")
                continue

            # Map transport type
            transport = server_config.get("transport", "stdio")
            if transport == "stdio":
                transport_type = "stdio"
            elif transport in ["http", "sse"]:
                transport_type = "http"
            else:
                transport_type = transport

            # Create server in database
            await db_manager.create_mcp_server(
                name=name,
                description=server_config.get("description"),
                command=server_config.get("command", ""),
                args=server_config.get("args"),
                env=server_config.get("env"),
                transport_type=transport_type,
                url=server_config.get("url"),
                enabled=server_config.get("enabled", True)
            )
            logger.info(f"✅ Added server '{name}' to database")
            synced_count += 1

        if synced_count > 0:
            logger.info(f"✅ Server sync complete: {synced_count} new server(s) added")
        else:
            logger.info("✅ Server sync complete: all servers already in database")

    except Exception as e:
        logger.error(f"Failed to sync servers from config: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app with proper checkpointer management."""
    global mcp_client, llm_client, db_manager

    # Startup: Initialize clients
    logger.info("🚀 Starting Universal MCP Client...")

    try:
        # Initialize database
        logger.info("Initializing database...")
        db_manager = get_db_manager()
        await init_database()
        logger.info("✅ Database initialized")

        # Sync MCP servers from config to database
        await sync_mcp_servers_from_config()

        # Initialize MCP client and connect to servers
        logger.info("Loading MCP servers...")
        mcp_client = MCPClient()
        await mcp_client.load_servers()
        logger.info(f"✅ Connected to {len(mcp_client.servers)} MCP server(s)")

        # Initialize Azure OpenAI client
        logger.info("Initializing Azure OpenAI client...")
        llm_client = AzureOpenAIClient()
        logger.info("✅ Azure OpenAI client initialized")

        # Get database URL for checkpointer
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            logger.warning("DATABASE_URL not set - running without LangGraph checkpointing")
            # Initialize agent without checkpointer
            await agent_module.initialize_clients(mcp_client, llm_client, db_manager, checkpointer=None)
            logger.info("✅ LangGraph agent initialized (no checkpointing)")
        else:
            # Convert asyncpg to psycopg format for LangGraph
            checkpointer_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            logger.info("Initializing LangGraph PostgreSQL checkpointer...")

            # Use AsyncPostgresSaver with proper context manager
            async with AsyncPostgresSaver.from_conn_string(checkpointer_url) as checkpointer:
                # Setup tables (first time only - idempotent operation)
                await checkpointer.setup()
                logger.info("✅ PostgreSQL checkpointer initialized and tables created")

                # Initialize LangGraph agent with checkpointer
                await agent_module.initialize_clients(mcp_client, llm_client, db_manager, checkpointer=checkpointer)
                logger.info("✅ LangGraph agent initialized with checkpointing")

                logger.info("✅ All systems ready!")

                yield  # Application runs here with active checkpointer

                # Checkpointer cleanup happens automatically on context exit
                logger.info("🛑 Shutting down checkpointer...")

    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    finally:
        # Shutdown: Clean up other resources
        logger.info("🛑 Shutting down remaining resources...")
        if mcp_client:
            await mcp_client.close()
        if db_manager:
            await db_manager.close()
        logger.info("✅ Cleanup complete")


app = FastAPI(
    title="Universal MCP Client",
    description="Agentic chat assistant with universal MCP server connectivity",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    session_id: str


# REST endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Universal MCP Client API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mcp_servers": list(mcp_client.servers.keys()) if mcp_client else [],
        "available_tools": len(mcp_client.tools) if mcp_client else 0
    }


@app.get("/tools")
async def list_tools():
    """List all available tools from MCP servers."""
    if not mcp_client:
        raise HTTPException(status_code=500, detail="MCP client not initialized")

    return {
        "tools": [
            {
                "key": key,
                "name": info["name"],
                "description": info["description"],
                "server": info["server"]
            }
            for key, info in mcp_client.tools.items()
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Process a chat message (REST endpoint) with Postgres persistence."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    session_id = message.session_id

    try:
        # Get conversation history from database
        conversation_history = await db_manager.get_conversation_history(session_id)

        # Process message with agent (using @entrypoint with checkpointing)
        # LangGraph requires config with thread_id for checkpointing
        config = {"configurable": {"thread_id": session_id}}
        result = await agent_module.chat_agent.ainvoke(
            {"user_message": message.message, "conversation_history": conversation_history, "session_id": session_id},
            config=config
        )

        # Save messages to database
        # Save user message
        await db_manager.save_message(
            session_id=session_id,
            role="user",
            content=message.message,
        )

        # Save assistant response
        await db_manager.save_message(
            session_id=session_id,
            role="assistant",
            content=result["response"],
        )

        return ChatResponse(
            response=result["response"],
            session_id=session_id
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(message: ChatMessage):
    """Process a chat message with Server-Sent Events (SSE) streaming."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    session_id = message.session_id

    async def event_generator():
        """Generate SSE events from the streaming agent."""
        try:
            # Get conversation history from database
            conversation_history = await db_manager.get_conversation_history(session_id)

            # Stream events from agent
            async for event in agent_module.chat_agent_stream(
                user_message=message.message,
                session_id=session_id,
                conversation_history=conversation_history
            ):
                # Format as SSE
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            error_event = {"type": "error", "data": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/chat/reset")
async def reset_conversation(session_id: str = "default"):
    """Clear conversation history for a session."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        deleted_count = await db_manager.clear_conversation(session_id)
        return {
            "message": f"Conversation reset successfully",
            "session_id": session_id,
            "deleted_messages": deleted_count
        }
    except Exception as e:
        logger.error(f"Reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        history = await db_manager.get_conversation_history(session_id)
        return {
            "session_id": session_id,
            "messages": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Session Management Endpoints
@app.get("/sessions")
async def list_sessions():
    """Get all chat sessions."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        sessions = await db_manager.get_sessions()
        return {
            "sessions": [session.to_dict() for session in sessions],
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get session information."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        session = await db_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SessionCreate(BaseModel):
    session_id: str
    title: str = "New Conversation"
    description: Optional[str] = None


@app.post("/sessions")
async def create_new_session(session_data: SessionCreate):
    """Create a new chat session."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        # Check if session already exists
        existing = await db_manager.get_session(session_data.session_id)
        if existing:
            raise HTTPException(status_code=400, detail="Session already exists")

        session = await db_manager.create_session(
            session_id=session_data.session_id,
            title=session_data.title,
            description=session_data.description
        )
        return session.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


@app.put("/sessions/{session_id}")
async def update_session_info(session_id: str, session_data: SessionUpdate):
    """Update session metadata."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        update_data = session_data.dict(exclude_unset=True)
        session = await db_manager.update_session(session_id, **update_data)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session and all its messages."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        success = await db_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"message": "Session deleted successfully", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Tool Execution Approval Endpoints
class ApprovalDecision(BaseModel):
    approved: bool
    tool_ids: Optional[List[str]] = None  # None means all tools
    reason: Optional[str] = None


@app.get("/approvals/pending")
async def list_pending_approvals(session_id: Optional[str] = None):
    """Get all pending approval requests, optionally filtered by session."""
    approval_manager = get_approval_manager()
    requests = approval_manager.get_pending_requests(session_id=session_id)

    return {
        "pending_requests": [req.to_dict() for req in requests],
        "count": len(requests)
    }


@app.get("/approvals/{request_id}")
async def get_approval_request(request_id: str):
    """Get a specific approval request."""
    approval_manager = get_approval_manager()
    request = approval_manager.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return request.to_dict()


@app.post("/approvals/{request_id}")
async def approve_or_reject_tools(request_id: str, decision: ApprovalDecision):
    """Approve or reject tool execution."""
    approval_manager = get_approval_manager()
    request = approval_manager.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is no longer pending (status: {request.status})")

    try:
        if decision.approved:
            request.approve(tool_ids=decision.tool_ids)
            return {
                "message": "Tool execution approved",
                "request_id": request_id,
                "approved_tools": request.approved_tools
            }
        else:
            request.reject(tool_ids=decision.tool_ids, reason=decision.reason)
            return {
                "message": "Tool execution rejected",
                "request_id": request_id,
                "rejected_tools": request.rejected_tools,
                "reason": decision.reason
            }
    except Exception as e:
        logger.error(f"Approval decision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# MCP Server Management Endpoints
class MCPServerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    command: Optional[str] = ""  # Optional - only needed for stdio transport
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    transport_type: str = "stdio"  # stdio, http, sse
    url: Optional[str] = None
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    transport_type: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None


@app.get("/mcp-servers")
async def list_mcp_servers(enabled_only: bool = False):
    """Get all MCP server configurations."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        servers = await db_manager.get_mcp_servers(enabled_only=enabled_only)
        return {
            "servers": [server.to_dict() for server in servers],
            "count": len(servers)
        }
    except Exception as e:
        logger.error(f"List MCP servers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp-servers/{server_id}")
async def get_mcp_server(server_id: str):
    """Get a specific MCP server configuration."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        server = await db_manager.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        return server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get MCP server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp-servers")
async def create_mcp_server(server_data: MCPServerCreate):
    """Create a new MCP server configuration."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        # Create server in database
        server = await db_manager.create_mcp_server(
            name=server_data.name,
            description=server_data.description,
            command=server_data.command,
            args=server_data.args,
            env=server_data.env,
            transport_type=server_data.transport_type,
            url=server_data.url,
            enabled=server_data.enabled
        )

        # Sync to config file
        await sync_config_to_json(server, operation="create")

        logger.info(f"✅ Created MCP server: {server.name} (restart required to load)")

        return server.to_dict()
    except Exception as e:
        logger.error(f"Create MCP server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/mcp-servers/{server_id}")
async def update_mcp_server(server_id: str, server_data: MCPServerUpdate):
    """Update an MCP server configuration."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        update_data = server_data.dict(exclude_unset=True)
        server = await db_manager.update_mcp_server(server_id, **update_data)

        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # Sync to config file
        await sync_config_to_json(server, operation="update")

        logger.info(f"✅ Updated MCP server: {server.name} (restart required to apply changes)")

        return server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update MCP server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str):
    """Delete an MCP server configuration."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        # Get server details before deleting (needed for config sync)
        server = await db_manager.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # Delete from database
        success = await db_manager.delete_mcp_server(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # Sync to config file
        await sync_config_to_json(server, operation="delete")

        logger.info(f"✅ Deleted MCP server: {server.name} (restart required to remove)")

        return {"message": "MCP server deleted successfully", "server_id": server_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete MCP server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp-servers/{server_id}/test")
async def test_mcp_server_connection(server_id: str):
    """Test connection to an MCP server."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        server = await db_manager.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # TODO: Implement actual connection test
        # For now, just update health status to indicate we tried
        await db_manager.update_server_health(server_id, "unknown")

        return {
            "message": "Connection test not yet implemented",
            "server_id": server_id,
            "status": "unknown"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test MCP server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time streaming
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with streaming and Postgres persistence."""
    await websocket.accept()
    active_connections.append(websocket)

    session_id = "default"

    try:
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to Universal MCP Client",
            "available_tools": len(mcp_client.tools) if mcp_client else 0
        })

        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)

            user_message = message_data.get("message")
            session_id = message_data.get("session_id", "default")

            if not user_message:
                continue

            # Send processing indicator
            await websocket.send_json({
                "type": "processing",
                "message": "Processing your request..."
            })

            # Process message with agent
            try:
                # Get conversation history from database
                conversation_history = await db_manager.get_conversation_history(session_id)

                # Process with agent (using @entrypoint with checkpointing)
                # LangGraph requires config with thread_id for checkpointing
                config = {"configurable": {"thread_id": session_id}}
                result = await agent_module.chat_agent.ainvoke(
                    {"user_message": user_message, "conversation_history": conversation_history, "session_id": session_id},
                    config=config
                )

                # Save user message to database
                await db_manager.save_message(
                    session_id=session_id,
                    role="user",
                    content=user_message,
                )

                # Save assistant response to database
                await db_manager.save_message(
                    session_id=session_id,
                    role="assistant",
                    content=result["response"],
                )

                # Send response
                await websocket.send_json({
                    "type": "message",
                    "response": result["response"],
                    "session_id": session_id
                })

            except Exception as e:
                error_msg = str(e) if str(e) else repr(e)
                logger.error(f"WebSocket chat error: {error_msg}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error: {error_msg}"
                })

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"Client disconnected (session: {session_id})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
