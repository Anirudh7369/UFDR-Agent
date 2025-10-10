from fastapi import APIRouter
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.time import is_valid_timestamp
from utils.ai.agent import create_forensic_agent
from schemas.opbects import AnalyticsPayload, AnalyticsResponse
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

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
        query = payload.query
        now = datetime.now(timezone.utc)
        current_timestamp = payload.current_timestamp or now.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        # Validate timestamp format
        if not is_valid_timestamp(current_timestamp):
            logger.error(f"Timestamp validation failed: {current_timestamp}")
            return {
                "status": "error",
                "message": f"Invalid timestamp format. Expected format: YYYY-MM-DDTHH:mm:SSZ. Example: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            }

        agent = await create_forensic_agent()

        # Process the query using the agent
        agent_response = await agent.analyze_forensic_data(payload.query)

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
        return AnalyticsResponse(
            status="error",
            message=f"Failed to process analytics data: {str(e)}",
            session_id=payload.session_id,
            status_code=500
        )