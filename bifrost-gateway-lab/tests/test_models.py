"""Schema-level tests — no network, no Bifrost required."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.audit import AuditLog
from src.models import AuditEvent, ChatResponse, ModelChoice


def _model() -> ModelChoice:
    return ModelChoice(
        label="OpenAI · gpt-4o-mini",
        provider="openai",
        bifrost_id="openai/gpt-4o-mini",
    )


def test_chat_response_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        ChatResponse(provider="openai", model="x", text="y", prompt_tokens=-1)


def test_audit_log_records_response_and_orders_newest_first() -> None:
    log = AuditLog()
    log.record_response(
        ChatResponse(
            provider="openai",
            model="openai/gpt-4o-mini",
            text="hi",
            prompt_tokens=3,
            completion_tokens=1,
            latency_ms=42.0,
        ),
        prompt_preview="first",
    )
    log.record_response(
        ChatResponse(
            provider="anthropic",
            model="anthropic/claude-3-5-haiku-20241022",
            text="hello",
            prompt_tokens=2,
            completion_tokens=1,
            latency_ms=55.0,
        ),
        prompt_preview="second",
    )
    events = log.events()
    assert len(events) == 2
    assert events[0].provider == "anthropic"
    assert events[1].provider == "openai"


def test_audit_log_records_errors() -> None:
    log = AuditLog()
    event = log.record_error(
        provider="openai",
        model="openai/gpt-4o-mini",
        error="429 rate limit",
        prompt_preview="hello",
    )
    assert event.decision == "error"
    assert "rate limit" in event.note


def test_audit_event_round_trips_through_pydantic() -> None:
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        provider="openai",
        model="openai/gpt-4o-mini",
        decision="ok",
        latency_ms=10.0,
        prompt_tokens=1,
        completion_tokens=1,
    )
    dumped = event.model_dump_json()
    assert AuditEvent.model_validate_json(dumped) == event
