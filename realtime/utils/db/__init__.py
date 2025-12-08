"""Database utilities for UFDR Agent"""

from .connection import (
    init_db_pool,
    close_db_pool,
    get_db_pool,
    get_db_connection
)

from .operations import (
    save_feedback,
    get_feedback_by_session,
    get_feedback_by_email
)

__all__ = [
    'init_db_pool',
    'close_db_pool',
    'get_db_pool',
    'get_db_connection',
    'save_feedback',
    'get_feedback_by_session',
    'get_feedback_by_email'
]
