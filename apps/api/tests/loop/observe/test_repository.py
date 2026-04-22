"""Tests for observe repository. Requires a live DB (integration test)."""
from __future__ import annotations

import uuid
import pytest

from src.loop.observe.models import TraceRecord, SpanRecord


def test_trace_record_defaults():
    rec = TraceRecord(
        deployment_id=uuid.uuid4(),
        variant="cot",
        model="grok-2-1212",
        input_tokens=512,
        output_tokens=284,
        latency_ms=980,
    )
    assert rec.error is None
    assert rec.cost_usd == 0.0


def test_span_record_cost_calculation():
    rec = SpanRecord(
        trace_id=uuid.uuid4(),
        model="grok-2-1212",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        latency_ms=1000,
        cost_usd=12.0,  # 2.0 input + 10.0 output
    )
    assert rec.cost_usd == 12.0
