"""
Database manager for connection pooling and operations.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from .models import Base, ConversationMessage, MCPServer, LangGraphCheckpoint

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and operations.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL (defaults to DATABASE_URL env var)
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Create async engine with connection pooling
        self.engine = create_async_engine(
            self.database_url,
            echo=os.getenv("DEBUG", "false").lower() == "true",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

        # Create session factory
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    async def drop_tables(self):
        """Drop all database tables (use with caution)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")

    @asynccontextmanager
    async def session(self):
        """
        Get a database session context manager.

        Usage:
            async with db_manager.session() as session:
                result = await session.execute(query)
        """
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise

    # ========== Conversation History Operations ==========

    async def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of messages in OpenAI format
        """
        async with self.session() as session:
            result = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at)
            )
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> ConversationMessage:
        """
        Save a message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, tool)
            content: Message content
            tool_calls: Tool call information
            tool_call_id: Tool call ID (for tool responses)
            name: Tool name (for tool responses)

        Returns:
            Created message object
        """
        async with self.session() as session:
            message = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                name=name,
            )
            session.add(message)
            await session.flush()
            await session.refresh(message)
            return message

    async def clear_conversation(self, session_id: str) -> int:
        """
        Clear all messages for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of messages deleted
        """
        async with self.session() as session:
            result = await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.session_id == session_id
                )
            )
            return result.rowcount

    # ========== MCP Server Operations ==========

    async def get_mcp_servers(self, enabled_only: bool = False) -> List[MCPServer]:
        """
        Get all MCP server configurations.

        Args:
            enabled_only: Return only enabled servers

        Returns:
            List of MCP server objects
        """
        async with self.session() as session:
            query = select(MCPServer)
            if enabled_only:
                query = query.where(MCPServer.enabled == True)
            result = await session.execute(query)
            return result.scalars().all()

    async def get_mcp_server(self, server_id: str) -> Optional[MCPServer]:
        """Get a specific MCP server by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(MCPServer).where(MCPServer.id == server_id)
            )
            return result.scalar_one_or_none()

    async def create_mcp_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        transport_type: str = "stdio",
        url: Optional[str] = None,
        enabled: bool = True,
    ) -> MCPServer:
        """
        Create a new MCP server configuration.

        Args:
            name: Server name
            command: Server command
            args: Command arguments
            env: Environment variables
            transport_type: Transport type (stdio, sse, http)
            url: URL for HTTP/SSE transports
            enabled: Whether server is enabled

        Returns:
            Created server object
        """
        async with self.session() as session:
            server = MCPServer(
                name=name,
                command=command,
                args=args,
                env=env,
                transport_type=transport_type,
                url=url,
                enabled=enabled,
            )
            session.add(server)
            await session.flush()
            await session.refresh(server)
            return server

    async def update_mcp_server(
        self,
        server_id: str,
        **kwargs,
    ) -> Optional[MCPServer]:
        """
        Update an MCP server configuration.

        Args:
            server_id: Server ID
            **kwargs: Fields to update

        Returns:
            Updated server object or None if not found
        """
        async with self.session() as session:
            result = await session.execute(
                select(MCPServer).where(MCPServer.id == server_id)
            )
            server = result.scalar_one_or_none()
            if server:
                for key, value in kwargs.items():
                    setattr(server, key, value)
                await session.flush()
                await session.refresh(server)
            return server

    async def delete_mcp_server(self, server_id: str) -> bool:
        """
        Delete an MCP server configuration.

        Args:
            server_id: Server ID

        Returns:
            True if deleted, False if not found
        """
        async with self.session() as session:
            result = await session.execute(
                delete(MCPServer).where(MCPServer.id == server_id)
            )
            return result.rowcount > 0

    async def update_server_health(
        self,
        server_id: str,
        status: str,
    ) -> Optional[MCPServer]:
        """
        Update server health status.

        Args:
            server_id: Server ID
            status: Health status (healthy, unhealthy, unknown)

        Returns:
            Updated server object or None if not found
        """
        return await self.update_mcp_server(
            server_id,
            health_status=status,
            last_health_check=datetime.now(timezone.utc),
        )

    # ========== LangGraph Checkpoint Operations ==========

    async def save_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        state: Dict[str, Any],
        parent_checkpoint_id: Optional[str] = None,
        checkpoint_metadata: Optional[Dict[str, Any]] = None,
    ) -> LangGraphCheckpoint:
        """
        Save a LangGraph checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_id: Checkpoint identifier
            state: Workflow state
            parent_checkpoint_id: Parent checkpoint ID
            checkpoint_metadata: Additional metadata

        Returns:
            Created checkpoint object
        """
        async with self.session() as session:
            checkpoint = LangGraphCheckpoint(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
                state=state,
                checkpoint_metadata=checkpoint_metadata,
            )
            session.add(checkpoint)
            await session.flush()
            await session.refresh(checkpoint)
            return checkpoint

    async def get_latest_checkpoint(
        self,
        session_id: str,
    ) -> Optional[LangGraphCheckpoint]:
        """
        Get the latest checkpoint for a session.

        Args:
            session_id: Session identifier

        Returns:
            Latest checkpoint object or None
        """
        async with self.session() as session:
            result = await session.execute(
                select(LangGraphCheckpoint)
                .where(LangGraphCheckpoint.session_id == session_id)
                .order_by(LangGraphCheckpoint.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get or create the global database manager instance.

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database():
    """Initialize database (create tables)."""
    db_manager = get_db_manager()
    await db_manager.create_tables()
    logger.info("Database initialized successfully")
