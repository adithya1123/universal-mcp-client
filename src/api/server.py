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
    uvicorn.run(app, host="0.0.0.0", port=8000)
