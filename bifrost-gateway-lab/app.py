"""Streamlit UI for bifrost-gateway-lab.

A small, beginner-friendly walkthrough of how an AI gateway like
Bifrost routes LLM calls and governs MCP tool access. All behaviour is
simulated locally — no real provider keys are required.
"""

from __future__ import annotations

import streamlit as st

from src.audit import AuditLog
from src.llm_gateway import LLMGateway
from src.mcp_gateway import MCPGateway
from src.mock_data import PROVIDERS, ROLE_TOOL_ALLOWLIST, TOOLS
from src.models import GatewayRequest, MCPRequest
from src.security import BUDGET_LIMIT_USD, RATE_LIMIT_PER_MIN, PolicyEngine

st.set_page_config(page_title="bifrost-gateway-lab", page_icon="🛰️", layout="wide")


# ---------------------------------------------------------------------------
# Session state — shared across pages so the audit log persists.
# ---------------------------------------------------------------------------
def _init_state() -> None:
    if "audit" not in st.session_state:
        st.session_state.audit = AuditLog()
    if "policy" not in st.session_state:
        st.session_state.policy = PolicyEngine()
    if "llm" not in st.session_state:
        st.session_state.llm = LLMGateway(
            policy=st.session_state.policy, audit=st.session_state.audit
        )
    if "mcp" not in st.session_state:
        st.session_state.mcp = MCPGateway(audit=st.session_state.audit)


_init_state()


# ---------------------------------------------------------------------------
# Page renderers.
# ---------------------------------------------------------------------------
def page_home() -> None:
    st.title("bifrost-gateway-lab")
    st.caption("A minimalist, local simulation of the Bifrost AI Gateway.")

    st.subheader("What is an AI Gateway? (ELI10)")
    st.markdown(
        """
An AI Gateway is like a **smart switchboard** sitting between your app
and every AI service it needs.

Instead of your app talking to OpenAI, Anthropic, Gemini, and a pile of
tools directly, it talks to **one** gateway. The gateway:

- picks the best provider,
- enforces budgets and rate limits,
- retries or falls back when something breaks,
- caches repeated answers, and
- writes everything down in an audit log.

Bifrost ships **two** gateways: an **LLM Gateway** for model calls and
an **MCP Gateway** for agent tool calls.
        """
    )

    st.subheader("Where Bifrost sits")
    st.code(
        """
            ┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
            │   Your App   │ ───▶  │  Bifrost Gateway │ ───▶  │  LLM Providers   │
            │  / AI Agent  │       │  (LLM + MCP)     │       │  & MCP Tools     │
            └──────────────┘       └──────────────────┘       └──────────────────┘
                                          │
                                          ▼
                                  Routing • Caching
                                  Budgets • Failover
                                  RBAC    • Audit log
        """,
        language="text",
    )

    st.info(
        "This project is an **educational simulation**, not an official "
        "Bifrost integration. See the README for links to the real docs."
    )


def page_llm_demo() -> None:
    st.title("LLM Gateway Demo")
    st.caption("See how Bifrost picks a provider, caches results, and falls back on failure.")

    col_in, col_cfg = st.columns([2, 1])
    with col_in:
        prompt = st.text_area(
            "Prompt",
            value="Summarize the value of an AI gateway in one sentence.",
            height=110,
        )
        strategy = st.selectbox(
            "Routing strategy",
            options=["cheapest", "fastest", "fallback", "balanced"],
            index=3,
        )
        virtual_key = st.text_input("Virtual key", value="vk_demo_default")

    with col_cfg:
        st.markdown("**Provider health**")
        st.caption("Toggle a provider off to see fallback in action.")
        for provider in st.session_state.llm.providers:
            new_state = st.checkbox(
                f"{provider.name} healthy",
                value=provider.healthy,
                key=f"hc_{provider.name}",
            )
            st.session_state.llm.set_provider_health(provider.name, new_state)

    if st.button("Send through gateway", type="primary"):
        request = GatewayRequest(prompt=prompt, strategy=strategy, virtual_key=virtual_key)
        response = st.session_state.llm.handle(request)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Provider", response.provider)
        c2.metric("Latency", f"{response.latency_ms:.0f} ms")
        c3.metric("Cost", f"${response.cost_usd:.5f}")
        c4.metric("Cache hit", "yes" if response.cache_hit else "no")

        if response.fallback_used:
            st.warning("Primary provider was unhealthy — Bifrost fell back automatically.")

        st.markdown("**Response**")
        st.code(response.text, language="text")

        st.markdown("**Trace**")
        st.code(" → ".join(response.trace), language="text")


def page_mcp_demo() -> None:
    st.title("MCP Gateway Demo")
    st.caption("See how Bifrost governs which tools each agent can call.")

    st.markdown(
        """
**MCP in one line:** MCP is a standard way for AI agents to call
**tools** (search, ticketing, calculators, …). The MCP Gateway decides
**who** gets to call **what**, and writes it all down.
        """
    )

    role = st.selectbox(
        "Agent role",
        options=["intern_agent", "engineer_agent", "admin_agent"],
        index=1,
    )

    available = st.session_state.mcp.discover(role)  # type: ignore[arg-type]
    st.markdown("**Tools discovered for this role**")
    if available:
        for tool in available:
            st.write(f"- `{tool.name}` — {tool.description}  _(risk: {tool.risk})_")
    else:
        st.write("_no tools available_")

    st.divider()
    tool_choice = st.selectbox(
        "Try invoking a tool",
        options=[t.name for t in TOOLS],
    )

    arg_help = {
        "calculator": ("expression", "2 * (3 + 4)"),
        "weather": ("city", "Bengaluru"),
        "company_docs_search": ("query", "onboarding checklist"),
        "ticket_creator": ("title", "Database is down"),
    }
    key, default = arg_help[tool_choice]
    arg_value = st.text_input(f"Argument: {key}", value=default)

    if st.button("Invoke tool", type="primary"):
        request = MCPRequest(
            agent_role=role,  # type: ignore[arg-type]
            tool=tool_choice,  # type: ignore[arg-type]
            arguments={key: arg_value},
        )
        response = st.session_state.mcp.handle(request)

        if response.allowed:
            st.success("Allowed by the MCP Gateway.")
            st.code(response.output or "", language="text")
        else:
            st.error(f"Blocked: {response.reason}")

        st.markdown("**Trace**")
        st.code(" → ".join(response.trace), language="text")


def page_compare() -> None:
    st.title("LLM Gateway vs MCP Gateway")
    st.caption("Two gateways, two jobs.")

    st.table(
        {
            "Concern": [
                "What it routes",
                "Main goal",
                "Key controls",
                "Typical risk",
                "Observability",
            ],
            "LLM Gateway": [
                "Model calls (OpenAI, Anthropic, Gemini, Bedrock, …)",
                "Reliable, cheap, fast model access",
                "Routing, caching, fallback, budgets, rate limits",
                "Latency spikes, runaway cost, provider outages",
                "Cost & latency per provider, cache hit rate",
            ],
            "MCP Gateway": [
                "Tool calls from AI agents (MCP servers & tools)",
                "Safe, governed tool access",
                "Tool discovery, RBAC, risk checks, audit",
                "Wrong tool used, data exfiltration, prompt injection",
                "Who called what, when, and with what result",
            ],
        }
    )

    st.subheader("When to use each")
    st.markdown(
        """
- Use the **LLM Gateway** when many apps or teams share many model
  providers and you need **one** place to control cost, latency, and
  reliability.
- Use the **MCP Gateway** when AI agents start touching **real
  systems** (tickets, docs, internal APIs) and you need governance,
  permissions, and an audit trail.
- In production you usually want **both**.
        """
    )


def page_security() -> None:
    st.title("Security & Governance")
    st.caption("The guardrails that make a gateway production-grade.")

    items = [
        ("Rate limiting", "Cap requests per key per minute so one app can't drown the others."),
        ("Virtual keys", "Issue per-team or per-app keys instead of sharing raw provider keys."),
        ("Budget control", "Stop spending when a key, team, or workload hits its cap."),
        ("Provider failover", "If OpenAI is down, automatically route to Anthropic or Bedrock."),
        ("Tool allowlist", "Only let each agent role see and call approved MCP tools."),
        ("Audit logs", "Record every request, decision, and tool call for later review."),
        ("SSRF risk", "Stop tools from being tricked into calling internal URLs they shouldn't."),
        (
            "Prompt injection risk",
            "Treat tool inputs and outputs as untrusted — never let them silently elevate privileges.",
        ),
    ]
    for title, desc in items:
        st.markdown(f"**{title}** — {desc}")

    st.divider()
    st.markdown(
        f"**Demo limits in this lab:** {RATE_LIMIT_PER_MIN} requests/min per virtual key, "
        f"${BUDGET_LIMIT_USD:.2f} budget per virtual key."
    )
    if st.button("Reset all counters"):
        st.session_state.policy.reset()
        st.success("Policy counters cleared.")


def page_audit() -> None:
    st.title("Live Audit Log")
    st.caption("Every simulated LLM and MCP event lands here.")

    events = st.session_state.audit.events()
    if not events:
        st.write("_No events yet. Try the LLM or MCP demo pages first._")
        return

    rows = [
        {
            "time": event.timestamp.strftime("%H:%M:%S"),
            "type": event.event_type,
            "actor": event.actor,
            "target": event.target,
            "decision": event.decision,
            "latency_ms": round(event.latency_ms, 1),
            "cost_usd": round(event.cost_usd, 5),
            "note": event.note,
        }
        for event in events
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if st.button("Clear audit log"):
        st.session_state.audit.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Sidebar navigation.
# ---------------------------------------------------------------------------
PAGES = {
    "Home": page_home,
    "LLM Gateway Demo": page_llm_demo,
    "MCP Gateway Demo": page_mcp_demo,
    "LLM vs MCP": page_compare,
    "Security & Governance": page_security,
    "Live Audit Log": page_audit,
}

with st.sidebar:
    st.markdown("### bifrost-gateway-lab")
    choice = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption(f"Providers loaded: {len(PROVIDERS)}")
    st.caption(f"MCP tools loaded: {len(TOOLS)}")
    st.caption(f"Roles: {len(ROLE_TOOL_ALLOWLIST)}")

PAGES[choice]()
