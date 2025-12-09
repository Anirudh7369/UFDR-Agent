import os
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, AsyncGenerator

# This global variable will hold the connection pool for the application.
redis_pool: Optional[ConnectionPool] = None

async def init_redis_pool():
    """
    Initializes the Redis connection pool. This should be called once during application startup.
    """
    global redis_pool
    if redis_pool is not None:
        return

    # Get the Redis URL from environment variables, with a sensible default.
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6380")
    print(f"Initializing Redis connection pool for URL: {redis_url}")

    try:
        # decode_responses=True ensures that Redis returns strings, not bytes.
        pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        # Basic connectivity check to fail fast but not crash the app.
        async with redis.Redis(connection_pool=pool) as client:
            await client.ping()
        redis_pool = pool
        print("Redis connection pool initialized successfully.")
    except Exception as exc:
        # Keep running without Redis; downstream callers will see redis_pool is None.
        redis_pool = None
        print(f"[WARNING] Redis connection pool not initialized: {exc}")

async def close_redis_pool():
    """
    Closes the Redis connection pool. This should be called once during application shutdown.
    """
    global redis_pool
    if redis_pool:
        print("Closing Redis connection pool.")
        try:
            await redis_pool.disconnect()
        except Exception as exc:
            print(f"[WARNING] Failed closing Redis pool: {exc}")

async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    FastAPI dependency injector to get a Redis client from the pool.
    """
    if not redis_pool:
        # Yield None so callers can degrade gracefully if Redis is unavailable.
        yield None
        return

    async with redis.Redis(connection_pool=redis_pool) as client:
        yield client
