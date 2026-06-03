"""Pydantic v2 models for the simulated Bifrost gateway.

These shapes intentionally mirror the public concepts described in the
Bifrost docs (providers, routing, virtual keys, MCP tools, audit events)
but they hold mock data — no real network calls are made anywhere.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, NonNegativeFloat, PositiveFloat

RoutingStrategy = Literal["cheapest", "fastest", "fallback", "balanced"]
ProviderName = Literal["openai", "anthropic", "gemini", "bedrock"]
AgentRole = Literal["intern_agent", "engineer_agent", "admin_agent"]
ToolName = Literal["calculator", "weather", "company_docs_search", "ticket_creator"]
Decision = Literal["allowed", "blocked", "fallback", "cache_hit"]


class ProviderConfig(BaseModel):
    """Configuration describing one LLM provider behind the gateway."""

    name: ProviderName
    cost_per_1k_tokens: PositiveFloat
    avg_latency_ms: PositiveFloat
    healthy: bool = True


class GatewayRequest(BaseModel):
    """Incoming request to the simulated LLM Gateway."""

    prompt: str = Field(min_length=1)
    strategy: RoutingStrategy = "balanced"
    virtual_key: str = "vk_demo_default"


class GatewayResponse(BaseModel):
    """Result returned by the simulated LLM Gateway."""

    provider: ProviderName
    text: str
    latency_ms: NonNegativeFloat
    cost_usd: NonNegativeFloat
    cache_hit: bool = False
    fallback_used: bool = False
    trace: list[str] = Field(default_factory=list)


class MCPTool(BaseModel):
    """A tool exposed through the MCP Gateway."""

    name: ToolName
    description: str
    risk: Literal["low", "medium", "high"] = "low"


class MCPRequest(BaseModel):
    """An agent request to invoke an MCP tool."""

    agent_role: AgentRole
    tool: ToolName
    arguments: dict = Field(default_factory=dict)


class MCPResponse(BaseModel):
    """Result of an MCP tool invocation through the gateway."""

    tool: ToolName
    allowed: bool
    output: Optional[str] = None
    reason: Optional[str] = None
    trace: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """A single row in the live audit log."""

    timestamp: datetime
    event_type: Literal["llm", "mcp"]
    actor: str
    target: str
    decision: Decision
    latency_ms: NonNegativeFloat = 0.0
    cost_usd: NonNegativeFloat = 0.0
    note: str = ""
