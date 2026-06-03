"""Simple audit log used by both the LLM and MCP gateway simulations."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, Decision


class AuditLog:
    """In-memory append-only log of gateway decisions."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(
        self,
        event_type: str,
        actor: str,
        target: str,
        decision: Decision,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        note: str = "",
    ) -> AuditEvent:
        """Append a new audit event and return it."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,  # type: ignore[arg-type]
            actor=actor,
            target=target,
            decision=decision,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            note=note,
        )
        self._events.append(event)
        return event

    def events(self) -> list[AuditEvent]:
        """Return events newest-first for display."""
        return list(reversed(self._events))

    def clear(self) -> None:
        self._events.clear()
