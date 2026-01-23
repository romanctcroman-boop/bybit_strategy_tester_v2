"""
Distributed Tracing for Multi-Agent Interactions

Provides OpenTelemetry-style distributed tracing:
- Trace context propagation between agents
- Span creation and management
- Parent-child relationships
- Timing and metadata

Enables understanding of complex multi-agent workflows.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, AsyncGenerator

from loguru import logger


class SpanStatus(Enum):
    """Status of a span"""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class SpanKind(Enum):
    """Kind of span"""

    INTERNAL = "internal"
    CLIENT = "client"  # Outgoing request
    SERVER = "server"  # Incoming request
    PRODUCER = "producer"  # Message producer
    CONSUMER = "consumer"  # Message consumer


@dataclass
class SpanContext:
    """Context for trace propagation"""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "baggage": self.baggage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpanContext":
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            baggage=data.get("baggage", {}),
        )

    def to_header(self) -> str:
        """Convert to propagation header (W3C Trace Context format)"""
        return f"00-{self.trace_id}-{self.span_id}-01"

    @classmethod
    def from_header(cls, header: str) -> Optional["SpanContext"]:
        """Parse from propagation header"""
        try:
            parts = header.split("-")
            if len(parts) >= 3:
                return cls(
                    trace_id=parts[1],
                    span_id=parts[2],
                )
        except Exception:
            pass
        return None


@dataclass
class SpanEvent:
    """Event within a span"""

    name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A single span in a trace"""

    name: str
    context: SpanContext
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span"""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def set_status(self, status: SpanStatus, description: str = "") -> None:
        """Set span status"""
        self.status = status
        if description:
            self.attributes["status_description"] = description

    def end(self) -> None:
        """End the span"""
        self.end_time = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": [
                {
                    "name": e.name,
                    "timestamp": e.timestamp.isoformat(),
                    "attributes": e.attributes,
                }
                for e in self.events
            ],
        }


@dataclass
class Trace:
    """A complete trace with all spans"""

    trace_id: str
    spans: List[Span] = field(default_factory=list)
    root_span: Optional[Span] = None

    @property
    def duration_ms(self) -> float:
        """Total trace duration"""
        if self.root_span:
            return self.root_span.duration_ms
        if self.spans:
            start = min(s.start_time for s in self.spans)
            end = max(s.end_time or datetime.now(timezone.utc) for s in self.spans)
            return (end - start).total_seconds() * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }


class TraceExporter:
    """Base class for trace exporters"""

    async def export(self, spans: List[Span]) -> bool:
        """Export spans"""
        raise NotImplementedError

    async def shutdown(self) -> None:
        """Shutdown exporter"""
        pass


class ConsoleExporter(TraceExporter):
    """Export traces to console"""

    async def export(self, spans: List[Span]) -> bool:
        for span in spans:
            status_icon = (
                "✅"
                if span.status == SpanStatus.OK
                else "❌"
                if span.status == SpanStatus.ERROR
                else "⏳"
            )
            logger.info(
                f"{status_icon} [{span.context.trace_id[:8]}] {span.name} "
                f"({span.duration_ms:.1f}ms) {span.attributes}"
            )
        return True


class FileExporter(TraceExporter):
    """Export traces to JSON file"""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def export(self, spans: List[Span]) -> bool:
        try:
            existing = []
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.extend([s.to_dict() for s in spans])

            # Keep last 1000 spans
            existing = existing[-1000:]

            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)

            return True
        except Exception as e:
            logger.warning(f"Failed to export traces: {e}")
            return False


class DistributedTracer:
    """
    Distributed tracing for multi-agent systems

    Example:
        tracer = DistributedTracer()

        async with tracer.start_span("agent_request", kind=SpanKind.CLIENT) as span:
            span.set_attribute("agent_type", "deepseek")
            span.set_attribute("model", "deepseek-chat")

            # Do work...
            response = await agent.send_request(request)

            span.set_attribute("tokens_used", response.tokens)
            span.add_event("response_received")

        # Get trace data
        traces = tracer.get_recent_traces(limit=10)
    """

    def __init__(
        self,
        service_name: str = "ai-agent-system",
        exporters: Optional[List[TraceExporter]] = None,
        sample_rate: float = 1.0,
    ):
        """
        Initialize tracer

        Args:
            service_name: Name of the service
            exporters: List of trace exporters
            sample_rate: Sampling rate (0.0 to 1.0)
        """
        self.service_name = service_name
        self.exporters = exporters or [ConsoleExporter()]
        self.sample_rate = sample_rate

        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}
        self._current_context: Optional[SpanContext] = None

        # Statistics
        self.stats = {
            "traces_created": 0,
            "spans_created": 0,
            "spans_exported": 0,
            "errors": 0,
        }

        logger.info(f"🔍 DistributedTracer initialized for {service_name}")

    def _generate_id(self) -> str:
        """Generate unique ID"""
        return uuid.uuid4().hex[:16]

    def _should_sample(self) -> bool:
        """Check if we should sample this trace"""
        import random

        return random.random() < self.sample_rate

    def start_trace(self, name: str) -> SpanContext:
        """Start a new trace"""
        trace_id = self._generate_id()
        span_id = self._generate_id()

        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
        )

        self._traces[trace_id] = Trace(trace_id=trace_id)
        self.stats["traces_created"] += 1

        return context

    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_context: Optional[SpanContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Span, None]:
        """
        Start a new span (async context manager)

        Args:
            name: Span name
            kind: Span kind
            parent_context: Parent span context for linking
            attributes: Initial attributes
        """
        # Determine context
        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        elif self._current_context:
            trace_id = self._current_context.trace_id
            parent_span_id = self._current_context.span_id
        else:
            trace_id = self._generate_id()
            parent_span_id = None
            self._traces[trace_id] = Trace(trace_id=trace_id)
            self.stats["traces_created"] += 1

        span_id = self._generate_id()

        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )

        span = Span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {},
        )
        span.set_attribute("service.name", self.service_name)

        self._active_spans[span_id] = span
        self.stats["spans_created"] += 1

        # Set as current context
        previous_context = self._current_context
        self._current_context = context

        try:
            yield span
            if span.status == SpanStatus.UNSET:
                span.set_status(SpanStatus.OK)
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            self.stats["errors"] += 1
            raise
        finally:
            span.end()
            self._current_context = previous_context

            # Add to trace
            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span)
                if parent_span_id is None:
                    self._traces[trace_id].root_span = span

            # Remove from active
            self._active_spans.pop(span_id, None)

            # Export
            await self._export_span(span)

    @contextmanager
    def start_span_sync(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_context: Optional[SpanContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Start a new span (sync context manager)"""
        # Similar to async but without export
        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        elif self._current_context:
            trace_id = self._current_context.trace_id
            parent_span_id = self._current_context.span_id
        else:
            trace_id = self._generate_id()
            parent_span_id = None
            self._traces[trace_id] = Trace(trace_id=trace_id)

        span_id = self._generate_id()

        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )

        span = Span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {},
        )

        previous_context = self._current_context
        self._current_context = context

        try:
            yield span
            if span.status == SpanStatus.UNSET:
                span.set_status(SpanStatus.OK)
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            raise
        finally:
            span.end()
            self._current_context = previous_context

            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span)

    async def _export_span(self, span: Span) -> None:
        """Export span to all exporters"""
        for exporter in self.exporters:
            try:
                await exporter.export([span])
                self.stats["spans_exported"] += 1
            except Exception as e:
                logger.warning(f"Exporter failed: {e}")

    def get_current_context(self) -> Optional[SpanContext]:
        """Get current span context"""
        return self._current_context

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a complete trace"""
        return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 10) -> List[Trace]:
        """Get recent traces"""
        traces = list(self._traces.values())
        traces.sort(
            key=lambda t: t.spans[0].start_time
            if t.spans
            else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return traces[:limit]

    def get_active_spans(self) -> List[Span]:
        """Get currently active spans"""
        return list(self._active_spans.values())

    def cleanup(self, max_traces: int = 100) -> int:
        """Remove old traces, keep recent ones"""
        if len(self._traces) <= max_traces:
            return 0

        traces = list(self._traces.items())
        traces.sort(
            key=lambda t: t[1].spans[0].start_time
            if t[1].spans
            else datetime.min.replace(tzinfo=timezone.utc)
        )

        to_remove = len(traces) - max_traces
        for trace_id, _ in traces[:to_remove]:
            del self._traces[trace_id]

        return to_remove

    async def shutdown(self) -> None:
        """Shutdown tracer and exporters"""
        for exporter in self.exporters:
            await exporter.shutdown()

    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics"""
        return {
            **self.stats,
            "active_spans": len(self._active_spans),
            "stored_traces": len(self._traces),
        }


# Global tracer instance
_tracer: Optional[DistributedTracer] = None


def get_tracer() -> DistributedTracer:
    """Get or create global tracer"""
    global _tracer
    if _tracer is None:
        _tracer = DistributedTracer()
    return _tracer


__all__ = [
    "DistributedTracer",
    "Span",
    "SpanContext",
    "SpanStatus",
    "SpanKind",
    "SpanEvent",
    "Trace",
    "TraceExporter",
    "ConsoleExporter",
    "FileExporter",
    "get_tracer",
]
