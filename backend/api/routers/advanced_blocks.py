"""
Advanced Strategy Builder Blocks — REST API

Exposes the advanced_blocks library (Volume Profile, Order Flow,
Cumulative Delta, ML Signal) over HTTP so the frontend can call them
directly during strategy building and backtesting.

Prefix: /api/v1/advanced-blocks
Tags:   advanced-blocks
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Shared OHLCV request model
# ─────────────────────────────────────────────────────────────────────────────


class OHLCVCandle(BaseModel):
    """Single OHLCV candlestick."""

    timestamp: int = Field(..., description="Open-time in milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float


def _candles_to_df(candles: list[OHLCVCandle]) -> pd.DataFrame:
    """Convert a list of OHLCVCandle objects to a typed DataFrame."""
    if not candles:
        raise HTTPException(status_code=422, detail="candles list is empty")
    df = pd.DataFrame([c.model_dump() for c in candles])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Volume Profile
# ─────────────────────────────────────────────────────────────────────────────


class VolumeProfileRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=2)
    n_bins: int = Field(50, ge=5, le=200, description="Price level bins")
    value_area_pct: float = Field(0.70, ge=0.5, le=0.95, description="Value area fraction")


class VolumeProfileResponse(BaseModel):
    poc: float
    value_area_high: float
    value_area_low: float
    profile_type: str
    metadata: dict[str, Any] = {}


@router.post(
    "/volume-profile",
    response_model=VolumeProfileResponse,
    summary="Calculate Volume Profile (POC, VAH, VAL)",
)
async def volume_profile(req: VolumeProfileRequest) -> VolumeProfileResponse:
    """
    Calculate Volume Profile for the supplied OHLCV candles.

    Returns Point of Control (POC), Value Area High/Low and a
    qualitative ``profile_type`` (balanced / trend / double_distribution).
    """
    try:
        from backend.backtesting.advanced_blocks.volume_profile import VolumeProfileBlock

        df = _candles_to_df(req.candles)
        block = VolumeProfileBlock(n_bins=req.n_bins, value_area_pct=req.value_area_pct)
        result = block.calculate(df)
        return VolumeProfileResponse(
            poc=result.poc,
            value_area_high=result.value_area_high,
            value_area_low=result.value_area_low,
            profile_type=result.profile_type,
            metadata=result.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("volume_profile failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Order Flow Imbalance
# ─────────────────────────────────────────────────────────────────────────────


class OrderFlowRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=2)
    lookback: int = Field(20, ge=2, le=200)
    threshold: float = Field(0.3, ge=0.0, le=1.0)


class OrderFlowResponse(BaseModel):
    imbalance: float
    signal: int
    strength: float
    metadata: dict[str, Any] = {}


@router.post(
    "/order-flow",
    response_model=OrderFlowResponse,
    summary="Calculate Order Flow Imbalance",
)
async def order_flow(req: OrderFlowRequest) -> OrderFlowResponse:
    """
    Calculate buy/sell pressure imbalance over the given lookback window.

    ``signal`` is ``1`` (buy pressure), ``-1`` (sell pressure) or ``0``.
    ``strength`` is in ``[0, 1]``.
    """
    try:
        from backend.backtesting.advanced_blocks.order_flow import OrderFlowImbalanceBlock

        df = _candles_to_df(req.candles)
        block = OrderFlowImbalanceBlock(lookback=req.lookback, threshold=req.threshold)
        result = block.calculate(df)
        return OrderFlowResponse(
            imbalance=result.imbalance,
            signal=result.signal,
            strength=result.strength,
            metadata=result.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("order_flow failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Cumulative Delta
# ─────────────────────────────────────────────────────────────────────────────


class CumulativeDeltaRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=2)
    window: int = Field(10, ge=2, le=200, description="Smoothing window")


class CumulativeDeltaResponse(BaseModel):
    cumulative_delta: float
    smoothed_delta: float
    delta_trend: float
    divergence: str
    delta: float


@router.post(
    "/cumulative-delta",
    response_model=CumulativeDeltaResponse,
    summary="Calculate Cumulative Delta",
)
async def cumulative_delta(req: CumulativeDeltaRequest) -> CumulativeDeltaResponse:
    """
    Compute the cumulative buy-minus-sell delta and detect price divergence.

    ``divergence`` is ``"bullish"``, ``"bearish"`` or ``"none"``.
    """
    try:
        from backend.backtesting.advanced_blocks.order_flow import CumulativeDeltaBlock

        df = _candles_to_df(req.candles)
        block = CumulativeDeltaBlock(window=req.window)
        result = block.calculate(df)
        return CumulativeDeltaResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("cumulative_delta failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# ML Signal (Random-Forest / lightweight ML)
# ─────────────────────────────────────────────────────────────────────────────


class MLSignalRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=10)
    model_type: str = Field("rf", description="Model type: 'rf' (Random Forest) or 'xgb'")
    n_estimators: int = Field(100, ge=10, le=500)
    max_depth: int = Field(5, ge=1, le=20)


class MLSignalResponse(BaseModel):
    signal: float
    confidence: float
    prediction: float | None = None
    metadata: dict[str, Any] = {}


@router.post(
    "/ml-signal",
    response_model=MLSignalResponse,
    summary="Generate ML-based trading signal (no pre-trained model required)",
)
async def ml_signal(req: MLSignalRequest) -> MLSignalResponse:
    """
    Run the lightweight ``MLSignalBlock`` on the supplied candles.

    No pre-trained model is required — the block trains on the supplied
    data and returns a signal for the last bar.
    ``signal`` is in ``[-1, 1]``, ``confidence`` in ``[0, 1]``.
    """
    try:
        from backend.backtesting.advanced_blocks.ml_blocks import MLSignalBlock

        df = _candles_to_df(req.candles)
        block = MLSignalBlock(
            model_type=req.model_type,
            n_estimators=req.n_estimators,
            max_depth=req.max_depth,
        )
        result = block.predict(df)
        return MLSignalResponse(
            signal=result.signal,
            confidence=result.confidence,
            prediction=result.prediction,
            metadata=result.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ml_signal failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Health / list
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/",
    summary="List available advanced blocks",
    include_in_schema=True,
)
async def list_blocks() -> dict[str, Any]:
    """Return the list of available advanced blocks and their endpoints."""
    return {
        "blocks": [
            {
                "id": "volume-profile",
                "name": "Volume Profile",
                "endpoint": "POST /api/v1/advanced-blocks/volume-profile",
                "description": "POC, VAH, VAL and distribution type",
            },
            {
                "id": "order-flow",
                "name": "Order Flow Imbalance",
                "endpoint": "POST /api/v1/advanced-blocks/order-flow",
                "description": "Buy/sell pressure imbalance with signal",
            },
            {
                "id": "cumulative-delta",
                "name": "Cumulative Delta",
                "endpoint": "POST /api/v1/advanced-blocks/cumulative-delta",
                "description": "Cumulative buy-sell delta with divergence detection",
            },
            {
                "id": "ml-signal",
                "name": "ML Signal",
                "endpoint": "POST /api/v1/advanced-blocks/ml-signal",
                "description": "Lightweight ML-based directional signal",
            },
        ]
    }
