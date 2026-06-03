"""Tests for the simulated MCP Gateway."""

from __future__ import annotations

from src.mcp_gateway import MCPGateway
from src.models import MCPRequest


def test_intern_can_use_calculator() -> None:
    gateway = MCPGateway()
    response = gateway.handle(
        MCPRequest(agent_role="intern_agent", tool="calculator", arguments={"expression": "1+1"})
    )
    assert response.allowed is True
    assert "calculator" in (response.output or "")


def test_intern_blocked_from_ticket_creator() -> None:
    gateway = MCPGateway()
    response = gateway.handle(
        MCPRequest(agent_role="intern_agent", tool="ticket_creator", arguments={"title": "x"})
    )
    assert response.allowed is False
    assert "not permitted" in (response.reason or "")


def test_engineer_can_search_company_docs() -> None:
    gateway = MCPGateway()
    response = gateway.handle(
        MCPRequest(
            agent_role="engineer_agent",
            tool="company_docs_search",
            arguments={"query": "onboarding"},
        )
    )
    assert response.allowed is True


def test_admin_can_create_ticket() -> None:
    gateway = MCPGateway()
    response = gateway.handle(
        MCPRequest(
            agent_role="admin_agent",
            tool="ticket_creator",
            arguments={"title": "Service down"},
        )
    )
    assert response.allowed is True
    assert "ticket_creator" in (response.output or "")


def test_discovery_filters_tools_by_role() -> None:
    gateway = MCPGateway()
    intern_tools = {tool.name for tool in gateway.discover("intern_agent")}
    admin_tools = {tool.name for tool in gateway.discover("admin_agent")}
    assert intern_tools == {"calculator", "weather"}
    assert "ticket_creator" in admin_tools
