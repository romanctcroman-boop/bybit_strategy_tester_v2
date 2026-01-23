"""
Bots Router
Endpoints for managing trading bots.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_bots():
    """List all bots"""
    return []
