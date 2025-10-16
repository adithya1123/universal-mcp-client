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

from .models import Base, Session, ConversationMessage, MCPServer, LangGraphCheckpoint

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

    # ========== Session Management Operations ==========

    async def get_sessions(self) -> List[Session]:
        """
        Get all chat sessions ordered by last activity.

        Returns:
            List of session objects
        """
        async with self.session() as session:
            result = await session.execute(
                select(Session).order_by(Session.updated_at.desc())
            )
            return result.scalars().all()

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a specific session by session_id.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        async with self.session() as session:
            result = await session.execute(
                select(Session).where(Session.session_id == session_id)
            )
            return result.scalar_one_or_none()

    async def create_session(
        self,
        session_id: str,
        title: str = "New Conversation",
        description: Optional[str] = None,
    ) -> Session:
        """
        Create a new chat session.

        Args:
            session_id: Unique session identifier
            title: Session title
            description: Optional session description

        Returns:
            Created session object
        """
        async with self.session() as session:
            new_session = Session(
                session_id=session_id,
                title=title,
                description=description,
                message_count="0",
            )
            session.add(new_session)
            await session.flush()
            await session.refresh(new_session)
            return new_session

    async def update_session(
        self,
        session_id: str,
        **kwargs,
    ) -> Optional[Session]:
        """
        Update a session's metadata.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update (title, description, etc.)

        Returns:
            Updated session object or None if not found
        """
        async with self.session() as session:
            result = await session.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                for key, value in kwargs.items():
                    if hasattr(session_obj, key):
                        setattr(session_obj, key, value)
                session_obj.updated_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(session_obj)
            return session_obj

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        async with self.session() as session:
            # Delete all messages first
            await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.session_id == session_id
                )
            )

            # Delete the session
            result = await session.execute(
                delete(Session).where(Session.session_id == session_id)
            )
            return result.rowcount > 0

    async def update_session_activity(self, session_id: str, message_count: int):
        """
        Update session's last activity time and message count.

        Args:
            session_id: Session identifier
            message_count: New message count
        """
        await self.update_session(
            session_id,
            last_message_at=datetime.now(timezone.utc),
            message_count=str(message_count),
        )

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
        command: Optional[str] = None,
        description: Optional[str] = None,
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
            command: Server command (optional, only needed for stdio transport)
            description: Optional server description
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
                description=description,
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
