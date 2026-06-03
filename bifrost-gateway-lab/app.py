"""Streamlit UI for bifrost-gateway-lab.

A small real-call demo of the Bifrost AI Gateway:
- Bifrost runs locally (auto-started via `npx -y @maximhq/bifrost`).
- Provider API keys (OpenAI, Anthropic) come from `.env`.
- The Streamlit app talks to Bifrost using the OpenAI Python SDK.
"""

from __future__ import annotations

import json

import streamlit as st

from src import bifrost_runtime, config, gateway_client
from src.audit import AuditLog
from src.models import BifrostStatus, ChatRequest

st.set_page_config(page_title="bifrost-gateway-lab", page_icon="🛰️", layout="wide")


# ---------------------------------------------------------------------------
# Session state.
# ---------------------------------------------------------------------------
def _init_state() -> None:
    if "audit" not in st.session_state:
        st.session_state.audit = AuditLog()
    cached = st.session_state.get("bifrost_status")
    # Recompute if absent, or if a redeploy left a stale BifrostStatus
    # from an older model revision in the session (Streamlit keeps
    # session objects across code reloads).
    if not isinstance(cached, BifrostStatus):
        st.session_state.bifrost_status = bifrost_runtime.ensure_running()


_init_state()


def _refresh_status() -> None:
    st.session_state.bifrost_status = bifrost_runtime.status()


# ---------------------------------------------------------------------------
# Pages.
# ---------------------------------------------------------------------------
def page_home() -> None:
    st.title("bifrost-gateway-lab")
    st.caption("Real Bifrost AI Gateway, running on your laptop.")

    st.subheader("What this demo does")
    st.markdown(
        """
This app talks to a **real Bifrost gateway** on `localhost:8080`,
which in turn talks to **OpenAI** and **Anthropic** using the keys in
your `.env`. The same OpenAI Python SDK is used for both providers —
that's the whole point of an AI gateway.

```
 Streamlit ──▶ OpenAI SDK ──▶ Bifrost (localhost:8080) ──▶ OpenAI / Anthropic
```
        """
    )

    st.subheader("Gateway status")
    status = st.session_state.bifrost_status
    if status.reachable:
        st.success(f"Bifrost reachable at {status.base_url}  ·  {status.detail}")
    else:
        st.error(f"Bifrost not reachable at {status.base_url}")
        if status.detail:
            st.caption(status.detail)
        # getattr guards against a stale BifrostStatus left in
        # st.session_state from before this field existed (Streamlit
        # keeps session objects across code reloads / redeploys).
        log_tail = getattr(status, "log_tail", None)
        if log_tail:
            with st.expander("bifrost.log (last lines)", expanded=True):
                st.code(log_tail, language="text")
        st.caption(
            "Set `BIFROST_AUTOSTART=1` in `.env` (default) and make sure "
            "Node.js / `npx` is installed, or start Bifrost yourself with: "
            "`npx -y @maximhq/bifrost --app-dir . --port 8080`."
        )

    cols = st.columns(2)
    cols[0].metric("OpenAI key", "loaded" if config.has_openai_key() else "missing")
    cols[1].metric(
        "Anthropic key", "loaded" if config.has_anthropic_key() else "missing"
    )


def page_chat() -> None:
    st.title("Chat through Bifrost")
    st.caption("One prompt, one provider, real call.")

    enabled_models = [
        m
        for m in config.MODEL_CATALOG
        if (m.provider == "openai" and config.has_openai_key())
        or (m.provider == "anthropic" and config.has_anthropic_key())
    ]
    if not enabled_models:
        st.warning("No provider keys found in `.env`. Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.")
        return

    model = st.selectbox(
        "Model",
        options=enabled_models,
        format_func=lambda m: m.label,
    )
    system = st.text_input(
        "System prompt", value="You are a concise, helpful assistant."
    )
    prompt = st.text_area(
        "Prompt", value="Explain what an AI gateway does in one sentence.", height=110
    )

    if st.button("Send through Bifrost", type="primary"):
        request = ChatRequest(prompt=prompt, model=model, system=system)
        preview = prompt[:80] + ("…" if len(prompt) > 80 else "")
        try:
            response = gateway_client.chat(request)
        except gateway_client.GatewayError as exc:
            st.error(str(exc))
            st.session_state.audit.record_error(
                provider=model.provider,
                model=model.bifrost_id,
                error=str(exc),
                prompt_preview=preview,
            )
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Provider", response.provider)
        c2.metric("Model", response.model.split("/")[-1])
        c3.metric("Latency", f"{response.latency_ms:.0f} ms")
        c4.metric(
            "Tokens",
            f"{response.prompt_tokens}+{response.completion_tokens}",
        )

        st.markdown("**Response**")
        st.write(response.text)
        st.session_state.audit.record_response(response, prompt_preview=preview)


def page_compare() -> None:
    st.title("Compare providers")
    st.caption("Run the same prompt through OpenAI and Anthropic side by side.")

    if not (config.has_openai_key() and config.has_anthropic_key()):
        st.warning("Both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are required for this page.")
        return

    openai_model = next(m for m in config.MODEL_CATALOG if m.bifrost_id == "openai/gpt-4o-mini")
    anthropic_model = next(
        m for m in config.MODEL_CATALOG if m.bifrost_id == "anthropic/claude-3-5-haiku-20241022"
    )

    prompt = st.text_area(
        "Prompt",
        value="In one sentence, what is a virtual API key?",
        height=110,
    )

    if st.button("Run on both", type="primary"):
        preview = prompt[:80] + ("…" if len(prompt) > 80 else "")
        left, right = st.columns(2)
        for column, model in ((left, openai_model), (right, anthropic_model)):
            with column:
                st.markdown(f"**{model.label}**")
                try:
                    response = gateway_client.chat(
                        ChatRequest(prompt=prompt, model=model)
                    )
                except gateway_client.GatewayError as exc:
                    st.error(str(exc))
                    st.session_state.audit.record_error(
                        provider=model.provider,
                        model=model.bifrost_id,
                        error=str(exc),
                        prompt_preview=preview,
                    )
                    continue
                st.caption(
                    f"{response.latency_ms:.0f} ms · "
                    f"{response.prompt_tokens}+{response.completion_tokens} tokens"
                )
                st.write(response.text)
                st.session_state.audit.record_response(
                    response, prompt_preview=preview, note="compare"
                )


def page_config() -> None:
    st.title("Bifrost configuration")
    st.caption("The `config.json` file that this Bifrost instance is using.")

    if config.CONFIG_FILE.exists():
        raw = config.CONFIG_FILE.read_text()
        st.code(raw, language="json")
        try:
            parsed = json.loads(raw)
            providers = list(parsed.get("providers", {}).keys())
            st.caption(f"Providers configured: {', '.join(providers) or 'none'}")
        except json.JSONDecodeError as exc:
            st.error(f"config.json is not valid JSON: {exc}")
    else:
        st.error(f"`config.json` not found at {config.CONFIG_FILE}")


def page_audit() -> None:
    st.title("Audit log")
    st.caption("Every real call this session has made through Bifrost.")

    events = st.session_state.audit.events()
    if not events:
        st.write("_No calls yet. Try the Chat page._")
        return

    rows = [
        {
            "time": event.timestamp.strftime("%H:%M:%S"),
            "provider": event.provider,
            "model": event.model.split("/")[-1],
            "decision": event.decision,
            "latency_ms": round(event.latency_ms, 1),
            "tokens_in": event.prompt_tokens,
            "tokens_out": event.completion_tokens,
            "prompt": event.prompt_preview,
            "note": event.note,
        }
        for event in events
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if st.button("Clear audit log"):
        st.session_state.audit.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Sidebar nav.
# ---------------------------------------------------------------------------
PAGES = {
    "Home": page_home,
    "Chat through Bifrost": page_chat,
    "Compare providers": page_compare,
    "Bifrost config": page_config,
    "Audit log": page_audit,
}

with st.sidebar:
    st.markdown("### bifrost-gateway-lab")
    choice = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    status = st.session_state.bifrost_status
    indicator = "🟢" if status.reachable else "🔴"
    st.caption(f"{indicator} {status.base_url}")
    if st.button("Re-check gateway"):
        _refresh_status()
        st.rerun()

PAGES[choice]()
