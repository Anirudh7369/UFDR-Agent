from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class VisualizationFile(BaseModel):
    """Represents a generated visualization file"""
    filename: str
    filepath: str
    url: str
    type: str  # e.g., "heatmap", "bar_chart", "matrix"
    description: str


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
    status_code: Optional[int] = 200
    visualizations: Optional[List[VisualizationFile]] = None  # Added for visualization support
    analysis_metadata: Optional[Dict[str, Any]] = None  # Added for additional metadata


class UFDRUploadResponse(BaseModel):
    status: str
    file_info: Dict[str, Any]
    file_id: Optional[str]
    status_code: Optional[int] = 200