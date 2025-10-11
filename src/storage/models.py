"""
SQLAlchemy models for database tables.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, String, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ConversationMessage(Base):
    """
    Store conversation history for context management.
    Each message represents a single turn in the conversation.
    """
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'tool'
    content = Column(Text, nullable=True)  # Message content (can be null for tool calls)
    tool_calls = Column(JSON, nullable=True)  # Tool call information
    tool_call_id = Column(String(255), nullable=True)  # For tool response messages
    name = Column(String(255), nullable=True)  # Tool name for tool responses
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        """Convert to OpenAI message format."""
        message = {
            "role": self.role,
        }

        if self.content:
            message["content"] = self.content

        if self.tool_calls:
            message["tool_calls"] = self.tool_calls

        if self.tool_call_id:
            message["tool_call_id"] = self.tool_call_id

        if self.name:
            message["name"] = self.name

        return message


class MCPServer(Base):
    """
    Store MCP server configurations.
    Allows dynamic server management through the UI.
    """
    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    command = Column(String(255), nullable=False)
    args = Column(JSON, nullable=True)  # Command arguments as list
    env = Column(JSON, nullable=True)  # Environment variables
    transport_type = Column(String(50), default="stdio", nullable=False)  # stdio, sse, http
    url = Column(String(512), nullable=True)  # For HTTP/SSE transports
    enabled = Column(Boolean, default=True, nullable=False)
    health_status = Column(String(50), default="unknown")  # unknown, healthy, unhealthy
    last_health_check = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "id": str(self.id),
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "transport_type": self.transport_type,
            "url": self.url,
            "enabled": self.enabled,
            "health_status": self.health_status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class LangGraphCheckpoint(Base):
    """
    Store LangGraph checkpoints for workflow persistence.
    This allows resuming interrupted conversations.
    """
    __tablename__ = "langgraph_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), index=True, nullable=False)
    checkpoint_id = Column(String(255), nullable=False)
    parent_checkpoint_id = Column(String(255), nullable=True)
    state = Column(JSON, nullable=False)  # Full workflow state
    checkpoint_metadata = Column(JSON, nullable=True)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "id": str(self.id),
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "state": self.state,
            "checkpoint_metadata": self.checkpoint_metadata,
            "created_at": self.created_at.isoformat(),
        }
