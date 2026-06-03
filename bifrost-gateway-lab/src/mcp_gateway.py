"""Simulated MCP Gateway.

Mirrors the real Bifrost MCP Gateway: tool discovery, role-based access
control, risk-aware execution, and an audit trail. Tool execution is
mocked and never touches the network.
"""

from __future__ import annotations

from typing import Optional

from .audit import AuditLog
from .mock_data import ROLE_TOOL_ALLOWLIST, TOOLS
from .models import AgentRole, MCPRequest, MCPResponse, MCPTool, ToolName


def _run_tool(tool: ToolName, arguments: dict) -> str:
    """Mock the side-effect of each tool. No real I/O happens here."""
    if tool == "calculator":
        expression = str(arguments.get("expression", "1+1"))
        return f"calculator → {expression} = (simulated)"
    if tool == "weather":
        city = arguments.get("city", "Bengaluru")
        return f"weather → {city}: 27°C, light clouds (simulated)"
    if tool == "company_docs_search":
        query = arguments.get("query", "onboarding")
        return f"company_docs_search → top match for '{query}' (simulated)"
    if tool == "ticket_creator":
        title = arguments.get("title", "New ticket")
        return f"ticket_creator → created ticket '{title}' #1234 (simulated)"
    return "unknown tool"


class MCPGateway:
    """Mock MCP Gateway with discovery, RBAC, and audit."""

    def __init__(self, audit: Optional[AuditLog] = None) -> None:
        self.tools: list[MCPTool] = list(TOOLS)
        self.audit = audit or AuditLog()

    def discover(self, role: AgentRole) -> list[MCPTool]:
        """Return only the tools that this role is allowed to see."""
        allowed = ROLE_TOOL_ALLOWLIST[role]
        return [tool for tool in self.tools if tool.name in allowed]

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Authenticate, authorize, risk-check, then execute a tool call."""
        trace: list[str] = [f"agent request: {request.agent_role} → {request.tool}"]

        # 1. AuthN — pretend the caller already presented a valid token.
        trace.append("authN: token verified (simulated)")

        # 2. AuthZ — role-based allowlist.
        allowed_tools = ROLE_TOOL_ALLOWLIST[request.agent_role]
        if request.tool not in allowed_tools:
            trace.append(f"authZ: blocked, {request.agent_role} cannot use {request.tool}")
            self.audit.record(
                "mcp",
                request.agent_role,
                request.tool,
                "blocked",
                note="role not permitted",
            )
            return MCPResponse(
                tool=request.tool,
                allowed=False,
                reason=f"{request.agent_role} is not permitted to use {request.tool}.",
                trace=trace,
            )

        # 3. Risk check — high-risk tools require admin.
        tool_meta = next(t for t in self.tools if t.name == request.tool)
        trace.append(f"risk check: tool risk = {tool_meta.risk}")
        if tool_meta.risk == "high" and request.agent_role != "admin_agent":
            trace.append("risk check: blocked, high-risk tool requires admin")
            self.audit.record(
                "mcp",
                request.agent_role,
                request.tool,
                "blocked",
                note="high-risk tool",
            )
            return MCPResponse(
                tool=request.tool,
                allowed=False,
                reason="High-risk tool requires admin role.",
                trace=trace,
            )

        # 4. Execution (mocked).
        output = _run_tool(request.tool, request.arguments)
        trace.append("tool execution: success (simulated)")
        trace.append("audit event recorded")
        self.audit.record(
            "mcp",
            request.agent_role,
            request.tool,
            "allowed",
            note=f"risk={tool_meta.risk}",
        )
        return MCPResponse(tool=request.tool, allowed=True, output=output, trace=trace)
