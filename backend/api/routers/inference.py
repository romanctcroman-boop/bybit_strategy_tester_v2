"""
Inference Router
Endpoints for running strategy inference and predictions.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/predict")
async def run_prediction():
    """Run strategy prediction"""
    return {"status": "not_implemented"}
