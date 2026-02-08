"""
Unified Prometheus Metrics Module

Consolidates all application metrics in one place:
- Backfill/data ingestion metrics
- MCP tool metrics
- Circuit breaker metrics
- Strategy health metrics
- Anomaly detection metrics

Usage:
    from backend.core.metrics import metrics

    # Increment counters
    metrics.backfill_upserts(symbol="BTCUSDT", interval="1h", count=100)

    # Observe durations
    metrics.observe_backfill_duration(seconds=15.5)

    # Track strategy health
    metrics.record_strategy_health(strategy_id="my_strategy", health_score=0.85)
"""

import logging

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

# =============================================================================
# REGISTRY - Custom registry to avoid conflicts with default registry
# =============================================================================

REGISTRY = CollectorRegistry()

# =============================================================================
# BACKFILL / DATA INGESTION METRICS
# =============================================================================

BACKFILL_UPSERTS = Counter(
    "backfill_upserts_total",
    "Total number of upserts performed by backfill",
    labelnames=["symbol", "interval"],
    registry=REGISTRY,
)

BACKFILL_PAGES = Counter(
    "backfill_pages_total",
    "Total number of pages processed by backfill",
    labelnames=["symbol", "interval"],
    registry=REGISTRY,
)

BACKFILL_DURATION = Histogram(
    "backfill_duration_seconds",
    "Backfill duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, float("inf")),
    registry=REGISTRY,
)

RUNS_BY_STATUS = Counter(
    "backfill_runs_total",
    "Backfill runs by terminal status",
    labelnames=["status"],
    registry=REGISTRY,
)

# =============================================================================
# MCP / AI AGENT METRICS
# =============================================================================

MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    labelnames=["tool", "success"],
    registry=REGISTRY,
)

MCP_TOOL_ERRORS = Counter(
    "mcp_tool_errors_total",
    "Total MCP tool errors",
    labelnames=["tool", "error_type"],
    registry=REGISTRY,
)

MCP_TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution latency",
    labelnames=["tool"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, float("inf")),
    registry=REGISTRY,
)

MCP_BRIDGE_CALLS = Counter(
    "mcp_bridge_calls_total",
    "MCP bridge direct calls (no HTTP)",
    labelnames=["tool", "success"],
    registry=REGISTRY,
)

MCP_BRIDGE_DURATION = Histogram(
    "mcp_bridge_tool_duration_seconds",
    "Duration of MCP bridge tool calls",
    labelnames=["tool", "success"],
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2,
        5,
        10,
        30,
        float("inf"),
    ),
    registry=REGISTRY,
)

# =============================================================================
# MULTI-AGENT SYSTEM METRICS
# =============================================================================

CONSENSUS_LOOP_PREVENTED = Counter(
    "consensus_loop_prevented_total",
    "Total consensus loops prevented by guard",
    labelnames=["reason"],  # iteration_cap, duplicate, frequency, depth
    registry=REGISTRY,
)

DLQ_MESSAGES = Counter(
    "dlq_messages_total",
    "Total messages enqueued to DLQ",
    labelnames=["priority", "agent_type"],
    registry=REGISTRY,
)

DLQ_RETRIES = Counter(
    "dlq_retries_total",
    "Total DLQ retry attempts",
    labelnames=["status"],  # success, failed, expired
    registry=REGISTRY,
)

CORRELATION_ID_REQUESTS = Counter(
    "correlation_id_requests_total",
    "Requests with correlation IDs",
    labelnames=["has_correlation_id"],  # true, false
    registry=REGISTRY,
)

# =============================================================================
# CIRCUIT BREAKER METRICS
# =============================================================================

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    labelnames=["service"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_FAILURES = Counter(
    "circuit_breaker_failures_total",
    "Total failures recorded by circuit breaker",
    labelnames=["service"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_SUCCESSES = Counter(
    "circuit_breaker_successes_total",
    "Total successes recorded by circuit breaker",
    labelnames=["service"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_OPENED = Counter(
    "circuit_breaker_opened_total",
    "Times circuit breaker opened",
    labelnames=["service"],
    registry=REGISTRY,
)

# =============================================================================
# STRATEGY HEALTH METRICS
# =============================================================================

STRATEGY_HEALTH_SCORE = Gauge(
    "strategy_health_score",
    "Health score of trading strategy (0-1)",
    labelnames=["strategy_id", "strategy_name"],
    registry=REGISTRY,
)

STRATEGY_DRAWDOWN = Gauge(
    "strategy_drawdown_percent",
    "Current drawdown percentage",
    labelnames=["strategy_id"],
    registry=REGISTRY,
)

STRATEGY_WIN_RATE = Gauge(
    "strategy_win_rate",
    "Win rate of strategy (0-1)",
    labelnames=["strategy_id"],
    registry=REGISTRY,
)

STRATEGY_SHARPE_RATIO = Gauge(
    "strategy_sharpe_ratio",
    "Sharpe ratio of strategy",
    labelnames=["strategy_id"],
    registry=REGISTRY,
)

STRATEGY_TRADES_TOTAL = Counter(
    "strategy_trades_total",
    "Total trades executed",
    labelnames=["strategy_id", "side", "result"],
    registry=REGISTRY,
)

STRATEGY_PNL_TOTAL = Counter(
    "strategy_pnl_total_usd",
    "Total PnL in USD",
    labelnames=["strategy_id"],
    registry=REGISTRY,
)

# =============================================================================
# TICK SYSTEM METRICS
# =============================================================================

TICK_TRADES_PROCESSED = Counter(
    "tick_trades_processed_total",
    "Total trades processed by tick system",
    labelnames=["symbol"],
    registry=REGISTRY,
)

TICK_CANDLES_CREATED = Counter(
    "tick_candles_created_total",
    "Total candles created from tick aggregation",
    labelnames=["symbol", "interval"],
    registry=REGISTRY,
)

TICK_PROCESSING_LATENCY = Histogram(
    "tick_processing_latency_seconds",
    "Latency of tick processing (trade to candle)",
    labelnames=["symbol"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=REGISTRY,
)

TICK_WEBSOCKET_CONNECTIONS = Gauge(
    "tick_websocket_connections",
    "Active WebSocket connections for tick streaming",
    labelnames=["mode"],  # direct, redis
    registry=REGISTRY,
)

TICK_AGGREGATORS_ACTIVE = Gauge(
    "tick_aggregators_active",
    "Number of active tick aggregators",
    registry=REGISTRY,
)

TICK_REDIS_MESSAGES = Counter(
    "tick_redis_messages_total",
    "Redis Pub/Sub messages for tick distribution",
    labelnames=["direction"],  # publish, subscribe
    registry=REGISTRY,
)

TICK_CALLBACKS_REGISTERED = Gauge(
    "tick_callbacks_registered",
    "Number of registered tick callbacks",
    labelnames=["callback_type"],  # trade, candle
    registry=REGISTRY,
)

TICK_BUFFER_SIZE = Gauge(
    "tick_buffer_size",
    "Current size of tick buffer per aggregator",
    labelnames=["symbol"],
    registry=REGISTRY,
)

# =============================================================================
# ANOMALY DETECTION METRICS
# =============================================================================

ANOMALY_DETECTED = Counter(
    "anomaly_detected_total",
    "Total anomalies detected",
    labelnames=[
        "anomaly_type",
        "severity",
    ],  # price_spike, volume_spike, correlation_break
    registry=REGISTRY,
)

ANOMALY_SCORE = Gauge(
    "anomaly_score",
    "Current anomaly score (0-1)",
    labelnames=["metric_name"],
    registry=REGISTRY,
)

ALERT_FIRED = Counter(
    "alerts_fired_total",
    "Total alerts fired",
    labelnames=["alert_name", "severity"],  # info, warning, critical
    registry=REGISTRY,
)

ALERT_ACKNOWLEDGED = Counter(
    "alerts_acknowledged_total",
    "Total alerts acknowledged",
    labelnames=["alert_name"],
    registry=REGISTRY,
)

# =============================================================================
# API PERFORMANCE METRICS
# =============================================================================

API_REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    labelnames=["method", "endpoint", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf")),
    registry=REGISTRY,
)

API_REQUEST_TOTAL = Counter(
    "api_requests_total",
    "Total API requests",
    labelnames=["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

# =============================================================================
# HELPER CLASS FOR EASY ACCESS
# =============================================================================


class MetricsCollector:
    """
    Unified interface for recording metrics.

    Usage:
        from backend.core.metrics import metrics

        metrics.backfill_upserts("BTCUSDT", "1h", 100)
        metrics.record_circuit_breaker_state("bybit_api", "open")
    """

    def __init__(self):
        self._registry = REGISTRY

    # -------------------------------------------------------------------------
    # Backfill Metrics
    # -------------------------------------------------------------------------

    def backfill_upserts(self, symbol: str, interval: str, count: int = 1) -> None:
        """Increment backfill upserts counter."""
        try:
            BACKFILL_UPSERTS.labels(symbol=symbol, interval=interval).inc(count)
        except Exception as e:
            logger.warning(f"Failed to record backfill upserts: {e}")

    def backfill_pages(self, symbol: str, interval: str, count: int = 1) -> None:
        """Increment backfill pages counter."""
        try:
            BACKFILL_PAGES.labels(symbol=symbol, interval=interval).inc(count)
        except Exception as e:
            logger.warning(f"Failed to record backfill pages: {e}")

    def observe_backfill_duration(self, seconds: float) -> None:
        """Record backfill duration."""
        try:
            BACKFILL_DURATION.observe(seconds)
        except Exception as e:
            logger.warning(f"Failed to record backfill duration: {e}")

    def backfill_run_status(self, status: str) -> None:
        """Increment run status counter."""
        try:
            RUNS_BY_STATUS.labels(status=status).inc()
        except Exception as e:
            logger.warning(f"Failed to record run status: {e}")

    # -------------------------------------------------------------------------
    # MCP Tool Metrics
    # -------------------------------------------------------------------------

    def mcp_tool_call(
        self, tool: str, success: bool, duration: float | None = None
    ) -> None:
        """Record MCP tool call."""
        try:
            MCP_TOOL_CALLS.labels(tool=tool, success=str(success).lower()).inc()
            if duration is not None:
                MCP_TOOL_DURATION.labels(tool=tool).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record MCP tool call: {e}")

    def mcp_tool_error(self, tool: str, error_type: str) -> None:
        """Record MCP tool error."""
        try:
            MCP_TOOL_ERRORS.labels(tool=tool, error_type=error_type).inc()
        except Exception as e:
            logger.warning(f"Failed to record MCP tool error: {e}")

    def mcp_bridge_call(
        self, tool: str, success: bool, duration: float | None = None
    ) -> None:
        """Record MCP bridge call."""
        try:
            MCP_BRIDGE_CALLS.labels(tool=tool, success=str(success).lower()).inc()
            if duration is not None:
                MCP_BRIDGE_DURATION.labels(
                    tool=tool, success=str(success).lower()
                ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record MCP bridge call: {e}")

    # -------------------------------------------------------------------------
    # Circuit Breaker Metrics
    # -------------------------------------------------------------------------

    def record_circuit_breaker_state(self, service: str, state: str) -> None:
        """Record circuit breaker state. state: closed, half_open, open"""
        try:
            state_map = {"closed": 0, "half_open": 1, "open": 2}
            CIRCUIT_BREAKER_STATE.labels(service=service).set(state_map.get(state, 0))
        except Exception as e:
            logger.warning(f"Failed to record circuit breaker state: {e}")

    def circuit_breaker_failure(self, service: str) -> None:
        """Record circuit breaker failure."""
        try:
            CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()
        except Exception as e:
            logger.warning(f"Failed to record circuit breaker failure: {e}")

    def circuit_breaker_success(self, service: str) -> None:
        """Record circuit breaker success."""
        try:
            CIRCUIT_BREAKER_SUCCESSES.labels(service=service).inc()
        except Exception as e:
            logger.warning(f"Failed to record circuit breaker success: {e}")

    def circuit_breaker_opened(self, service: str) -> None:
        """Record circuit breaker opened."""
        try:
            CIRCUIT_BREAKER_OPENED.labels(service=service).inc()
        except Exception as e:
            logger.warning(f"Failed to record circuit breaker opened: {e}")

    # -------------------------------------------------------------------------
    # Strategy Health Metrics
    # -------------------------------------------------------------------------

    def record_strategy_health(
        self,
        strategy_id: str,
        health_score: float,
        strategy_name: str = "",
        drawdown: float | None = None,
        win_rate: float | None = None,
        sharpe_ratio: float | None = None,
    ) -> None:
        """Record strategy health metrics."""
        try:
            STRATEGY_HEALTH_SCORE.labels(
                strategy_id=strategy_id, strategy_name=strategy_name or strategy_id
            ).set(health_score)

            if drawdown is not None:
                STRATEGY_DRAWDOWN.labels(strategy_id=strategy_id).set(drawdown)
            if win_rate is not None:
                STRATEGY_WIN_RATE.labels(strategy_id=strategy_id).set(win_rate)
            if sharpe_ratio is not None:
                STRATEGY_SHARPE_RATIO.labels(strategy_id=strategy_id).set(sharpe_ratio)
        except Exception as e:
            logger.warning(f"Failed to record strategy health: {e}")

    def record_trade(self, strategy_id: str, side: str, result: str) -> None:
        """Record trade execution. side: buy/sell, result: win/loss/breakeven"""
        try:
            STRATEGY_TRADES_TOTAL.labels(
                strategy_id=strategy_id, side=side, result=result
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record trade: {e}")

    def record_pnl(self, strategy_id: str, pnl_usd: float) -> None:
        """Record PnL in USD."""
        try:
            STRATEGY_PNL_TOTAL.labels(strategy_id=strategy_id).inc(pnl_usd)
        except Exception as e:
            logger.warning(f"Failed to record PnL: {e}")

    # -------------------------------------------------------------------------
    # Tick System Metrics
    # -------------------------------------------------------------------------

    def tick_trade_processed(self, symbol: str) -> None:
        """Record processed trade."""
        try:
            TICK_TRADES_PROCESSED.labels(symbol=symbol).inc()
        except Exception as e:
            logger.warning(f"Failed to record tick trade: {e}")

    def tick_candle_created(self, symbol: str, interval: str) -> None:
        """Record created candle from tick aggregation."""
        try:
            TICK_CANDLES_CREATED.labels(symbol=symbol, interval=interval).inc()
        except Exception as e:
            logger.warning(f"Failed to record tick candle: {e}")

    def tick_processing_latency(self, symbol: str, latency_seconds: float) -> None:
        """Record tick processing latency."""
        try:
            TICK_PROCESSING_LATENCY.labels(symbol=symbol).observe(latency_seconds)
        except Exception as e:
            logger.warning(f"Failed to record tick latency: {e}")

    def tick_websocket_connection(self, mode: str, delta: int) -> None:
        """Update WebSocket connections. delta: +1 for connect, -1 for disconnect."""
        try:
            TICK_WEBSOCKET_CONNECTIONS.labels(mode=mode).inc(delta)
        except Exception as e:
            logger.warning(f"Failed to update websocket connections: {e}")

    def tick_set_aggregators(self, count: int) -> None:
        """Set active aggregators count."""
        try:
            TICK_AGGREGATORS_ACTIVE.set(count)
        except Exception as e:
            logger.warning(f"Failed to set aggregators count: {e}")

    def tick_redis_message(self, direction: str) -> None:
        """Record Redis message. direction: publish, subscribe."""
        try:
            TICK_REDIS_MESSAGES.labels(direction=direction).inc()
        except Exception as e:
            logger.warning(f"Failed to record redis message: {e}")

    def tick_set_callbacks(self, callback_type: str, count: int) -> None:
        """Set callback count. callback_type: trade, candle."""
        try:
            TICK_CALLBACKS_REGISTERED.labels(callback_type=callback_type).set(count)
        except Exception as e:
            logger.warning(f"Failed to set callbacks count: {e}")

    def tick_set_buffer_size(self, symbol: str, size: int) -> None:
        """Set tick buffer size for symbol."""
        try:
            TICK_BUFFER_SIZE.labels(symbol=symbol).set(size)
        except Exception as e:
            logger.warning(f"Failed to set buffer size: {e}")

    # -------------------------------------------------------------------------
    # Anomaly Detection Metrics
    # -------------------------------------------------------------------------

    def record_anomaly(self, anomaly_type: str, severity: str = "warning") -> None:
        """Record detected anomaly. severity: info, warning, critical"""
        try:
            ANOMALY_DETECTED.labels(anomaly_type=anomaly_type, severity=severity).inc()
        except Exception as e:
            logger.warning(f"Failed to record anomaly: {e}")

    def set_anomaly_score(self, metric_name: str, score: float) -> None:
        """Set current anomaly score for a metric."""
        try:
            ANOMALY_SCORE.labels(metric_name=metric_name).set(score)
        except Exception as e:
            logger.warning(f"Failed to set anomaly score: {e}")

    def fire_alert(self, alert_name: str, severity: str = "warning") -> None:
        """Record fired alert."""
        try:
            ALERT_FIRED.labels(alert_name=alert_name, severity=severity).inc()
        except Exception as e:
            logger.warning(f"Failed to record alert: {e}")

    def acknowledge_alert(self, alert_name: str) -> None:
        """Record acknowledged alert."""
        try:
            ALERT_ACKNOWLEDGED.labels(alert_name=alert_name).inc()
        except Exception as e:
            logger.warning(f"Failed to record alert acknowledgement: {e}")

    # -------------------------------------------------------------------------
    # Multi-Agent Metrics
    # -------------------------------------------------------------------------

    def consensus_loop_prevented(self, reason: str) -> None:
        """Record prevented consensus loop."""
        try:
            CONSENSUS_LOOP_PREVENTED.labels(reason=reason).inc()
        except Exception as e:
            logger.warning(f"Failed to record consensus loop prevention: {e}")

    def dlq_message(self, priority: str, agent_type: str) -> None:
        """Record DLQ message."""
        try:
            DLQ_MESSAGES.labels(priority=priority, agent_type=agent_type).inc()
        except Exception as e:
            logger.warning(f"Failed to record DLQ message: {e}")

    def dlq_retry(self, status: str) -> None:
        """Record DLQ retry. status: success, failed, expired"""
        try:
            DLQ_RETRIES.labels(status=status).inc()
        except Exception as e:
            logger.warning(f"Failed to record DLQ retry: {e}")

    # -------------------------------------------------------------------------
    # API Metrics
    # -------------------------------------------------------------------------

    def record_api_request(
        self, method: str, endpoint: str, status_code: int, duration: float
    ) -> None:
        """Record API request."""
        try:
            API_REQUEST_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).inc()
            API_REQUEST_DURATION.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record API request: {e}")

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def get_metrics_text(self) -> str:
        """Generate Prometheus metrics text."""
        return generate_latest(self._registry).decode("utf-8")

    def get_content_type(self) -> str:
        """Get content type for Prometheus metrics."""
        return CONTENT_TYPE_LATEST


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_metrics_instance: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get singleton metrics collector instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance


# Convenience alias
metrics = get_metrics()


# =============================================================================
# CONTEXT MANAGER FOR TIMING
# =============================================================================


class MetricsTimer:
    """
    Context manager for timing operations.

    Usage:
        with MetricsTimer("mcp_tool", tool="get_balance") as timer:
            result = await get_balance()
        # Automatically records duration
    """

    def __init__(self, metric_type: str, success: bool = True, **labels):
        self.metric_type = metric_type
        self.success = success
        self.labels = labels
        self.start_time: float | None = None
        self.duration: float | None = None

    def __enter__(self) -> "MetricsTimer":
        import time

        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        import time

        self.duration = time.perf_counter() - self.start_time

        # Update success based on exception
        if exc_type is not None:
            self.success = False

        # Record metric based on type
        m = get_metrics()
        if self.metric_type == "mcp_tool":
            m.mcp_tool_call(
                tool=self.labels.get("tool", "unknown"),
                success=self.success,
                duration=self.duration,
            )
        elif self.metric_type == "mcp_bridge":
            m.mcp_bridge_call(
                tool=self.labels.get("tool", "unknown"),
                success=self.success,
                duration=self.duration,
            )
        elif self.metric_type == "backfill":
            m.observe_backfill_duration(self.duration)
        elif self.metric_type == "api":
            m.record_api_request(
                method=self.labels.get("method", "GET"),
                endpoint=self.labels.get("endpoint", "/"),
                status_code=self.labels.get(
                    "status_code", 200 if self.success else 500
                ),
                duration=self.duration,
            )
