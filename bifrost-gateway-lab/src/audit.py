"""In-session append-only log of real gateway calls."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, ChatResponse, Decision


class AuditLog:
    """In-memory log of chat calls and their outcomes."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record_response(
        self, response: ChatResponse, prompt_preview: str, note: str = ""
    ) -> AuditEvent:
        """Record a successful chat response."""
        return self._append(
            provider=response.provider,
            model=response.model,
            decision="ok",
            latency_ms=response.latency_ms,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            note=note,
            prompt_preview=prompt_preview,
        )

    def record_error(
        self, provider: str, model: str, error: str, prompt_preview: str
    ) -> AuditEvent:
        """Record a failed chat call."""
        return self._append(
            provider=provider,
            model=model,
            decision="error",
            latency_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            note=error[:200],
            prompt_preview=prompt_preview,
        )

    def _append(
        self,
        *,
        provider: str,
        model: str,
        decision: Decision,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        note: str,
        prompt_preview: str,
    ) -> AuditEvent:
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            provider=provider,  # type: ignore[arg-type]
            model=model,
            decision=decision,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            note=note,
            prompt_preview=prompt_preview,
        )
        self._events.append(event)
        return event

    def events(self) -> list[AuditEvent]:
        """Newest events first, for display."""
        return list(reversed(self._events))

    def clear(self) -> None:
        self._events.clear()
