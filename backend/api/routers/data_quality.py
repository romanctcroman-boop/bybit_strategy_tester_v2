"""
Data Quality API Router.

AI Agent Recommendation Implementation:
Provides REST API endpoints for market data quality monitoring.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.data_quality import (
    CandleData,
    DataIssueType,
    DataQualityLevel,
    get_data_quality_monitor,
)

router = APIRouter(prefix="/api/v1/data-quality")


# ============================================================================
# Request/Response Models
# ============================================================================


class CandleRequest(BaseModel):
    """Request to validate a candle."""

    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(..., description="Volume")
    symbol: str = Field(..., description="Trading symbol")
    interval: str = Field(default="1", description="Candle interval")


class BatchCandlesRequest(BaseModel):
    """Request to validate multiple candles."""

    candles: list[CandleRequest] = Field(..., description="List of candles")


class DataQualityIssueResponse(BaseModel):
    """Response model for data quality issue."""

    issue_type: str
    symbol: str
    interval: str
    timestamp: datetime
    severity: float
    description: str
    raw_data: dict[str, Any] | None
    auto_corrected: bool


class ValidationResultResponse(BaseModel):
    """Response model for validation result."""

    is_valid: bool
    quality_score: float
    quality_level: str
    issues: list[DataQualityIssueResponse]
    has_correction: bool


class DataQualityMetricsResponse(BaseModel):
    """Response model for quality metrics."""

    symbol: str
    interval: str
    total_candles: int
    valid_candles: int
    issues_detected: int
    gaps_detected: int
    spikes_detected: int
    quality_score: float
    quality_level: str
    last_update: datetime | None
    staleness_seconds: float


class QualitySummaryResponse(BaseModel):
    """Response model for quality summary."""

    symbols_monitored: int
    overall_quality: float
    quality_level: str
    total_candles: int
    total_issues: int
    by_quality_level: dict[str, int]
    uptime_hours: float


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/summary", response_model=QualitySummaryResponse)
async def get_quality_summary():
    """Get data quality summary across all monitored symbols."""
    monitor = get_data_quality_monitor()
    summary = monitor.get_summary()

    return QualitySummaryResponse(
        symbols_monitored=summary["symbols_monitored"],
        overall_quality=summary["overall_quality"],
        quality_level=summary["quality_level"],
        total_candles=summary["total_candles"],
        total_issues=summary["total_issues"],
        by_quality_level=summary.get("by_quality_level", {}),
        uptime_hours=summary.get("uptime_hours", 0.0),
    )


@router.post("/validate", response_model=ValidationResultResponse)
async def validate_candle(request: CandleRequest):
    """Validate a single candle."""
    monitor = get_data_quality_monitor()

    candle = CandleData(
        timestamp=request.timestamp,
        open=request.open,
        high=request.high,
        low=request.low,
        close=request.close,
        volume=request.volume,
        symbol=request.symbol,
        interval=request.interval,
    )

    result = monitor.process_candle(candle)

    return ValidationResultResponse(
        is_valid=result.is_valid,
        quality_score=result.quality_score,
        quality_level=monitor.get_quality_level(result.quality_score).value,
        issues=[
            DataQualityIssueResponse(
                issue_type=i.issue_type.value,
                symbol=i.symbol,
                interval=i.interval,
                timestamp=i.timestamp,
                severity=i.severity,
                description=i.description,
                raw_data=i.raw_data,
                auto_corrected=i.auto_corrected,
            )
            for i in result.issues
        ],
        has_correction=result.corrected_data is not None,
    )


@router.post("/validate-batch", response_model=dict[str, Any])
async def validate_batch(request: BatchCandlesRequest):
    """Validate a batch of candles."""
    monitor = get_data_quality_monitor()

    candles = [
        CandleData(
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            symbol=c.symbol,
            interval=c.interval,
        )
        for c in request.candles
    ]

    results, metrics = monitor.process_batch(candles)

    # Aggregate results
    valid_count = sum(1 for r in results if r.is_valid)
    total_issues = sum(len(r.issues) for r in results)
    avg_quality = (
        sum(r.quality_score for r in results) / len(results) if results else 100.0
    )

    return {
        "total_candles": len(results),
        "valid_candles": valid_count,
        "invalid_candles": len(results) - valid_count,
        "total_issues": total_issues,
        "average_quality": avg_quality,
        "quality_level": monitor.get_quality_level(avg_quality).value,
        "metrics": {
            "symbol": metrics.symbol,
            "interval": metrics.interval,
            "quality_score": metrics.quality_score,
        },
    }


@router.get("/metrics", response_model=list[DataQualityMetricsResponse])
async def get_all_metrics():
    """Get quality metrics for all monitored symbols."""
    monitor = get_data_quality_monitor()
    all_metrics = monitor.get_all_metrics()

    return [
        DataQualityMetricsResponse(
            symbol=m.symbol,
            interval=m.interval,
            total_candles=m.total_candles,
            valid_candles=m.valid_candles,
            issues_detected=m.issues_detected,
            gaps_detected=m.gaps_detected,
            spikes_detected=m.spikes_detected,
            quality_score=m.quality_score,
            quality_level=monitor.get_quality_level(m.quality_score).value,
            last_update=m.last_update,
            staleness_seconds=m.staleness_seconds,
        )
        for m in all_metrics.values()
    ]


@router.get("/metrics/{symbol}/{interval}", response_model=DataQualityMetricsResponse)
async def get_symbol_metrics(symbol: str, interval: str):
    """Get quality metrics for a specific symbol/interval."""
    monitor = get_data_quality_monitor()
    metrics = monitor.get_metrics(symbol, interval)

    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for {symbol}:{interval}",
        )

    return DataQualityMetricsResponse(
        symbol=metrics.symbol,
        interval=metrics.interval,
        total_candles=metrics.total_candles,
        valid_candles=metrics.valid_candles,
        issues_detected=metrics.issues_detected,
        gaps_detected=metrics.gaps_detected,
        spikes_detected=metrics.spikes_detected,
        quality_score=metrics.quality_score,
        quality_level=monitor.get_quality_level(metrics.quality_score).value,
        last_update=metrics.last_update,
        staleness_seconds=metrics.staleness_seconds,
    )


@router.get("/issues", response_model=list[DataQualityIssueResponse])
async def get_recent_issues(
    limit: int = 100,
    symbol: str | None = None,
    issue_type: str | None = None,
):
    """Get recent data quality issues."""
    monitor = get_data_quality_monitor()

    # Validate issue type
    type_enum = None
    if issue_type:
        try:
            type_enum = DataIssueType(issue_type)
        except ValueError:
            valid = [t.value for t in DataIssueType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid issue_type. Valid: {valid}",
            )

    issues = monitor.get_recent_issues(limit=limit, symbol=symbol, issue_type=type_enum)

    return [
        DataQualityIssueResponse(
            issue_type=i.issue_type.value,
            symbol=i.symbol,
            interval=i.interval,
            timestamp=i.timestamp,
            severity=i.severity,
            description=i.description,
            raw_data=i.raw_data,
            auto_corrected=i.auto_corrected,
        )
        for i in issues
    ]


@router.get("/check-staleness", response_model=list[DataQualityIssueResponse])
async def check_staleness():
    """Check for stale data across all monitored symbols."""
    monitor = get_data_quality_monitor()
    stale_issues = monitor.check_all_staleness()

    return [
        DataQualityIssueResponse(
            issue_type=i.issue_type.value,
            symbol=i.symbol,
            interval=i.interval,
            timestamp=i.timestamp,
            severity=i.severity,
            description=i.description,
            raw_data=i.raw_data,
            auto_corrected=i.auto_corrected,
        )
        for i in stale_issues
    ]


@router.get("/issue-types")
async def list_issue_types():
    """List all data quality issue types."""
    return {
        "issue_types": [t.value for t in DataIssueType],
        "quality_levels": [lv.value for lv in DataQualityLevel],
    }


@router.get("/health")
async def get_data_quality_health():
    """Get data quality health status."""
    monitor = get_data_quality_monitor()
    summary = monitor.get_summary()
    stale = monitor.check_all_staleness()

    # Determine overall health
    quality = summary["overall_quality"]
    stale_count = len(stale)

    if quality >= 90 and stale_count == 0:
        health = "healthy"
    elif quality >= 70 and stale_count <= 2:
        health = "degraded"
    else:
        health = "unhealthy"

    return {
        "health": health,
        "quality_score": quality,
        "quality_level": summary["quality_level"],
        "symbols_monitored": summary["symbols_monitored"],
        "stale_symbols": stale_count,
        "total_issues": summary["total_issues"],
    }
