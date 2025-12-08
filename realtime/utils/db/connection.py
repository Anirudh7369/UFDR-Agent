import asyncpg
import os
from typing import Optional
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
# Get the realtime directory (3 levels up: db -> utils -> realtime)
realtime_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(realtime_dir, '.env')

# Load .env file and verify it exists
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[connection] Loaded .env from: {env_path}")
else:
    print(f"[connection] WARNING: .env file not found at: {env_path}")

logger = logging.getLogger(__name__)

# Database connection pool
_pool: Optional[asyncpg.Pool] = None

async def init_db_pool():
    """Initialize the database connection pool"""
    global _pool

    if _pool is not None:
        return _pool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    try:
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("Database connection pool initialized successfully")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {str(e)}")
        raise

async def close_db_pool():
    """Close the database connection pool"""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")

async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool, initializing if necessary"""
    global _pool

    if _pool is None:
        await init_db_pool()

    return _pool

@asynccontextmanager
async def get_db_connection():
    """Context manager to get a database connection from the pool"""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        yield connection
