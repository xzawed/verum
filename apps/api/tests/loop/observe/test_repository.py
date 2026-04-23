"""Tests for observe repository. Requires a live DB (integration test)."""
from __future__ import annotations

import uuid
import pytest

from src.loop.observe.models import TraceRecord, SpanRecord
from src.db.models.traces import Trace


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


def test_trace_model_import():
    assert Trace.__tablename__ == "traces"


from src.loop.observe.repository import calculate_cost


def test_calculate_cost_known_model():
    # 1M input + 1M output of grok-2-1212 = 2.00 + 10.00 = 12.00
    pricing = {"input_per_1m_usd": 2.0, "output_per_1m_usd": 10.0}
    cost = calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        pricing=pricing,
    )
    assert abs(cost - 12.0) < 0.0001


def test_calculate_cost_none_for_no_pricing():
    cost = calculate_cost(input_tokens=500, output_tokens=300, pricing=None)
    assert cost is None
