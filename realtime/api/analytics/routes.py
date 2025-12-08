from fastapi import APIRouter
from datetime import datetime, timezone
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.time import is_valid_timestamp
from utils.ai.agent import create_forensic_agent
from utils.db import save_feedback
from schemas.objects import AnalyticsPayload, AnalyticsResponse
from utils.chat_session import SessionCache

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter()


@router.options("/analytics")
async def analytics_options():
    """Handle CORS preflight OPTIONS requests"""
    return {"status": "ok"}


@router.get("/session/{session_id}/debug")
async def debug_session(session_id: str):
    """
    Debug endpoint to inspect session cache contents.
    """
    from utils.ai.redis_client import is_redis_available

    try:
        # Check if Redis is available
        redis_available = is_redis_available()

        if not redis_available:
            return {
                "session_id": session_id,
                "redis_available": False,
                "message": "Redis is not available. Session cache is disabled.",
            }

        # Check if session exists
        exists = await SessionCache.session_exists(session_id)

        if not exists:
            return {
                "session_id": session_id,
                "exists": False,
                "message": "Session not found in cache",
                "redis_available": True,
            }

        # Get message count
        count = await SessionCache.get_session_message_count(session_id)

        # Get all messages
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
            "redis_available": is_redis_available(),
        }


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
                "message": "Redis is not available. No session to clear.",
                "redis_available": False,
            }

        # Clear the session
        success = await SessionCache.clear_session(session_id)

        if success:
            return {
                "session_id": session_id,
                "status": "success",
                "message": "Session cleared successfully",
                "redis_available": True,
            }
        else:
            return {
                "session_id": session_id,
                "status": "error",
                "message": "Failed to clear session",
                "redis_available": True,
            }

    except Exception as e:
        logger.error(f"Error clearing session: {e}", exc_info=True)
        return {
            "session_id": session_id,
            "status": "error",
            "message": f"Exception occurred: {str(e)}",
            "redis_available": is_redis_available(),
        }


@router.post("/analytics", response_model=AnalyticsResponse)
async def analytics_endpoint(payload: AnalyticsPayload) -> AnalyticsResponse:
    """
    Analytics endpoint that receives data from the frontend and uses Redis
    session cache to store/retrieve recent conversation history.
    """
    try:
        # Log what we receive from frontend
        print(
            f"[REQUEST] Received from frontend - Query: {payload.query}, "
            f"Session ID: {payload.session_id}, Email ID: {payload.email_id}, "
            f"Timestamp: {payload.current_timestamp}"
        )
        logger.info(
            f"Received from frontend - Query: {payload.query}, "
            f"Session ID: {payload.session_id}, Email ID: {payload.email_id}, "
            f"Timestamp: {payload.current_timestamp}"
        )

        query = payload.query
        session_id = payload.session_id
        email_id = payload.email_id
        now = datetime.now(timezone.utc)
        current_timestamp = (
            payload.current_timestamp
            or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        # Validate timestamp format
        if not is_valid_timestamp(current_timestamp):
            logger.error(f"Timestamp validation failed: {current_timestamp}")
            return AnalyticsResponse(
                status="error",
                message=(
                    "Invalid timestamp format. Expected format: "
                    "YYYY-MM-DDTHH:mm:SSZ. Example: "
                    f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                ),
                response={},
                session_id=session_id,
                status_code=400,
            )

        # Cache user query in Redis (if available)
        cached_messages = []
        if session_id:
            metadata = {"email_id": email_id} if email_id else None
            await SessionCache.append_message(
                session_id=session_id,
                role="user",
                content=query,
                metadata=metadata,
            )

            # Retrieve recent conversation history for context
            cached_messages = await SessionCache.get_messages(
                session_id, limit=10
            )
            logger.debug(
                f"Retrieved {len(cached_messages)} cached messages "
                f"for session {session_id}"
            )

        agent = await create_forensic_agent()

        # Process the query using the agent
        agent_response = await agent.analyze_forensic_data(query)

        # Cache agent response in Redis (if available)
        if session_id:
            await SessionCache.append_message(
                session_id=session_id,
                role="assistant",
                content=agent_response,
                metadata=None,
            )

        # Log our response
        if len(agent_response) > 200:
            short_resp = agent_response[:200] + "..."
        else:
            short_resp = agent_response
        print(f"[RESPONSE] Agent response: {short_resp}")
        logger.info(f"Agent response: {short_resp}")

        # Build response
        response_data = AnalyticsResponse(
            message=agent_response,
            status="success",
            response={"query": query},
            session_id=session_id,
            status_code=200,
        )

        # Save feedback to database
        try:
            await save_feedback(
                session_id=session_id,
                email_id=email_id,
                timestamp=current_timestamp,
                query=query,
                generated_payload={"query": query, "history": cached_messages},
                response=agent_response,
            )
            logger.info(
                f"Feedback saved to database for session_id: {session_id}"
            )
        except Exception as db_error:
            # Log the error but don't fail the request
            logger.error(
                f"Failed to save feedback to database: {str(db_error)}",
                exc_info=True,
            )
            print(
                f"[WARNING] Failed to save feedback to database: "
                f"{str(db_error)}"
            )

        return response_data

    except Exception as e:
        print(f"[ERROR] Exception occurred: {str(e)}")
        logger.error(
            f"Exception in analytics endpoint: {str(e)}", exc_info=True
        )
        return AnalyticsResponse(
            status="error",
            message=f"Failed to process analytics data: {str(e)}",
            response={},
            session_id=payload.session_id,
            status_code=500,
        )
