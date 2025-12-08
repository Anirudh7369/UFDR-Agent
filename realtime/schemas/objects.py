from typing import Dict, Any, Optional, TypedDict


# Lightweight typed dicts to avoid requiring `pydantic` at import time.
# These are only used for local development/startup so the server can run
# without building native pydantic extensions. They preserve the shape of
# the data for readability but do not provide runtime validation.


class AnalyticsPayload(TypedDict, total=False):
    query: str
    current_timestamp: str
    session_id: str
    email_id: str


class AnalyticsResponse(TypedDict, total=False):
    message: str
    status: str
    response: Dict[str, Any]
    session_id: Optional[str]
    status_code: Optional[int]


class UFDRUploadResponse(TypedDict, total=False):
    status: str
    file_info: Dict[str, Any]
    file_id: Optional[str]
    status_code: Optional[int]