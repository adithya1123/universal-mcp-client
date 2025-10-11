"""FastAPI server with WebSocket support for real-time chat and Postgres persistence."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.mcp.client import MCPClient
from src.llm.azure_openai import AzureOpenAIClient
from src.orchestration import agent as agent_module
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
    """Lifecycle manager for the FastAPI app."""
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

        # Initialize LangGraph agent with clients
        await agent_module.initialize_clients(mcp_client, llm_client, db_manager)
        logger.info("✅ LangGraph agent initialized")

        logger.info("✅ All systems ready!")

    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise

    yield

    # Shutdown: Clean up
    logger.info("🛑 Shutting down...")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
