import redis.asyncio as redis
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Define a constant for the session expiration time (e.g., 1 hour in seconds)
SESSION_EXPIRATION_SECONDS = 3600

# Define a constant for the max number of messages to keep in history.
# A value of 20 means 10 pairs of user/AI messages.
MAX_HISTORY_LENGTH = 20

def get_session_key(session_id: str) -> str:
    """Generates the standard Redis key for a given chat session ID."""
    return f"chat_history:{session_id}"

async def get_chat_history(redis_client: Optional[redis.Redis], session_id: Optional[str]) -> str:
    """
    Retrieves the conversation history for a session from Redis and formats
    it as a single string for the AI agent's context.
    """
    if not redis_client or not session_id:
        return ""

    try:
        redis_key = get_session_key(session_id)
        # LRANGE 0 -1 fetches all elements from the list.
        history_list: List[str] = await redis_client.lrange(redis_key, 0, -1)
        return "\n".join(history_list)
    except Exception as exc:
        logger.warning("Failed to read chat history for session %s: %s", session_id, exc)
        return ""

async def save_chat_message(
    redis_client: Optional[redis.Redis],
    session_id: Optional[str],
    user_message: str,
    ai_response: str
):
    """
    Saves a user message and the corresponding AI response to the chat history in Redis.
    It also trims the history and resets the session expiration.
    """
    if not redis_client or not session_id:
        return

    redis_key = get_session_key(session_id)

    try:
        # Use a pipeline to execute multiple commands efficiently and atomically.
        pipe = redis_client.pipeline()

        # Add the new messages to the end of the list.
        await pipe.rpush(redis_key, f"User: {user_message}", f"AI: {ai_response}")

        # Trim the history to keep it from growing indefinitely.
        await pipe.ltrim(redis_key, -MAX_HISTORY_LENGTH, -1)

        # Reset the expiration time for the session to keep it active.
        await pipe.expire(redis_key, SESSION_EXPIRATION_SECONDS)

        # Execute all commands in the pipeline.
        await pipe.execute()
    except Exception as exc:
        logger.warning("Failed to save chat message for session %s: %s", session_id, exc)
