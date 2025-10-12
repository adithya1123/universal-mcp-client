"""
PostgreSQL checkpointer for LangGraph - DEPRECATED

⚠️ DEPRECATION NOTICE:
This module is deprecated and should not be used. The checkpointer is now managed
directly in the FastAPI lifespan context (src/api/server.py) to ensure proper
resource lifecycle management.

REASON FOR DEPRECATION:
- AsyncPostgresSaver requires context manager pattern for proper cleanup
- Connection pool must be managed at application level, not function level
- Previous implementation created multiple connection pools incorrectly

NEW PATTERN (see src/api/server.py):
```python
async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
    await checkpointer.setup()
    await initialize_clients(mcp, llm, db, checkpointer=checkpointer)
    yield  # Application runs
    # Cleanup happens automatically
```

This file is kept for reference only and will be removed in a future version.
"""

import logging
import warnings

logger = logging.getLogger(__name__)


def create_checkpointer():
    """
    DEPRECATED: Do not use this function.

    Checkpointer should be created in FastAPI lifespan using:
    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        await checkpointer.setup()
    """
    warnings.warn(
        "create_checkpointer() is deprecated. "
        "Manage checkpointer in FastAPI lifespan context instead. "
        "See src/api/server.py for correct implementation.",
        DeprecationWarning,
        stacklevel=2
    )
    raise RuntimeError(
        "create_checkpointer() has been deprecated. "
        "Checkpointer is now managed in FastAPI lifespan (src/api/server.py). "
        "Do not call this function."
    )


# Previous implementation kept for reference (DO NOT USE):
"""
INCORRECT PATTERN (for reference only):

async def create_checkpointer() -> AsyncPostgresSaver:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")

    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }

    pool = AsyncConnectionPool(
        conninfo=db_url,
        max_size=20,
        kwargs=connection_kwargs,
    )

    checkpointer = AsyncPostgresSaver(pool)

    # PROBLEM: Creates ANOTHER pool, doesn't use the one above
    async with AsyncPostgresSaver.from_conn_string(db_url) as setup_checkpointer:
        await setup_checkpointer.setup()

    return checkpointer  # Returns checkpointer with DIFFERENT pool

WHY THIS WAS WRONG:
1. Created two separate connection pools
2. Context manager pool was closed after setup
3. Returned checkpointer used orphaned pool
4. No cleanup mechanism for the returned checkpointer
5. Connection leaks in production

CORRECT PATTERN:
See src/api/server.py lifespan function for proper implementation.
"""
