"""
ML Anomaly Detection API Router.

AI Agent Recommendation Implementation:
Provides REST API endpoints for ML-based anomaly detection.
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.ml_anomaly_detection import (
    AnomalySeverity,
    AnomalyType,
    DataPoint,
    get_anomaly_detector,
)

router = APIRouter(prefix="/api/v1/anomaly-detection")


# ============================================================================
# Request/Response Models
# ============================================================================


class DataPointRequest(BaseModel):
    """Request to add a data point for anomaly detection."""

    value: float = Field(..., description="The value to check")
    symbol: str = Field(default="", description="Trading symbol")
    metric_type: str = Field(default="price", description="Type of metric")
    timestamp: Optional[float] = Field(
        default=None, description="Unix timestamp (defaults to now)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "value": 45000.0,
                "symbol": "BTCUSDT",
                "metric_type": "price",
                "metadata": {"source": "bybit"},
            }
        }
    }


class BatchDataPointsRequest(BaseModel):
    """Request to add multiple data points."""

    points: list[DataPointRequest] = Field(..., description="List of data points")


class MultivariateCheckRequest(BaseModel):
    """Request for multivariate anomaly check."""

    features: list[float] = Field(
        ..., description="Feature vector for multivariate check"
    )

    model_config = {
        "json_schema_extra": {"example": {"features": [45000.0, 1000.5, 0.02, 1.5]}}
    }


class AnomalyEventResponse(BaseModel):
    """Response model for anomaly event."""

    id: str
    anomaly_type: str
    severity: str
    timestamp: datetime
    value: float
    expected_range: tuple[float, float]
    z_score: float
    symbol: str
    metric_type: str
    description: str
    metadata: dict[str, Any]
    acknowledged: bool


class AnomalyStatsResponse(BaseModel):
    """Response model for anomaly statistics."""

    total_detections: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_symbol: dict[str, int]
    last_detection: Optional[datetime]
    detection_rate_per_hour: float


class RollingStatsResponse(BaseModel):
    """Response model for rolling statistics."""

    mean: float
    std: float
    count: int
    z_score_threshold: float


class DetectorStatusResponse(BaseModel):
    """Response model for detector status."""

    enabled: bool
    z_score_threshold: float
    window_size: int
    metrics_tracked: int
    multivariate_samples: int
    isolation_forest_fitted: bool
    total_anomalies: int
    unacknowledged_anomalies: int
    uptime_hours: float


class MultivariateCheckResponse(BaseModel):
    """Response for multivariate anomaly check."""

    is_anomaly: bool
    anomaly_score: float
    threshold: float


class ConfigUpdateRequest(BaseModel):
    """Request to update detector configuration."""

    z_score_threshold: Optional[float] = Field(
        default=None, ge=1.0, le=10.0, description="Z-score threshold"
    )
    window_size: Optional[int] = Field(
        default=None, ge=10, le=1000, description="Rolling window size"
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=DetectorStatusResponse)
async def get_detector_status():
    """
    Get anomaly detector status.

    Returns current configuration and statistics.
    """
    detector = get_anomaly_detector()
    return DetectorStatusResponse(**detector.get_status())


@router.post("/data-point", response_model=Optional[AnomalyEventResponse])
async def add_data_point(request: DataPointRequest):
    """
    Add data point for anomaly detection.

    Returns detected anomaly if found, null otherwise.
    """
    import time as _time

    detector = get_anomaly_detector()

    point = DataPoint(
        timestamp=request.timestamp or _time.time(),
        value=request.value,
        symbol=request.symbol,
        metric_type=request.metric_type,
        metadata=request.metadata,
    )

    anomaly = detector.add_data_point(point)

    if anomaly:
        return AnomalyEventResponse(
            id=anomaly.id,
            anomaly_type=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
            timestamp=anomaly.timestamp,
            value=anomaly.value,
            expected_range=anomaly.expected_range,
            z_score=anomaly.z_score,
            symbol=anomaly.symbol,
            metric_type=anomaly.metric_type,
            description=anomaly.description,
            metadata=anomaly.metadata,
            acknowledged=anomaly.acknowledged,
        )
    return None


@router.post("/batch", response_model=list[AnomalyEventResponse])
async def add_batch_data_points(request: BatchDataPointsRequest):
    """
    Add multiple data points and return detected anomalies.

    Efficient for bulk data ingestion.
    """
    import time as _time

    detector = get_anomaly_detector()
    detected_anomalies = []

    for point_req in request.points:
        point = DataPoint(
            timestamp=point_req.timestamp or _time.time(),
            value=point_req.value,
            symbol=point_req.symbol,
            metric_type=point_req.metric_type,
            metadata=point_req.metadata,
        )

        anomaly = detector.add_data_point(point)
        if anomaly:
            detected_anomalies.append(
                AnomalyEventResponse(
                    id=anomaly.id,
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity.value,
                    timestamp=anomaly.timestamp,
                    value=anomaly.value,
                    expected_range=anomaly.expected_range,
                    z_score=anomaly.z_score,
                    symbol=anomaly.symbol,
                    metric_type=anomaly.metric_type,
                    description=anomaly.description,
                    metadata=anomaly.metadata,
                    acknowledged=anomaly.acknowledged,
                )
            )

    return detected_anomalies


@router.post("/check-multivariate", response_model=MultivariateCheckResponse)
async def check_multivariate_anomaly(request: MultivariateCheckRequest):
    """
    Check for multivariate anomaly using Isolation Forest.

    Useful for detecting complex patterns across multiple features.
    """
    detector = get_anomaly_detector()

    if not detector._isolation_forest._fitted:
        raise HTTPException(
            status_code=400,
            detail="Isolation Forest not yet trained. Add more data points first.",
        )

    is_anomaly, score = detector.check_multivariate_anomaly(request.features)

    return MultivariateCheckResponse(
        is_anomaly=is_anomaly,
        anomaly_score=score,
        threshold=detector._isolation_forest.threshold,
    )


@router.get("/anomalies", response_model=list[AnomalyEventResponse])
async def get_recent_anomalies(
    limit: int = 100,
    severity: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    symbol: Optional[str] = None,
):
    """
    Get recent detected anomalies.

    Supports filtering by severity, type, and symbol.
    """
    detector = get_anomaly_detector()

    # Validate and convert severity
    severity_enum = None
    if severity:
        try:
            severity_enum = AnomalySeverity(severity)
        except ValueError:
            valid = [s.value for s in AnomalySeverity]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Valid: {valid}",
            )

    # Validate and convert anomaly type
    type_enum = None
    if anomaly_type:
        try:
            type_enum = AnomalyType(anomaly_type)
        except ValueError:
            valid = [t.value for t in AnomalyType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid anomaly_type. Valid: {valid}",
            )

    anomalies = detector.get_recent_anomalies(
        limit=limit,
        severity=severity_enum,
        anomaly_type=type_enum,
        symbol=symbol,
    )

    return [
        AnomalyEventResponse(
            id=a.id,
            anomaly_type=a.anomaly_type.value,
            severity=a.severity.value,
            timestamp=a.timestamp,
            value=a.value,
            expected_range=a.expected_range,
            z_score=a.z_score,
            symbol=a.symbol,
            metric_type=a.metric_type,
            description=a.description,
            metadata=a.metadata,
            acknowledged=a.acknowledged,
        )
        for a in anomalies
    ]


@router.get("/statistics", response_model=AnomalyStatsResponse)
async def get_anomaly_statistics():
    """Get anomaly detection statistics."""
    detector = get_anomaly_detector()
    stats = detector.get_statistics()

    return AnomalyStatsResponse(
        total_detections=stats.total_detections,
        by_type=stats.by_type,
        by_severity=stats.by_severity,
        by_symbol=stats.by_symbol,
        last_detection=stats.last_detection,
        detection_rate_per_hour=stats.detection_rate_per_hour,
    )


@router.get(
    "/rolling-stats/{symbol}/{metric_type}", response_model=RollingStatsResponse
)
async def get_rolling_statistics(symbol: str, metric_type: str):
    """
    Get rolling statistics for a specific metric.

    Used to understand baseline statistics for anomaly detection.
    """
    detector = get_anomaly_detector()
    stats = detector.get_rolling_stats(symbol, metric_type)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"No statistics found for {symbol}:{metric_type}",
        )

    return RollingStatsResponse(**stats)


@router.post("/acknowledge/{anomaly_id}")
async def acknowledge_anomaly(anomaly_id: str):
    """Acknowledge an anomaly event."""
    detector = get_anomaly_detector()

    if not detector.acknowledge_anomaly(anomaly_id):
        raise HTTPException(
            status_code=404,
            detail=f"Anomaly {anomaly_id} not found",
        )

    return {"status": "acknowledged", "anomaly_id": anomaly_id}


@router.get("/types")
async def list_anomaly_types():
    """List all supported anomaly types."""
    return {
        "anomaly_types": [t.value for t in AnomalyType],
        "severity_levels": [s.value for s in AnomalySeverity],
    }


@router.get("/metrics-tracked")
async def list_tracked_metrics():
    """List all metrics currently being tracked."""
    detector = get_anomaly_detector()

    return {
        "metrics": list(detector._rolling_stats.keys()),
        "count": len(detector._rolling_stats),
    }


@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update detector configuration.

    Note: Changes affect future detections only.
    """
    detector = get_anomaly_detector()

    if request.z_score_threshold is not None:
        detector.z_score_threshold = request.z_score_threshold

    if request.window_size is not None:
        detector.window_size = request.window_size
        # Note: existing rolling stats keep their old window size

    return {
        "status": "updated",
        "z_score_threshold": detector.z_score_threshold,
        "window_size": detector.window_size,
    }


@router.post("/train-isolation-forest")
async def train_isolation_forest():
    """
    Manually trigger Isolation Forest training.

    Uses current multivariate buffer data.
    """
    detector = get_anomaly_detector()

    if len(detector._multivariate_buffer) < detector._min_samples_for_iforest:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {detector._min_samples_for_iforest} samples. "
            f"Currently have {len(detector._multivariate_buffer)}.",
        )

    detector._retrain_isolation_forest()

    return {
        "status": "trained",
        "samples_used": len(detector._multivariate_buffer),
        "threshold": detector._isolation_forest.threshold,
    }


@router.get("/summary")
async def get_anomaly_summary():
    """
    Get comprehensive anomaly detection summary.

    Includes status, statistics, and recent critical anomalies.
    """
    detector = get_anomaly_detector()
    status = detector.get_status()
    stats = detector.get_statistics()

    # Get recent critical anomalies
    critical = detector.get_recent_anomalies(
        limit=10, severity=AnomalySeverity.CRITICAL
    )
    high = detector.get_recent_anomalies(limit=10, severity=AnomalySeverity.HIGH)

    return {
        "status": status,
        "statistics": {
            "total_detections": stats.total_detections,
            "by_type": stats.by_type,
            "by_severity": stats.by_severity,
            "by_symbol": stats.by_symbol,
            "last_detection": stats.last_detection.isoformat()
            if stats.last_detection
            else None,
            "detection_rate_per_hour": stats.detection_rate_per_hour,
        },
        "recent_critical": [
            {
                "id": a.id,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged,
            }
            for a in critical
        ],
        "recent_high": [
            {
                "id": a.id,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged,
            }
            for a in high
        ],
    }
