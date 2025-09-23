from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.time import is_valid_timestamp
from utils.ai.agent import get_agent
import openai
from agents import Runner
from dotenv import load_dotenv

load_dotenv()

# Define the model
model = "gemini-2.5-pro"
openai.api_key = os.getenv("OPENAI_API_KEY")


logger = logging.getLogger(__name__)
router = APIRouter()

class AnalyticsPayload(BaseModel):
    query: str
    current_timestamp: Optional[str]
    session_id: Optional[str]
    email_id: Optional[str]

@router.post("/analytics")
async def analytics_endpoint(payload: AnalyticsPayload) -> Dict[str, Any]:
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
        
        agent = get_agent(model=model)
        result = await Runner.run(agent, query)

        # Process the analytics data here
        response_data = {
            "message": result,
            "status": "success",
            "response": {
                "query": query,
            },
            "session_id": payload.session_id
        }
        
        return response_data
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to process analytics data: {str(e)}"
        }