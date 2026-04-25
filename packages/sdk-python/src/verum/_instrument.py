"""OpenTelemetry OTLP setup for automatic LLM instrumentation."""
from __future__ import annotations

import logging
import os

_OTEL_CONFIGURED = False
_logger = logging.getLogger(__name__)


def _setup_otel() -> None:
    """Configure OpenTelemetry OTLP exporter for LLM tracing.

    Reads ``OTEL_EXPORTER_OTLP_ENDPOINT`` from environment. If not set,
    returns immediately without configuring anything.

    All imports are attempted lazily; if the optional ``openinference`` or
    ``opentelemetry`` packages are absent the function logs a warning and
    returns gracefully.

    This function is idempotent — subsequent calls are no-ops.
    """
    global _OTEL_CONFIGURED  # noqa: PLW0603

    if _OTEL_CONFIGURED:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        return

    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor  # type: ignore[import-untyped]
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-untyped]
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-untyped]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-untyped]
    except ImportError:
        _logger.warning(
            "Verum: OTEL_EXPORTER_OTLP_ENDPOINT is set but optional OTLP "
            "packages are not installed. Run: "
            "pip install 'verum[instrument]' to enable automatic tracing."
        )
        return

    try:
        provider = TracerProvider()
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        from opentelemetry import trace as otel_trace  # type: ignore[import-untyped]

        otel_trace.set_tracer_provider(provider)
        OpenAIInstrumentor().instrument()
        _OTEL_CONFIGURED = True
    except Exception:  # noqa: BLE001
        _logger.warning("Verum: failed to configure OpenTelemetry — continuing without tracing.")
