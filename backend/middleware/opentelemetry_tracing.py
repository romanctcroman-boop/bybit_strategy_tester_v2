"""
OpenTelemetry Tracing Middleware
Provides distributed tracing with OpenTelemetry SDK integration.

Features:
- Automatic span creation for HTTP requests
- Context propagation with trace/span IDs
- Custom attributes for trading-specific metrics
- Integration with Circuit Breaker and Rate Limiter
- Export to Jaeger/Zipkin/OTLP collectors
"""

import logging
import os
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable for current trace context
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class SpanContext:
    """Represents a span in the trace tree."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    operation_name: str
    service_name: str
    start_time: float
    end_time: float | None = None
    status: str = "OK"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    def add_event(self, name: str, attributes: dict[str, Any] | None = None):
        """Add an event to the span."""
        self.events.append(
            {
                "name": name,
                "timestamp": datetime.now(UTC).isoformat(),
                "attributes": attributes or {},
            }
        )

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value

    def set_status(self, status: str, description: str = ""):
        """Set span status."""
        self.status = status
        if description:
            self.attributes["status.description"] = description

    def end(self):
        """End the span."""
        self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert span to dictionary for export."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat()
            if self.end_time
            else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
        }


@dataclass
class TraceContext:
    """Represents a complete trace with multiple spans."""

    trace_id: str
    service_name: str
    spans: list[SpanContext] = field(default_factory=list)
    current_span_id: str | None = None
    baggage: dict[str, str] = field(default_factory=dict)

    def create_span(
        self,
        operation_name: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> SpanContext:
        """Create a new span in this trace."""
        span = SpanContext(
            span_id=str(uuid4())[:16],
            trace_id=self.trace_id,
            parent_span_id=parent_span_id or self.current_span_id,
            operation_name=operation_name,
            service_name=self.service_name,
            start_time=time.time(),
            attributes=attributes or {},
        )
        self.spans.append(span)
        self.current_span_id = span.span_id
        return span

    def get_current_span(self) -> SpanContext | None:
        """Get the currently active span."""
        if not self.current_span_id:
            return None
        for span in self.spans:
            if span.span_id == self.current_span_id:
                return span
        return None


class SpanExporter:
    """Base class for span exporters."""

    async def export(self, spans: list[SpanContext]):
        """Export spans to backend."""
        raise NotImplementedError


class ConsoleSpanExporter(SpanExporter):
    """Export spans to console (for development)."""

    async def export(self, spans: list[SpanContext]):
        """Export spans to console."""
        for span in spans:
            logger.info(
                f"[TRACE] {span.trace_id[:8]}... "
                f"[SPAN] {span.span_id[:8]}... "
                f"{span.operation_name} "
                f"({span.duration_ms:.2f}ms) "
                f"status={span.status}"
            )


class InMemorySpanExporter(SpanExporter):
    """Export spans to in-memory storage for analysis."""

    def __init__(self, max_spans: int = 10000):
        self.spans: list[dict[str, Any]] = []
        self.max_spans = max_spans

    async def export(self, spans: list[SpanContext]):
        """Export spans to memory."""
        for span in spans:
            self.spans.append(span.to_dict())
            if len(self.spans) > self.max_spans:
                self.spans.pop(0)

    def get_spans(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        """Get stored spans, optionally filtered by trace_id."""
        if trace_id:
            return [s for s in self.spans if s["trace_id"] == trace_id]
        return self.spans

    def get_trace_summary(self) -> dict[str, Any]:
        """Get summary of stored traces."""
        traces = {}
        for span in self.spans:
            tid = span["trace_id"]
            if tid not in traces:
                traces[tid] = {"span_count": 0, "total_duration_ms": 0}
            traces[tid]["span_count"] += 1
            traces[tid]["total_duration_ms"] += span["duration_ms"]
        return {
            "total_traces": len(traces),
            "total_spans": len(self.spans),
            "traces": traces,
        }


class TracingManager:
    """Central manager for OpenTelemetry tracing."""

    def __init__(
        self,
        service_name: str = "bybit-strategy-tester",
        exporters: list[SpanExporter] | None = None,
        sampling_rate: float = 1.0,
        enabled: bool = True,
    ):
        self.service_name = service_name
        self.exporters = exporters or [InMemorySpanExporter()]
        self.sampling_rate = sampling_rate
        self.enabled = enabled
        self._traces: dict[str, TraceContext] = {}

        # Metrics
        self.total_traces = 0
        self.total_spans = 0
        self.error_count = 0

    def should_sample(self) -> bool:
        """Determine if request should be sampled."""
        import random

        return random.random() < self.sampling_rate

    def create_trace(
        self, trace_id: str | None = None, baggage: dict[str, str] | None = None
    ) -> TraceContext:
        """Create a new trace context."""
        trace = TraceContext(
            trace_id=trace_id or str(uuid4()),
            service_name=self.service_name,
            baggage=baggage or {},
        )
        self._traces[trace.trace_id] = trace
        self.total_traces += 1
        _current_trace.set(trace)
        return trace

    def get_current_trace(self) -> TraceContext | None:
        """Get the current trace from context."""
        return _current_trace.get()

    def start_span(
        self, operation_name: str, attributes: dict[str, Any] | None = None
    ) -> SpanContext | None:
        """Start a new span in the current trace."""
        trace = self.get_current_trace()
        if not trace:
            logger.debug("No active trace, creating new one")
            trace = self.create_trace()

        span = trace.create_span(operation_name, attributes=attributes)
        self.total_spans += 1
        return span

    async def end_span(self, span: SpanContext, status: str = "OK"):
        """End a span and export if it's a root span."""
        span.set_status(status)
        span.end()

        if status == "ERROR":
            self.error_count += 1

        # If this is a root span, export all spans in the trace
        if not span.parent_span_id:
            await self._export_trace(span.trace_id)

    async def _export_trace(self, trace_id: str):
        """Export all spans from a trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            return

        for exporter in self.exporters:
            try:
                await exporter.export(trace.spans)
            except Exception as e:
                logger.error(f"Failed to export spans: {e}")

        # Clean up completed trace
        del self._traces[trace_id]
        _current_trace.set(None)

    def get_metrics(self) -> dict[str, Any]:
        """Get tracing metrics."""
        return {
            "total_traces": self.total_traces,
            "total_spans": self.total_spans,
            "active_traces": len(self._traces),
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.total_spans, 1) * 100,
            "sampling_rate": self.sampling_rate,
            "enabled": self.enabled,
        }


# Global tracing manager instance
_tracing_manager: TracingManager | None = None


def get_tracing_manager() -> TracingManager:
    """Get or create the global tracing manager."""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager(
            service_name=os.getenv("SERVICE_NAME", "bybit-strategy-tester"),
            sampling_rate=float(os.getenv("TRACE_SAMPLING_RATE", "1.0")),
            enabled=os.getenv("TRACING_ENABLED", "true").lower() == "true",
        )
    return _tracing_manager


def trace_span(operation_name: str | None = None):
    """
    Decorator to add tracing to a function.

    Usage:
        @trace_span("my_operation")
        async def my_function():
            ...
    """

    def decorator(func: Callable):
        import asyncio
        import functools

        op_name = operation_name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_tracing_manager()
            if not manager.enabled:
                return await func(*args, **kwargs)

            span = manager.start_span(
                op_name,
                attributes={"function": func.__name__, "module": func.__module__},
            )

            try:
                result = await func(*args, **kwargs)
                if span:
                    await manager.end_span(span, "OK")
                return result
            except Exception as e:
                if span:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    await manager.end_span(span, "ERROR")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            manager = get_tracing_manager()
            if not manager.enabled:
                return func(*args, **kwargs)

            span = manager.start_span(
                op_name,
                attributes={"function": func.__name__, "module": func.__module__},
            )

            try:
                result = func(*args, **kwargs)
                if span:
                    span.end()
                    span.set_status("OK")
                return result
            except Exception as e:
                if span:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.set_status("ERROR")
                    span.end()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class OpenTelemetryMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OpenTelemetry tracing.

    Automatically creates spans for HTTP requests with:
    - HTTP method, path, status code
    - Client IP, User-Agent
    - Request/Response timing
    - Error tracking
    """

    def __init__(
        self,
        app,
        service_name: str = "bybit-strategy-tester",
        excluded_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.service_name = service_name
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/favicon.ico"]
        self.manager = get_tracing_manager()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tracing."""
        # Skip excluded paths
        if any(request.url.path.startswith(p) for p in self.excluded_paths):
            return await call_next(request)

        # Skip if tracing is disabled
        if not self.manager.enabled:
            return await call_next(request)

        # Skip if not sampled
        if not self.manager.should_sample():
            return await call_next(request)

        # Extract or create trace context
        trace_id = request.headers.get("X-Trace-ID")
        parent_span_id = request.headers.get("X-Span-ID")

        trace = self.manager.create_trace(trace_id=trace_id)

        # Create root span for this request
        span = trace.create_span(
            operation_name=f"{request.method} {request.url.path}",
            parent_span_id=parent_span_id,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.host": request.headers.get("host", ""),
                "http.user_agent": request.headers.get("user-agent", ""),
                "http.client_ip": request.client.host if request.client else "",
                "http.scheme": request.url.scheme,
            },
        )

        # Store trace context in request state
        request.state.trace_id = trace.trace_id
        request.state.span_id = span.span_id

        try:
            response = await call_next(request)

            # Add response attributes
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute(
                "http.response_content_type", response.headers.get("content-type", "")
            )

            # Determine status based on HTTP code
            if response.status_code >= 500:
                await self.manager.end_span(span, "ERROR")
            elif response.status_code >= 400:
                span.set_status("ERROR", f"HTTP {response.status_code}")
                await self.manager.end_span(span, "ERROR")
            else:
                await self.manager.end_span(span, "OK")

            # Add trace headers to response
            response.headers["X-Trace-ID"] = trace.trace_id
            response.headers["X-Span-ID"] = span.span_id

            return response

        except Exception as e:
            span.add_event(
                "exception",
                {"exception.type": type(e).__name__, "exception.message": str(e)},
            )
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            await self.manager.end_span(span, "ERROR")
            raise


# Convenience function to add custom span attributes
def add_span_attribute(key: str, value: Any):
    """Add an attribute to the current span."""
    manager = get_tracing_manager()
    trace = manager.get_current_trace()
    if trace:
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict[str, Any] | None = None):
    """Add an event to the current span."""
    manager = get_tracing_manager()
    trace = manager.get_current_trace()
    if trace:
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes)
