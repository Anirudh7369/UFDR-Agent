"""
Session cache interface for managing chat conversation history in Redis.

This module provides a SessionCache class that stores recent chat messages
in Redis for quick retrieval and LLM context building.

Redis Storage Schema:
    Key Pattern: session:{session_id}:messages
    Data Structure: Redis LIST
    Element Format: JSON-encoded message objects
    TTL: 7 days (604800 seconds), refreshed on each write

Message Format:
    {
        "role": "user" | "assistant" | "system",
        "content": "message text",
        "timestamp": "2024-01-15T10:30:00Z",
        "metadata": {  // optional
            "query_id": "...",
            "email_id": "...",
            // other lightweight references
        }
    }

Design Notes:
    - Only stores conversational messages, not raw evidence data
    - Keeps last N messages (default: 30) per session
    - Gracefully degrades if Redis is unavailable
    - Does not replace the main database; this is a cache layer only
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from utils.ai.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_MESSAGE_LIMIT = 30  # Keep last 30 messages per session
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


class SessionCache:
    """
    Redis-based cache for chat session messages.

    Provides methods to append messages, retrieve recent history,
    and clear sessions. All operations gracefully handle Redis unavailability.
    """

    @staticmethod
    def _get_session_key(session_id: str) -> str:
        """
        Generate Redis key for a session's message list.

        Args:
            session_id: Unique session identifier

        Returns:
            Redis key string in format: session:{session_id}:messages
        """
        return f"session:{session_id}:messages"

    @staticmethod
    async def append_message(
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Append a new message to the session's message history in Redis.

        This method:
        1. Adds the message to the Redis LIST using RPUSH
        2. Trims the list to keep only the last N messages
        3. Refreshes the TTL to 7 days

        Args:
            session_id: Unique session identifier
            role: Message role - "user", "assistant", or "system"
            content: The message text content
            metadata: Optional dictionary of lightweight metadata (e.g., email_id, case_id)

        Returns:
            True if successful, False if Redis is unavailable

        Security Note:
            Do NOT include raw evidence blobs or full records in metadata.
            Only store lightweight references and chat dialogue.
        """
        redis_client = await get_redis_client()
        if not redis_client:
            logger.debug(f"Redis unavailable, skipping message append for session {session_id}")
            return False

        try:
            # Create message object
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if metadata:
                message["metadata"] = metadata

            # Serialize to JSON
            message_json = json.dumps(message)

            # Redis key for this session
            key = SessionCache._get_session_key(session_id)

            # Use pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Append message to the list
            pipe.rpush(key, message_json)

            # Trim to keep only last N messages
            pipe.ltrim(key, -DEFAULT_MESSAGE_LIMIT, -1)

            # Refresh TTL
            pipe.expire(key, SESSION_TTL_SECONDS)

            await pipe.execute()

            logger.debug(f"Appended {role} message to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error appending message to Redis for session {session_id}: {e}")
            return False

    @staticmethod
    async def get_messages(
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent messages for a session from Redis.

        Args:
            session_id: Unique session identifier
            limit: Optional limit on number of messages to return (default: all cached messages)

        Returns:
            List of message dictionaries, ordered chronologically (oldest first).
            Returns empty list if Redis is unavailable or session not found.

        Example:
            messages = await SessionCache.get_messages("session-123", limit=10)
            for msg in messages:
                print(f"{msg['role']}: {msg['content']}")
        """
        redis_client = await get_redis_client()
        if not redis_client:
            logger.debug(f"Redis unavailable, returning empty message list for session {session_id}")
            return []

        try:
            key = SessionCache._get_session_key(session_id)

            # Get all or limited messages from the list
            if limit:
                # Get last N messages
                messages_json = await redis_client.lrange(key, -limit, -1)
            else:
                # Get all messages
                messages_json = await redis_client.lrange(key, 0, -1)

            # Parse JSON messages
            messages = []
            for msg_json in messages_json:
                try:
                    message = json.loads(msg_json)
                    messages.append(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message JSON for session {session_id}: {e}")
                    continue

            logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages

        except Exception as e:
            logger.error(f"Error retrieving messages from Redis for session {session_id}: {e}")
            return []

    @staticmethod
    async def clear_session(session_id: str) -> bool:
        """
        Clear all messages for a session from Redis.

        This removes the session key entirely from Redis.

        Args:
            session_id: Unique session identifier

        Returns:
            True if successful or key didn't exist, False if Redis is unavailable
        """
        redis_client = await get_redis_client()
        if not redis_client:
            logger.debug(f"Redis unavailable, cannot clear session {session_id}")
            return False

        try:
            key = SessionCache._get_session_key(session_id)
            await redis_client.delete(key)
            logger.info(f"Cleared session cache for {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing session {session_id} from Redis: {e}")
            return False

    @staticmethod
    async def session_exists(session_id: str) -> bool:
        """
        Check if a session exists in Redis cache.

        Args:
            session_id: Unique session identifier

        Returns:
            True if session exists in cache, False otherwise
        """
        redis_client = await get_redis_client()
        if not redis_client:
            return False

        try:
            key = SessionCache._get_session_key(session_id)
            exists = await redis_client.exists(key)
            return bool(exists)

        except Exception as e:
            logger.error(f"Error checking session existence for {session_id}: {e}")
            return False

    @staticmethod
    async def get_session_message_count(session_id: str) -> int:
        """
        Get the number of messages stored for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            Number of messages in cache, 0 if session not found or Redis unavailable
        """
        redis_client = await get_redis_client()
        if not redis_client:
            return 0

        try:
            key = SessionCache._get_session_key(session_id)
            count = await redis_client.llen(key)
            return count

        except Exception as e:
            logger.error(f"Error getting message count for session {session_id}: {e}")
            return 0
