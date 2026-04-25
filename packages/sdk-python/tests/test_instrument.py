"""Tests for verum._instrument OTEL setup."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestSetupOtelNoEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

    def test_no_endpoint_returns_without_configuring(self) -> None:
        import verum._instrument as inst
        inst._setup_otel()
        self.assertFalse(inst._OTEL_CONFIGURED)


class TestSetupOtelIdempotent(unittest.TestCase):
    def setUp(self) -> None:
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = True

    def tearDown(self) -> None:
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False

    def test_already_configured_is_no_op(self) -> None:
        import verum._instrument as inst
        inst._setup_otel()
        self.assertTrue(inst._OTEL_CONFIGURED)


class TestSetupOtelMissingPackages(unittest.TestCase):
    """When endpoint is set but openinference/opentelemetry are absent."""

    def setUp(self) -> None:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False

    def tearDown(self) -> None:
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False

    def test_missing_packages_does_not_raise(self) -> None:
        """_setup_otel() must swallow ImportError and return gracefully."""
        import verum._instrument as inst

        # Force the openinference import to fail.
        with patch.dict(sys.modules, {"openinference": None,
                                       "openinference.instrumentation": None,
                                       "openinference.instrumentation.openai": None}):
            inst._setup_otel()
        # Should not be configured since packages weren't available.
        self.assertFalse(inst._OTEL_CONFIGURED)

    def test_warning_logged_when_packages_missing(self) -> None:
        import logging
        import verum._instrument as inst

        with self.assertLogs("verum._instrument", level=logging.WARNING) as log_ctx:
            with patch.dict(sys.modules, {"openinference": None,
                                           "openinference.instrumentation": None,
                                           "openinference.instrumentation.openai": None}):
                inst._setup_otel()

        self.assertTrue(any("OTEL_EXPORTER_OTLP_ENDPOINT" in msg for msg in log_ctx.output))


class TestSetupOtelSuccess(unittest.TestCase):
    """When all OTEL packages are present, setup should complete."""

    def setUp(self) -> None:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False

    def tearDown(self) -> None:
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        import verum._instrument as inst
        inst._OTEL_CONFIGURED = False

    def test_configures_tracer_provider_and_instrumentor(self) -> None:
        mock_instrumentor = MagicMock()
        mock_provider = MagicMock()
        mock_exporter = MagicMock()
        mock_processor = MagicMock()
        mock_otel_trace = MagicMock()

        mock_oi_mod = MagicMock()
        mock_oi_mod.OpenAIInstrumentor.return_value = mock_instrumentor

        mock_exporter_mod = MagicMock()
        mock_exporter_mod.OTLPSpanExporter.return_value = mock_exporter

        mock_sdk_trace_mod = MagicMock()
        mock_sdk_trace_mod.TracerProvider.return_value = mock_provider

        mock_sdk_export_mod = MagicMock()
        mock_sdk_export_mod.BatchSpanProcessor.return_value = mock_processor

        # `from opentelemetry import trace` reads sys.modules["opentelemetry"].trace,
        # not sys.modules["opentelemetry.trace"].  Wire the attribute explicitly.
        mock_opentelemetry_pkg = MagicMock()
        mock_opentelemetry_pkg.trace = mock_otel_trace

        mocked = {
            "openinference": MagicMock(),
            "openinference.instrumentation": MagicMock(),
            "openinference.instrumentation.openai": mock_oi_mod,
            "opentelemetry": mock_opentelemetry_pkg,
            "opentelemetry.exporter": MagicMock(),
            "opentelemetry.exporter.otlp": MagicMock(),
            "opentelemetry.exporter.otlp.proto": MagicMock(),
            "opentelemetry.exporter.otlp.proto.http": MagicMock(),
            "opentelemetry.exporter.otlp.proto.http.trace_exporter": mock_exporter_mod,
            "opentelemetry.sdk": MagicMock(),
            "opentelemetry.sdk.trace": mock_sdk_trace_mod,
            "opentelemetry.sdk.trace.export": mock_sdk_export_mod,
        }

        import verum._instrument as inst

        with patch.dict(sys.modules, mocked):
            inst._setup_otel()

        self.assertTrue(inst._OTEL_CONFIGURED)
        mock_provider.add_span_processor.assert_called_once_with(mock_processor)
        mock_otel_trace.set_tracer_provider.assert_called_once_with(mock_provider)
        mock_instrumentor.instrument.assert_called_once()
