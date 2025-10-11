"""
PostgreSQL checkpointer for LangGraph using official AsyncPostgresSaver.
"""

import logging
import os

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)


async def create_checkpointer() -> AsyncPostgresSaver:
    """
    Create an AsyncPostgresSaver instance using the official LangGraph implementation.

    Returns:
        AsyncPostgresSaver instance

    Note:
        Uses DATABASE_URL from environment. The connection string should use
        psycopg format: postgresql://user:pass@host:port/dbname
    """
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Convert asyncpg to psycopg format if needed
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        logger.info("Converted DATABASE_URL from asyncpg to psycopg format")

    # Create connection pool with required settings
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }

    pool = AsyncConnectionPool(
        conninfo=db_url,
        max_size=20,
        kwargs=connection_kwargs,
    )

    # Create checkpointer with connection pool (direct instantiation)
    checkpointer = AsyncPostgresSaver(pool)

    # Setup tables using the context manager approach
    async with AsyncPostgresSaver.from_conn_string(db_url) as setup_checkpointer:
        await setup_checkpointer.setup()

    logger.info("PostgreSQL checkpointer initialized with connection pool")

    return checkpointer
