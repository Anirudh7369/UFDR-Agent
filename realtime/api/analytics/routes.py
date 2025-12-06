from fastapi import APIRouter
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.time import is_valid_timestamp
from utils.ai.agent import create_forensic_agent
from schemas.objects import AnalyticsPayload, AnalyticsResponse
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

@router.post("/analytics", response_model=AnalyticsResponse)
async def analytics_endpoint(payload: AnalyticsPayload) -> AnalyticsResponse:
    """
    Analytics endpoint that receives data from the frontend.
    
    Args:
        payload: AnalyticsPayload containing query, current_timestamp, session_id, email_id
    
    Returns:
        Dict with status and received data
    """
    try:
        # Log what we receive from frontend
        print(f"[REQUEST] Received from frontend - Query: {payload.query}, Session ID: {payload.session_id}, Email ID: {payload.email_id}, Timestamp: {payload.current_timestamp}")
        logger.info(f"Received from frontend - Query: {payload.query}, Session ID: {payload.session_id}, Email ID: {payload.email_id}, Timestamp: {payload.current_timestamp}")
        
        query = payload.query
        now = datetime.now(timezone.utc)
        current_timestamp = payload.current_timestamp or now.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        # Validate timestamp format
        if not is_valid_timestamp(current_timestamp):
            logger.error(f"Timestamp validation failed: {current_timestamp}")
            return AnalyticsResponse(
                status="error",
                message=f"Invalid timestamp format. Expected format: YYYY-MM-DDTHH:mm:SSZ. Example: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
                response={},
                session_id=payload.session_id,
                status_code=400
            )

        agent = await create_forensic_agent()

        # Process the query using the agent
        agent_response = await agent.analyze_forensic_data(payload.query)
        
        # Log our response
        print(f"[RESPONSE] Agent response: {agent_response[:200]}..." if len(agent_response) > 200 else f"[RESPONSE] Agent response: {agent_response}")
        logger.info(f"Agent response: {agent_response[:200]}..." if len(agent_response) > 200 else f"Agent response: {agent_response}")

        # Process the analytics data here
        response_data = AnalyticsResponse(
            message=agent_response,
            status="success",
            response={
                "query": query,
            },
            session_id=payload.session_id,
            status_code=200
        )
        
        return response_data
        
    except Exception as e:
        print(f"[ERROR] Exception occurred: {str(e)}")
        logger.error(f"Exception in analytics endpoint: {str(e)}", exc_info=True)
        return AnalyticsResponse(
            status="error",
            message=f"Failed to process analytics data: {str(e)}",
            response={},
            session_id=payload.session_id,
            status_code=500
        )