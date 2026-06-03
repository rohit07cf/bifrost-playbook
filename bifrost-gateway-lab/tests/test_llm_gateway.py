"""Tests for the simulated LLM Gateway."""

from __future__ import annotations

from src.llm_gateway import LLMGateway
from src.models import GatewayRequest
from src.security import RATE_LIMIT_PER_MIN, PolicyEngine


def test_cheapest_strategy_picks_lowest_cost_provider() -> None:
    gateway = LLMGateway()
    response = gateway.handle(GatewayRequest(prompt="hi there", strategy="cheapest"))
    # Gemini is the cheapest provider in the mock dataset.
    assert response.provider == "gemini"
    assert response.cost_usd > 0


def test_fastest_strategy_picks_lowest_latency_provider() -> None:
    gateway = LLMGateway()
    response = gateway.handle(GatewayRequest(prompt="quick please", strategy="fastest"))
    assert response.provider == "openai"


def test_cache_hit_on_repeated_prompt() -> None:
    gateway = LLMGateway()
    prompt = "what is bifrost?"
    first = gateway.handle(GatewayRequest(prompt=prompt))
    second = gateway.handle(GatewayRequest(prompt=prompt))
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.provider == first.provider


def test_fallback_when_primary_provider_is_unhealthy() -> None:
    gateway = LLMGateway()
    gateway.set_provider_health("openai", False)
    response = gateway.handle(GatewayRequest(prompt="failover please", strategy="fastest"))
    # With OpenAI down, the next-fastest healthy provider should answer.
    assert response.provider != "openai"


def test_rate_limit_blocks_excess_requests() -> None:
    gateway = LLMGateway(policy=PolicyEngine())
    for i in range(RATE_LIMIT_PER_MIN):
        gateway.handle(GatewayRequest(prompt=f"prompt {i}"))
    blocked = gateway.handle(GatewayRequest(prompt="one too many"))
    assert "[blocked]" in blocked.text
