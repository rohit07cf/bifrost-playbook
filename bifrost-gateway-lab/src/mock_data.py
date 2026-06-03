"""Static mock data: providers, tools, and access-control rules.

Numbers are illustrative and chosen so the demo scenarios are easy to
reason about (e.g. Gemini is cheapest, OpenAI is fastest, Bedrock is the
slow-but-cheap fallback).
"""

from __future__ import annotations

from .models import AgentRole, MCPTool, ProviderConfig, ToolName

PROVIDERS: list[ProviderConfig] = [
    ProviderConfig(name="openai", cost_per_1k_tokens=0.010, avg_latency_ms=320, healthy=True),
    ProviderConfig(name="anthropic", cost_per_1k_tokens=0.012, avg_latency_ms=380, healthy=True),
    ProviderConfig(name="gemini", cost_per_1k_tokens=0.004, avg_latency_ms=450, healthy=True),
    ProviderConfig(name="bedrock", cost_per_1k_tokens=0.006, avg_latency_ms=600, healthy=True),
]

TOOLS: list[MCPTool] = [
    MCPTool(name="calculator", description="Evaluate basic arithmetic.", risk="low"),
    MCPTool(name="weather", description="Look up a city's weather.", risk="low"),
    MCPTool(
        name="company_docs_search",
        description="Semantic search over internal documents.",
        risk="medium",
    ),
    MCPTool(
        name="ticket_creator",
        description="Create a ticket in the internal ticketing system.",
        risk="high",
    ),
]

# Role-based access control: which tools each agent role may invoke.
ROLE_TOOL_ALLOWLIST: dict[AgentRole, set[ToolName]] = {
    "intern_agent": {"calculator", "weather"},
    "engineer_agent": {"calculator", "weather", "company_docs_search"},
    "admin_agent": {"calculator", "weather", "company_docs_search", "ticket_creator"},
}
