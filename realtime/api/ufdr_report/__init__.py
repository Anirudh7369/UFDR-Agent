"""
UFDR Report router module for the FastAPI application.

This module initializes the UFDR report router and makes it available
for import by the main FastAPI application.
"""

from .routes import router

__all__ = ["router"]
