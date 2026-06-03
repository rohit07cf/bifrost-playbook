"""Lightweight simulation of Bifrost governance: rate limits and budgets.

The real Bifrost gateway enforces these policies centrally for every
caller. Here we keep tiny in-memory counters keyed by virtual key so the
Streamlit UI can demonstrate the same shape of behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Per-virtual-key limits used by the demo. Kept small so the UI can hit
# them quickly without spamming the user.
RATE_LIMIT_PER_MIN = 5
BUDGET_LIMIT_USD = 0.05


@dataclass
class UsageCounters:
    """Counters tracked per virtual key for the current session."""

    requests_this_minute: int = 0
    spend_usd: float = 0.0


@dataclass
class PolicyEngine:
    """In-memory policy engine for the simulated gateway."""

    counters: dict[str, UsageCounters] = field(default_factory=dict)

    def _bucket(self, virtual_key: str) -> UsageCounters:
        return self.counters.setdefault(virtual_key, UsageCounters())

    def check_rate_limit(self, virtual_key: str) -> bool:
        """Return True when the caller is still under the rate limit."""
        return self._bucket(virtual_key).requests_this_minute < RATE_LIMIT_PER_MIN

    def check_budget(self, virtual_key: str) -> bool:
        """Return True when the caller still has budget remaining."""
        return self._bucket(virtual_key).spend_usd < BUDGET_LIMIT_USD

    def record_request(self, virtual_key: str, cost_usd: float) -> None:
        """Record a successful request against the caller's quota."""
        bucket = self._bucket(virtual_key)
        bucket.requests_this_minute += 1
        bucket.spend_usd += cost_usd

    def reset(self) -> None:
        """Clear all counters — useful for the Streamlit reset button."""
        self.counters.clear()
