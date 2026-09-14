"""Local OpenTelemetry exporter. No prompts, keys or model output in spans."""

import json
import threading
from functools import lru_cache
from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class JsonExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def export(self, spans):
        with self.lock, self.path.open("a", encoding="utf-8") as file:
            for span in spans:
                file.write(
                    json.dumps(
                        {
                            "name": span.name,
                            "trace_id": format(span.context.trace_id, "032x"),
                            "span_id": format(span.context.span_id, "016x"),
                            "parent_id": format(span.parent.span_id, "016x")
                            if span.parent
                            else None,
                            "duration_ms": (span.end_time - span.start_time) / 1e6,
                            "status": span.status.status_code.name,
                        }
                    )
                    + "\n"
                )
        return SpanExportResult.SUCCESS


@lru_cache
def tracer(runtime_dir):
    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(JsonExporter(Path(runtime_dir) / "traces.jsonl"))
    )
    return provider.get_tracer("diagnosis-agent")
