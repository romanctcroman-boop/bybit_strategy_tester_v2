"""
State Management API Router.

Provides REST API endpoints for unified state management.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from backend.services.state_manager import (
    Order,
    OrderStatus,
    Position,
    PositionSide,
    StateSource,
    get_state_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/state", tags=["State Management"])

# Valid order types and sides
VALID_ORDER_SIDES = {"buy", "sell"}
VALID_ORDER_TYPES = {
    "market",
    "limit",
    "stop_market",
    "stop_limit",
    "take_profit_market",
}
VALID_SYMBOLS_PATTERN = re.compile(r"^[A-Z0-9]{2,10}(USDT|USD|BTC|ETH)$")


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateOrderRequest(BaseModel):
    """Create order request with comprehensive validation."""

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")
    side: str = Field(..., description="Order side: buy or sell")
    order_type: str = Field(..., description="Order type: market, limit, etc.")
    quantity: float = Field(..., gt=0, le=1_000_000, description="Order quantity")
    price: Optional[float] = Field(
        None, gt=0, description="Limit price (for limit orders)"
    )
    client_order_id: Optional[str] = Field(
        None, max_length=64, description="Client order ID"
    )
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate trading symbol format."""
        v = v.upper().strip()
        if not VALID_SYMBOLS_PATTERN.match(v):
            raise ValueError(
                f"Invalid symbol format: {v}. Expected format: BTCUSDT, ETHUSDT, etc."
            )
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate order side."""
        v = v.lower().strip()
        if v not in VALID_ORDER_SIDES:
            raise ValueError(
                f"Invalid order side: {v}. Must be one of: {VALID_ORDER_SIDES}"
            )
        return v

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        """Validate order type."""
        v = v.lower().strip()
        if v not in VALID_ORDER_TYPES:
            raise ValueError(
                f"Invalid order type: {v}. Must be one of: {VALID_ORDER_TYPES}"
            )
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        """Validate order quantity."""
        if v <= 0:
            raise ValueError("Quantity must be positive")
        if v > 1_000_000:
            raise ValueError("Quantity exceeds maximum limit of 1,000,000")
        return v


class UpdateOrderRequest(BaseModel):
    """Update order request."""

    status: Optional[str] = None
    filled_quantity: Optional[float] = None
    average_price: Optional[float] = None
    exchange_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OrderResponse(BaseModel):
    """Order response."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float]
    status: str
    filled_quantity: float
    average_price: float
    created_at: str
    updated_at: str
    exchange_order_id: Optional[str]
    client_order_id: Optional[str]
    metadata: Dict[str, Any]


class OpenPositionRequest(BaseModel):
    """Open position request."""

    symbol: str = Field(..., description="Trading pair symbol")
    side: str = Field(..., description="Position side: long or short")
    quantity: float = Field(..., gt=0, description="Position quantity")
    entry_price: float = Field(..., gt=0, description="Entry price")
    leverage: float = Field(1.0, ge=1, description="Leverage")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdatePositionRequest(BaseModel):
    """Update position request."""

    current_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ClosePositionRequest(BaseModel):
    """Close position request."""

    close_price: float = Field(..., gt=0, description="Close price")


class PositionResponse(BaseModel):
    """Position response."""

    position_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: float
    margin_used: float
    created_at: str
    updated_at: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    metadata: Dict[str, Any]


class StateMetricsResponse(BaseModel):
    """State metrics response."""

    orders_in_redis: int
    orders_in_postgres: int
    positions_in_redis: int
    positions_in_postgres: int
    pending_events: int
    processed_events: int
    failed_events: int
    conflicts_detected: int
    conflicts_resolved: int
    last_sync: Optional[str]
    sync_latency_ms: float
    redis_latency_ms: float
    postgres_latency_ms: float


class ConflictResponse(BaseModel):
    """Conflict response."""

    conflict_id: str
    entity_type: str
    entity_id: str
    redis_timestamp: str
    postgres_timestamp: str
    resolved: bool
    resolution: Optional[str]
    resolved_at: Optional[str]


class SyncResponse(BaseModel):
    """Sync response."""

    synced_orders: int
    synced_positions: int
    conflicts_detected: int
    conflicts_resolved: int
    errors: List[str]


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    running: bool
    metrics: Dict[str, Any]
    event_queue: Dict[str, int]


# ============================================================================
# Helper Functions
# ============================================================================


def order_to_response(order: Order) -> OrderResponse:
    """Convert Order to OrderResponse."""
    return OrderResponse(
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        status=order.status.value
        if isinstance(order.status, OrderStatus)
        else order.status,
        filled_quantity=order.filled_quantity,
        average_price=order.average_price,
        created_at=order.created_at.isoformat() if order.created_at else "",
        updated_at=order.updated_at.isoformat() if order.updated_at else "",
        exchange_order_id=order.exchange_order_id,
        client_order_id=order.client_order_id,
        metadata=order.metadata,
    )


def position_to_response(position: Position) -> PositionResponse:
    """Convert Position to PositionResponse."""
    return PositionResponse(
        position_id=position.position_id,
        symbol=position.symbol,
        side=position.side.value
        if isinstance(position.side, PositionSide)
        else position.side,
        quantity=position.quantity,
        entry_price=position.entry_price,
        current_price=position.current_price,
        unrealized_pnl=position.unrealized_pnl,
        realized_pnl=position.realized_pnl,
        leverage=position.leverage,
        margin_used=position.margin_used,
        created_at=position.created_at.isoformat() if position.created_at else "",
        updated_at=position.updated_at.isoformat() if position.updated_at else "",
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        metadata=position.metadata,
    )


# ============================================================================
# Order Endpoints
# ============================================================================


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(request: CreateOrderRequest):
    """Create new order with pre-trade validation."""
    try:
        # Validate limit orders have price
        if request.order_type in ("limit", "stop_limit") and request.price is None:
            raise HTTPException(
                status_code=400,
                detail=f"Price is required for {request.order_type} orders",
            )

        # Risk checks - get current risk metrics
        try:
            from backend.services.risk_dashboard import get_risk_dashboard

            risk_dashboard = get_risk_dashboard()
            risk_summary = risk_dashboard.get_risk_summary()

            # Check if trading is blocked due to high risk
            if risk_summary.get("overall_risk_level") == "critical":
                raise HTTPException(
                    status_code=403,
                    detail="Trading blocked: Critical risk level detected. Check risk dashboard.",
                )

            # Check exposure limits
            thresholds = risk_summary.get("thresholds", {})
            portfolio = risk_summary.get("portfolio", {})
            max_exposure = thresholds.get("max_exposure", 100.0)
            current_exposure = portfolio.get("exposure_pct", 0.0)

            if current_exposure >= max_exposure:
                raise HTTPException(
                    status_code=403,
                    detail=f"Max exposure limit reached: {current_exposure:.1f}% >= {max_exposure:.1f}%",
                )

            logger.info(
                f"Risk check passed for order: {request.symbol} {request.side} {request.quantity}"
            )
        except ImportError:
            logger.warning("Risk dashboard not available, skipping risk checks")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Risk check failed (non-blocking): {e}")

        manager = get_state_manager()

        order = Order(
            order_id="",  # Will be generated
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            client_order_id=request.client_order_id,
            metadata=request.metadata or {},
        )

        created_order = await manager.create_order(order)
        logger.info(
            f"Order created: {created_order.order_id} - {request.symbol} {request.side} {request.quantity}"
        )
        return order_to_response(created_order)
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error creating order: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    source: str = Query("redis", description="Data source: redis or postgres"),
):
    """List orders."""
    try:
        manager = get_state_manager()
        state_source = (
            StateSource.POSTGRES if source.lower() == "postgres" else StateSource.REDIS
        )
        orders = await manager.list_orders(symbol=symbol, source=state_source)
        return [order_to_response(o) for o in orders]
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    source: str = Query("redis", description="Data source: redis or postgres"),
):
    """Get order by ID."""
    try:
        manager = get_state_manager()
        state_source = (
            StateSource.POSTGRES if source.lower() == "postgres" else StateSource.REDIS
        )
        order = await manager.get_order(order_id, source=state_source)

        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

        return order_to_response(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(order_id: str, request: UpdateOrderRequest):
    """Update order."""
    try:
        manager = get_state_manager()
        order = await manager.get_order(order_id)

        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

        if request.status:
            order.status = OrderStatus(request.status)
        if request.filled_quantity is not None:
            order.filled_quantity = request.filled_quantity
        if request.average_price is not None:
            order.average_price = request.average_price
        if request.exchange_order_id:
            order.exchange_order_id = request.exchange_order_id
        if request.metadata:
            order.metadata.update(request.metadata)

        updated_order = await manager.update_order(order)
        return order_to_response(updated_order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: str):
    """Cancel order."""
    try:
        manager = get_state_manager()
        order = await manager.cancel_order(order_id)

        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

        return order_to_response(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Position Endpoints
# ============================================================================


@router.post("/positions", response_model=PositionResponse, status_code=201)
async def open_position(request: OpenPositionRequest):
    """Open new position."""
    try:
        manager = get_state_manager()

        position = Position(
            position_id="",  # Will be generated
            symbol=request.symbol,
            side=PositionSide(request.side),
            quantity=request.quantity,
            entry_price=request.entry_price,
            current_price=request.entry_price,
            leverage=request.leverage,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            metadata=request.metadata or {},
        )

        created_position = await manager.open_position(position)
        return position_to_response(created_position)
    except Exception as e:
        logger.error(f"Error opening position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=List[PositionResponse])
async def list_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    source: str = Query("redis", description="Data source: redis or postgres"),
):
    """List positions."""
    try:
        manager = get_state_manager()
        state_source = (
            StateSource.POSTGRES if source.lower() == "postgres" else StateSource.REDIS
        )
        positions = await manager.list_positions(symbol=symbol, source=state_source)
        return [position_to_response(p) for p in positions]
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: str,
    source: str = Query("redis", description="Data source: redis or postgres"),
):
    """Get position by ID."""
    try:
        manager = get_state_manager()
        state_source = (
            StateSource.POSTGRES if source.lower() == "postgres" else StateSource.REDIS
        )
        position = await manager.get_position(position_id, source=state_source)

        if not position:
            raise HTTPException(
                status_code=404, detail=f"Position {position_id} not found"
            )

        return position_to_response(position)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(position_id: str, request: UpdatePositionRequest):
    """Update position."""
    try:
        manager = get_state_manager()
        position = await manager.get_position(position_id)

        if not position:
            raise HTTPException(
                status_code=404, detail=f"Position {position_id} not found"
            )

        if request.current_price is not None:
            position.current_price = request.current_price
        if request.stop_loss is not None:
            position.stop_loss = request.stop_loss
        if request.take_profit is not None:
            position.take_profit = request.take_profit
        if request.metadata:
            position.metadata.update(request.metadata)

        updated_position = await manager.update_position(position)
        return position_to_response(updated_position)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/{position_id}/close", response_model=PositionResponse)
async def close_position(position_id: str, request: ClosePositionRequest):
    """Close position."""
    try:
        manager = get_state_manager()
        position = await manager.close_position(position_id, request.close_price)

        if not position:
            raise HTTPException(
                status_code=404, detail=f"Position {position_id} not found"
            )

        return position_to_response(position)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# State Management Endpoints
# ============================================================================


@router.post("/sync", response_model=SyncResponse)
async def sync_state():
    """Manually trigger state synchronization."""
    try:
        manager = get_state_manager()
        result = await manager.sync_state()
        return SyncResponse(**result)
    except Exception as e:
        logger.error(f"Error syncing state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=StateMetricsResponse)
async def get_metrics():
    """Get state management metrics."""
    try:
        manager = get_state_manager()
        metrics = manager.get_metrics()
        return StateMetricsResponse(
            orders_in_redis=metrics.orders_in_redis,
            orders_in_postgres=metrics.orders_in_postgres,
            positions_in_redis=metrics.positions_in_redis,
            positions_in_postgres=metrics.positions_in_postgres,
            pending_events=metrics.pending_events,
            processed_events=metrics.processed_events,
            failed_events=metrics.failed_events,
            conflicts_detected=metrics.conflicts_detected,
            conflicts_resolved=metrics.conflicts_resolved,
            last_sync=metrics.last_sync.isoformat() if metrics.last_sync else None,
            sync_latency_ms=metrics.sync_latency_ms,
            redis_latency_ms=metrics.redis_latency_ms,
            postgres_latency_ms=metrics.postgres_latency_ms,
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conflicts", response_model=List[ConflictResponse])
async def get_conflicts(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
):
    """Get state conflicts."""
    try:
        manager = get_state_manager()
        conflicts = manager.get_conflicts(resolved=resolved)
        return [
            ConflictResponse(
                conflict_id=c.conflict_id,
                entity_type=c.entity_type,
                entity_id=c.entity_id,
                redis_timestamp=c.redis_timestamp.isoformat(),
                postgres_timestamp=c.postgres_timestamp.isoformat(),
                resolved=c.resolved,
                resolution=c.resolution.value if c.resolution else None,
                resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
            )
            for c in conflicts
        ]
    except Exception as e:
        logger.error(f"Error getting conflicts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(100, ge=1, le=1000, description="Number of entries to return"),
):
    """Get audit log."""
    try:
        manager = get_state_manager()
        return manager.get_audit_log(limit=limit)
    except Exception as e:
        logger.error(f"Error getting audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Get state management health status."""
    try:
        manager = get_state_manager()
        health = manager.get_health()
        return HealthResponse(**health)
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_manager():
    """Start state manager background tasks."""
    try:
        manager = get_state_manager()
        await manager.start()
        return {"status": "started"}
    except Exception as e:
        logger.error(f"Error starting manager: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_manager():
    """Stop state manager background tasks."""
    try:
        manager = get_state_manager()
        await manager.stop()
        return {"status": "stopped"}
    except Exception as e:
        logger.error(f"Error stopping manager: {e}")
        raise HTTPException(status_code=500, detail=str(e))
