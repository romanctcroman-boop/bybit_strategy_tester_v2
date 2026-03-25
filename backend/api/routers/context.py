"""
Context Router
Endpoints for context management (MCP replacement).
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_context():
    """Get current context"""
    return {"context": {}}
