"""Simulated LLM Gateway.

Mirrors the responsibilities of the real Bifrost LLM Gateway:
provider selection, semantic-cache lookup, governance checks, automatic
fallback, and observability traces. All provider calls are mocked.
"""

from __future__ import annotations

import hashlib
import random
from typing import Optional

from .audit import AuditLog
from .mock_data import PROVIDERS
from .models import (
    GatewayRequest,
    GatewayResponse,
    ProviderConfig,
    ProviderName,
    RoutingStrategy,
)
from .security import PolicyEngine

# Approximation: we treat 4 characters as ~1 token for cost estimation.
_CHARS_PER_TOKEN = 4


def _estimate_tokens(prompt: str) -> int:
    return max(1, len(prompt) // _CHARS_PER_TOKEN)


def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()


def _pick_provider(
    strategy: RoutingStrategy, providers: list[ProviderConfig]
) -> Optional[ProviderConfig]:
    """Pick a healthy provider according to the routing strategy."""
    healthy = [p for p in providers if p.healthy]
    if not healthy:
        return None
    if strategy == "cheapest":
        return min(healthy, key=lambda p: p.cost_per_1k_tokens)
    if strategy == "fastest":
        return min(healthy, key=lambda p: p.avg_latency_ms)
    if strategy == "fallback":
        # Deterministic primary; the caller handles the swap on failure.
        return healthy[0]
    # "balanced" — minimize a simple cost*latency score.
    return min(healthy, key=lambda p: p.cost_per_1k_tokens * p.avg_latency_ms)


class LLMGateway:
    """Mock LLM Gateway with caching, routing, and governance."""

    def __init__(
        self,
        providers: Optional[list[ProviderConfig]] = None,
        policy: Optional[PolicyEngine] = None,
        audit: Optional[AuditLog] = None,
    ) -> None:
        # Copy so callers can flip `healthy` flags without mutating module state.
        self.providers = [p.model_copy() for p in (providers or PROVIDERS)]
        self.policy = policy or PolicyEngine()
        self.audit = audit or AuditLog()
        self.cache: dict[str, GatewayResponse] = {}

    def set_provider_health(self, name: ProviderName, healthy: bool) -> None:
        """Toggle a provider's health flag (for the failover demo)."""
        for provider in self.providers:
            if provider.name == name:
                provider.healthy = healthy

    def handle(self, request: GatewayRequest) -> GatewayResponse:
        """Run a request through the full simulated pipeline."""
        trace: list[str] = ["request received"]

        # 1. Governance — rate limit + budget.
        trace.append("policy check")
        if not self.policy.check_rate_limit(request.virtual_key):
            trace.append("blocked: rate limit exceeded")
            self.audit.record(
                "llm", request.virtual_key, "-", "blocked", note="rate limit"
            )
            return GatewayResponse(
                provider="openai",
                text="[blocked] rate limit exceeded for this virtual key.",
                latency_ms=0,
                cost_usd=0,
                trace=trace,
            )
        if not self.policy.check_budget(request.virtual_key):
            trace.append("blocked: budget exhausted")
            self.audit.record(
                "llm", request.virtual_key, "-", "blocked", note="budget"
            )
            return GatewayResponse(
                provider="openai",
                text="[blocked] budget exhausted for this virtual key.",
                latency_ms=0,
                cost_usd=0,
                trace=trace,
            )

        # 2. Semantic cache lookup (here: exact prompt hash).
        key = _cache_key(request.prompt)
        if key in self.cache:
            cached = self.cache[key].model_copy(
                update={"cache_hit": True, "trace": trace + ["cache hit"]}
            )
            self.audit.record(
                "llm",
                request.virtual_key,
                cached.provider,
                "cache_hit",
                latency_ms=cached.latency_ms,
                cost_usd=0.0,
                note="cached",
            )
            return cached

        # 3. Routing.
        provider = _pick_provider(request.strategy, self.providers)
        if provider is None:
            trace.append("no healthy provider")
            self.audit.record(
                "llm", request.virtual_key, "-", "blocked", note="no providers"
            )
            return GatewayResponse(
                provider="openai",
                text="[error] no healthy providers available.",
                latency_ms=0,
                cost_usd=0,
                trace=trace,
            )
        trace.append(f"route selected: {provider.name} ({request.strategy})")

        # 4. Call the provider (mocked); fall back if primary is unhealthy.
        fallback_used = False
        if not provider.healthy:
            trace.append(f"primary {provider.name} unavailable, falling back")
            fallback_used = True
            healthy = [p for p in self.providers if p.healthy and p.name != provider.name]
            if not healthy:
                self.audit.record(
                    "llm", request.virtual_key, provider.name, "blocked", note="no fallback"
                )
                return GatewayResponse(
                    provider=provider.name,
                    text="[error] no fallback provider available.",
                    latency_ms=0,
                    cost_usd=0,
                    fallback_used=True,
                    trace=trace,
                )
            provider = healthy[0]
            trace.append(f"fallback provider: {provider.name}")

        tokens = _estimate_tokens(request.prompt)
        # Tiny jitter so repeated runs look realistic in the UI.
        latency = provider.avg_latency_ms * random.uniform(0.85, 1.15)
        cost = (tokens / 1000) * provider.cost_per_1k_tokens
        text = (
            f"[{provider.name}] simulated reply to: "
            f"{request.prompt[:80]}{'…' if len(request.prompt) > 80 else ''}"
        )
        trace.append("provider called")

        response = GatewayResponse(
            provider=provider.name,
            text=text,
            latency_ms=round(latency, 1),
            cost_usd=round(cost, 6),
            fallback_used=fallback_used,
            trace=trace + ["response returned"],
        )

        # 5. Bookkeeping.
        self.cache[key] = response
        self.policy.record_request(request.virtual_key, response.cost_usd)
        decision = "fallback" if fallback_used else "allowed"
        self.audit.record(
            "llm",
            request.virtual_key,
            provider.name,
            decision,  # type: ignore[arg-type]
            latency_ms=response.latency_ms,
            cost_usd=response.cost_usd,
            note=request.strategy,
        )
        return response
