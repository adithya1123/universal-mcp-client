#!/usr/bin/env python3
"""
Initialize the database by creating all tables.
This script can be run standalone or imported.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from src.storage.database import init_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Initialize database tables."""
    try:
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
