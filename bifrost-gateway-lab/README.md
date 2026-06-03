# bifrost-gateway-lab

A small, portfolio-friendly Streamlit app that **teaches and demonstrates
the core ideas behind the [Bifrost AI Gateway](https://www.getmaxim.ai/bifrost)**
by Maxim AI — without needing any real provider keys.

> This is a **local educational simulation**, not an official Bifrost
> integration. Provider calls and MCP tool execution are mocked.
> Reference docs: <https://docs.getbifrost.ai/overview> and
> <https://www.getmaxim.ai/bifrost/resources/mcp-gateway>.

## What this project demonstrates

Bifrost ships two gateways. This lab models both:

- **LLM Gateway** — one OpenAI-compatible entry point that fronts many
  providers and adds routing, semantic caching, automatic fallback,
  rate limits, budget control, and observability.
- **MCP Gateway** — a centralized gateway for **tool calls from AI
  agents** that adds tool discovery, role-based access control,
  risk-aware execution, and audit trails.

The Streamlit UI walks a beginner through both, side by side, with a
live audit log.

## Project layout

```
bifrost-gateway-lab/
  app.py                  # Streamlit entry point
  requirements.txt
  README.md
  src/
    models.py             # Pydantic v2 models
    llm_gateway.py        # Simulated LLM Gateway
    mcp_gateway.py        # Simulated MCP Gateway
    security.py           # Rate limits + budget policy engine
    audit.py              # In-memory audit log
    mock_data.py          # Mock providers, tools, and RBAC rules
  tests/
    test_llm_gateway.py
    test_mcp_gateway.py
```

## How to run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually <http://localhost:8501>).

To run the tests:

```bash
pytest -q
```

## Demo scenarios to try

1. **LLM fallback when OpenAI is unavailable**
   Go to *LLM Gateway Demo*, pick the `fastest` strategy, uncheck
   *openai healthy*, and send a prompt. The gateway falls back to the
   next-fastest healthy provider and the trace shows it.

2. **Cache hit on repeated prompt**
   On the same page, send any prompt twice. The second response shows
   `cache hit = yes` and zero added cost.

3. **Intern agent blocked from `ticket_creator`**
   Go to *MCP Gateway Demo*, pick `intern_agent`, choose
   `ticket_creator`, and click *Invoke tool*. The gateway blocks it via
   the role allowlist.

4. **Admin agent allowed to use `ticket_creator`**
   Same page, switch to `admin_agent`, and invoke `ticket_creator`. The
   call is allowed and a simulated ticket id is returned.

5. **Rate limit exceeded**
   In *LLM Gateway Demo*, send 6+ prompts in quick succession with the
   same virtual key. The 6th one is blocked by the policy engine (see
   *Security & Governance* for the configured limits).

Every action above appears in *Live Audit Log* with a timestamp,
decision, latency, and cost.

## LLM Gateway vs MCP Gateway

| Concern           | LLM Gateway                                  | MCP Gateway                                |
|-------------------|----------------------------------------------|--------------------------------------------|
| What it routes    | Model calls (OpenAI, Anthropic, Gemini, …)   | Tool calls from AI agents (MCP tools)      |
| Main goal         | Reliable, cheap, fast model access           | Safe, governed tool access                 |
| Key controls      | Routing, caching, fallback, budgets, RPS     | Discovery, RBAC, risk checks, audit        |
| Typical risk      | Latency spikes, cost blowups, outages        | Wrong tool used, data exfiltration, PI     |
| Observability     | Cost & latency per provider, cache hit rate  | Who called what, when, and with what input |

In production you usually want **both**, working together.

## Disclaimers

- This repo is an educational toy. Real Bifrost handles many more
  concerns (semantic caching, multi-tenant governance, distributed
  rate limits, real provider keys, etc.) — see the official docs.
- No real API calls are made. All providers and tools are mocked.
