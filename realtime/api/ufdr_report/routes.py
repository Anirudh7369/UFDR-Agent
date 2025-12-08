from fastapi import APIRouter
from datetime import datetime, timezone
import logging
import sys
import os

# Allow imports from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.time import is_valid_timestamp
from utils.ai.agent import create_forensic_agent
from utils.db import save_feedback
from schemas.objects import AnalyticsPayload, AnalyticsResponse
from utils.chat_session import SessionCache

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()


# -------------------------------------------------------------------------
# CORS preflight handler
# -------------------------------------------------------------------------
@router.options("/analytics")
async def analytics_options():
    return {"status": "ok"}


# -------------------------------------------------------------------------
# Session Debug Endpoint
# -------------------------------------------------------------------------
@router.get("/session/{session_id}/debug")
async def debug_session(session_id: str):
    """
    Debug endpoint to inspect session cache contents.
    """
    from utils.ai.redis_client import is_redis_available

    try:
        redis_available = is_redis_available()

        if not redis_available:
            return {
                "session_id": session_id,
                "redis_available": False,
                "message": "Redis is not available. Session cache is disabled."
            }

        exists = await SessionCache.session_exists(session_id)

        if not exists:
            return {
                "session_id": session_id,
                "exists": False,
                "redis_available": True,
                "message": "Session not found in cache.",
            }

        count = await SessionCache.get_session_message_count(session_id)
        messages = await SessionCache.get_messages(session_id)

        return {
            "session_id": session_id,
            "exists": True,
            "message_count": count,
            "messages": messages,
            "redis_available": True,
        }

    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return {
            "session_id": session_id,
            "error": str(e),
            "redis_available": False,
        }


# -------------------------------------------------------------------------
# Session Clear Endpoint
# -------------------------------------------------------------------------
@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear all cached messages for a session.
    """
    from utils.ai.redis_client import is_redis_available

    try:
        redis_available = is_redis_available()

        if not redis_available:
            return {
                "session_id": session_id,
                "status": "warning",
                "message": "Redis unavailable — nothing to clear.",
                "redis_available": False,
            }

        success = await SessionCache.clear_session(session_id)

        return {
            "session_id": session_id,
            "status": "success" if success else "error",
            "message": "Session cleared successfully" if success else "Failed to clear session",
            "redis_available": True,
        }

    except Exception as e:
        logger.error(f"Error clearing session: {e}", exc_info=True)
        return {
            "session_id": session_id,
            "status": "error",
            "message": f"Exception: {e}",
            "redis_available": False,
        }


# -------------------------------------------------------------------------
# MAIN ANALYTICS ENDPOINT
# -------------------------------------------------------------------------
@router.post("/analytics", response_model=AnalyticsResponse)
async def analytics_endpoint(payload: AnalyticsPayload) -> AnalyticsResponse:
    """
    Main analytics endpoint with Redis session caching.
    """
    try:
        query = payload.query
        session_id = payload.session_id
        email_id = payload.email_id

        now = datetime.now(timezone.utc)
        current_timestamp = (
            payload.current_timestamp or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        # Validate timestamp format
        if not is_valid_timestamp(current_timestamp):
            example = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            return AnalyticsResponse(
                status="error",
                message=f"Invalid timestamp format. Expected: YYYY-MM-DDTHH:mm:SSZ. Example: {example}",
                response={},
                session_id=session_id,
                status_code=400,
            )

        # Cache USER message in Redis
        cached_messages = []
        if session_id:
            metadata = {"email_id": email_id} if email_id else None

            await SessionCache.append_message(
                session_id=session_id,
                role="user",
                content=query,
                metadata=metadata,
            )

            cached_messages = await SessionCache.get_messages(
                session_id=session_id, limit=10
            )

        # Call the forensic agent (LLM)
        agent = await create_forensic_agent()
        agent_response = await agent.analyze_forensic_data(query)

        # Cache ASSISTANT message in Redis
        if session_id:
            await SessionCache.append_message(
                session_id=session_id,
                role="assistant",
                content=agent_response,
            )

        # Save Feedback to DB
        try:
            await save_feedback(
                session_id=session_id,
                email_id=email_id,
                timestamp=current_timestamp,
                query=query,
                generated_payload={"query": query, "history": cached_messages},
                response=agent_response,
            )
        except Exception as db_err:
            logger.error(f"DB Save Error: {db_err}", exc_info=True)

        # Build analytics response
        return AnalyticsResponse(
            message=agent_response,
            status="success",
            response={"query": query},
            session_id=session_id,
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Analytics endpoint error: {e}", exc_info=True)
        return AnalyticsResponse(
            status="error",
            message=f"Processing error: {e}",
            response={},
            session_id=payload.session_id,
            status_code=500,
        )
