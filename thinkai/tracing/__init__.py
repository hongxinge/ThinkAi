"""链路追踪模块 - 提供可观测性支持"""
import json
import uuid
import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("thinkai.tracing")

_current_span: ContextVar[Optional["TraceSpan"]] = ContextVar(
    "current_span", default=None
)


class TraceSpan(BaseModel):
    """追踪跨度"""

    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: Optional[str] = None
    name: str
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    end_time: Optional[datetime] = None
    status: str = "started"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def finish(self, status: str = "completed") -> None:
        self.end_time = datetime.now(timezone.utc)
        self.status = status

    def add_event(self, name: str, **attrs: Any) -> None:
        event: Dict[str, Any] = {
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if attrs:
            event["attributes"] = attrs
        self.events.append(event)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class Tracer:
    """追踪器 - 管理追踪跨度"""

    def __init__(self) -> None:
        self._spans: List[TraceSpan] = []
        self._exporters: List["BaseTraceExporter"] = []

    def add_exporter(self, exporter: "BaseTraceExporter") -> None:
        self._exporters.append(exporter)

    def remove_exporter(self, exporter: "BaseTraceExporter") -> None:
        if exporter in self._exporters:
            self._exporters.remove(exporter)

    def start_span(
        self,
        name: str,
        parent: Optional[TraceSpan] = None,
        **attributes: Any,
    ) -> TraceSpan:
        parent_id: Optional[str] = None
        trace_id = uuid.uuid4().hex

        if parent is not None:
            parent_id = parent.span_id
            trace_id = parent.trace_id
        else:
            current = _current_span.get()
            if current is not None:
                parent_id = current.span_id
                trace_id = current.trace_id

        span = TraceSpan(
            name=name,
            parent_id=parent_id,
            trace_id=trace_id,
            attributes=attributes,
        )
        self._spans.append(span)
        return span

    def get_current_span(self) -> Optional[TraceSpan]:
        return _current_span.get()

    def finish_span(self, span: TraceSpan, status: str = "completed") -> None:
        span.finish(status)
        for exporter in self._exporters:
            try:
                exporter.export(span)
            except Exception as exc:
                logger.warning("Exporter %s failed: %s", type(exporter).__name__, exc)

    @asynccontextmanager
    async def trace(self, name: str, **attributes: Any):
        span = self.start_span(name, **attributes)
        token = _current_span.set(span)
        try:
            yield span
            self.finish_span(span, status="completed")
        except Exception:
            self.finish_span(span, status="error")
            raise
        finally:
            _current_span.reset(token)

    def clear(self) -> None:
        self._spans.clear()

    @property
    def spans(self) -> List[TraceSpan]:
        return list(self._spans)


class BaseTraceExporter(ABC):
    """追踪导出器基类"""

    @abstractmethod
    def export(self, span: TraceSpan) -> None:
        pass


class ConsoleTraceExporter(BaseTraceExporter):
    """控制台追踪导出器 - 用于调试"""

    def export(self, span: TraceSpan) -> None:
        duration = f"{span.duration_ms:.2f}ms" if span.duration_ms is not None else "N/A"
        indent = "  " if span.parent_id else ""
        print(
            f"{indent}[TRACE] {span.name} | "
            f"status={span.status} | "
            f"duration={duration} | "
            f"trace_id={span.trace_id[:8]}... | "
            f"span_id={span.span_id[:8]}..."
        )
        if span.attributes:
            for key, value in span.attributes.items():
                print(f"{indent}  attr: {key}={value}")
        for event in span.events:
            ts = event.get("timestamp", "")
            evt_name = event.get("name", "")
            evt_attrs = event.get("attributes", {})
            attr_str = f" {evt_attrs}" if evt_attrs else ""
            print(f"{indent}  event: {evt_name} @ {ts}{attr_str}")


class JSONTraceExporter(BaseTraceExporter):
    """JSON文件追踪导出器"""

    def __init__(self, output_file: str = "traces.json") -> None:
        self.output_file = output_file

    def export(self, span: TraceSpan) -> None:
        record = span.model_dump(mode="json")
        record["duration_ms"] = span.duration_ms
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.warning("JSON export failed: %s", exc)


class TraceCallback:
    """追踪回调 - 集成Agent生命周期钩子"""

    def __init__(self, tracer: Optional[Tracer] = None) -> None:
        self._tracer = tracer or get_tracer()
        self._active_spans: Dict[str, TraceSpan] = {}

    def on_start(self, task: str) -> None:
        span = self._tracer.start_span("agent_run", task=task)
        self._active_spans[span.span_id] = span
        span.add_event("agent_started", task=task)

    def on_tool_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        current = self._tracer.get_current_span()
        parent = current or self._get_last_active_span()
        span = self._tracer.start_span(
            f"tool_call:{tool_name}", parent=parent, tool_name=tool_name, args=args
        )
        self._active_spans[span.span_id] = span
        if current:
            current.add_event("tool_call", tool_name=tool_name)

    def on_tool_result(self, tool_name: str, result: str) -> None:
        for span in reversed(list(self._active_spans.values())):
            if span.name == f"tool_call:{tool_name}" and span.status == "started":
                span.set_attribute("result", result)
                self._tracer.finish_span(span)
                break

    def on_finish(self, result: str) -> None:
        for span in reversed(list(self._active_spans.values())):
            if span.status == "started":
                span.set_attribute("result", result)
                self._tracer.finish_span(span)

    def on_error(self, error: Exception) -> None:
        for span in reversed(list(self._active_spans.values())):
            if span.status == "started":
                span.add_event("error", message=str(error))
                self._tracer.finish_span(span, status="error")

    def _get_last_active_span(self) -> Optional[TraceSpan]:
        for span in reversed(list(self._active_spans.values())):
            if span.status == "started":
                return span
        return None


tracer = Tracer()


def get_tracer() -> Tracer:
    return tracer
