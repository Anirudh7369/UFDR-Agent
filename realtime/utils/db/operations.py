import asyncpg
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timezone
from .connection import get_db_connection

logger = logging.getLogger(__name__)

async def save_feedback(
    session_id: Optional[str],
    email_id: Optional[str],
    timestamp: str,
    query: str,
    generated_payload: Dict[str, Any],
    response: str
) -> bool:
    """
    Save feedback data to the feedback table in PostgreSQL.

    Args:
        session_id: Session identifier
        email_id: Email identifier
        timestamp: Timestamp in ISO format
        query: User's query
        generated_payload: The payload that was generated
        response: The response message generated

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with get_db_connection() as conn:
            # Convert the generated_payload dict to JSON string for storage
            import json
            payload_json = json.dumps(generated_payload)

            # Convert timestamp string to datetime object if it's a string
            if isinstance(timestamp, str):
                # Parse ISO format timestamp (e.g., "2025-12-08T09:27:41Z")
                timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                timestamp_dt = timestamp

            # Insert the feedback record
            await conn.execute(
                """
                INSERT INTO feedback (session_id, email_id, timestamp, query, generatedpayload, response)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                session_id,
                email_id,
                timestamp_dt,
                query,
                payload_json,
                response
            )

            logger.info(f"Feedback saved successfully for session_id: {session_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to save feedback: {str(e)}", exc_info=True)
        return False

async def get_feedback_by_session(session_id: str) -> list:
    """
    Retrieve feedback records by session_id.

    Args:
        session_id: Session identifier

    Returns:
        list: List of feedback records
    """
    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT session_id, email_id, timestamp, query, generatedpayload, response
                FROM feedback
                WHERE session_id = $1
                ORDER BY timestamp DESC
                """,
                session_id
            )

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to retrieve feedback: {str(e)}", exc_info=True)
        return []

async def get_feedback_by_email(email_id: str) -> list:
    """
    Retrieve feedback records by email_id.

    Args:
        email_id: Email identifier

    Returns:
        list: List of feedback records
    """
    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT session_id, email_id, timestamp, query, generatedpayload, response
                FROM feedback
                WHERE email_id = $1
                ORDER BY timestamp DESC
                """,
                email_id
            )

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to retrieve feedback: {str(e)}", exc_info=True)
        return []
