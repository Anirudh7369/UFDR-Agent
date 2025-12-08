"""
Redis client helper for session caching.

This module provides a singleton Redis client for managing chat session cache.
Connection errors are handled gracefully to allow the app to run without Redis.

Connection Configuration:
    REDIS_URL: Full Redis connection URL (default: redis://localhost:6379/0)
    Alternatively, individual components:
        REDIS_HOST: Redis server host (default: localhost)
        REDIS_PORT: Redis server port (default: 6379)
        REDIS_DB: Redis database number (default: 0)

Usage:
    from utils.ai.redis_client import get_redis_client

    redis_client = await get_redis_client()
    if redis_client:
        await redis_client.set("key", "value")
"""

from __future__ import annotations
import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[object] = None
_redis_available: bool = True


async def get_redis_client() -> Optional[object]:
    """
    Get or create a singleton Redis client instance.

    Returns:
        Redis client instance if available, None if Redis is unavailable or connection failed.

    Note:
        This function attempts to connect only once. If the connection fails,
        subsequent calls will return None without retrying to avoid performance impact.
    """
    global _redis_client, _redis_available

    # If Redis is known to be unavailable, return None immediately
    if not _redis_available:
        return None

    # Return existing client if already initialized
    if _redis_client is not None:
        return _redis_client

    try:
        # Lazy import to avoid requiring redis at startup
        import redis.asyncio as redis

        # Read Redis configuration from environment
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            # Use full URL if provided
            _redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        else:
            # Build connection from individual components
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))

            _redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

        # Test the connection
        await _redis_client.ping()
        logger.info(f"Redis client initialized successfully: {redis_url or f'{host}:{port}/{db}'}")

        return _redis_client

    except ImportError:
        logger.warning("Redis package not installed. Session cache will be disabled.")
        _redis_available = False
        return None

    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}. Session cache will be disabled.")
        _redis_available = False
        _redis_client = None
        return None


async def close_redis_client():
    """
    Close the Redis client connection.

    This should be called during application shutdown.
    """
    global _redis_client

    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis client closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None


def is_redis_available() -> bool:
    """
    Check if Redis is available for use.

    Returns:
        True if Redis connection is available, False otherwise.
    """
    return _redis_available and _redis_client is not None
