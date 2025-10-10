from pydantic import BaseModel
from typing import Dict, Any, Optional


class AnalyticsPayload(BaseModel):
    query: str
    current_timestamp: Optional[str]
    session_id: Optional[str]
    email_id: Optional[str]


class AnalyticsResponse(BaseModel):
    message: str
    status: str
    response: Dict[str, Any]
    session_id: Optional[str]