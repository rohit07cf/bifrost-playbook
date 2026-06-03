# bifrost-gateway-lab

A small Streamlit app that runs a **real** [Bifrost AI Gateway](https://www.getmaxim.ai/bifrost)
on `localhost:8080` and uses it to route chat requests to **OpenAI**
and **Anthropic** through a single OpenAI-compatible endpoint.

> Docs reference: <https://docs.getbifrost.ai/overview>.

## What you get

- Bifrost is started automatically as a subprocess via
  `npx -y @maximhq/bifrost`. The npm wrapper downloads the
  platform-appropriate Go binary on first run.
- Provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) live in `.env`
  and are referenced from `config.json` using Bifrost's
  `env.OPENAI_API_KEY` syntax.
- The Streamlit app uses the **official `openai` Python SDK** pointed
  at Bifrost — the same SDK call works for OpenAI **and** Anthropic
  because Bifrost translates between protocols.

## Project layout

```
bifrost-gateway-lab/
  app.py                  # Streamlit UI
  config.json             # Bifrost provider config (loaded from --app-dir)
  requirements.txt
  .env.example            # Copy to .env and fill in keys
  README.md
  src/
    config.py             # Loads .env + model catalog
    bifrost_runtime.py    # Starts/probes/stops the Bifrost subprocess
    gateway_client.py     # OpenAI SDK pointed at Bifrost
    models.py             # Pydantic v2 models
    audit.py              # In-session call log
  tests/
    test_models.py
    test_gateway_client.py
```

## Prerequisites

- Python 3.11+
- Node.js 18+ on PATH (so `npx` can fetch `@maximhq/bifrost`)
- An OpenAI key, an Anthropic key, or both

## Setup

```bash
# 1. clone, create the env, install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. configure your keys
cp .env.example .env
# then edit .env and paste in your OPENAI_API_KEY / ANTHROPIC_API_KEY

# 3. run it
streamlit run app.py
```

Open <http://localhost:8501>. The first run will take ~10–30 seconds
while `npx` downloads the Bifrost binary; subsequent runs use the
cached binary and start in a second.

You can also run Bifrost yourself in another terminal and set
`BIFROST_AUTOSTART=0` in `.env`:

```bash
npx -y @maximhq/bifrost --app-dir . --port 8080
```

Bifrost's own web UI (configuration, live traces) is at
<http://localhost:8080>.

## How the pieces fit together

```
   ┌──────────────┐    OpenAI Python SDK     ┌──────────────────┐
   │  Streamlit   │ ───────────────────────▶ │  Bifrost (Go)    │
   │   (app.py)   │      base_url =          │  localhost:8080  │
   └──────────────┘  http://localhost:8080/v1 └────────┬─────────┘
                                                       │
                          model = "openai/gpt-4o-mini" │
                          model = "anthropic/claude-3-5-haiku-…"
                                                       │
                                          ┌────────────┴────────────┐
                                          ▼                         ▼
                                   api.openai.com           api.anthropic.com
```

Bifrost reads `config.json` from `--app-dir`. Each provider block
references the matching env var, e.g.:

```json
{
  "providers": {
    "openai": {
      "keys": [{ "value": "env.OPENAI_API_KEY", "models": ["gpt-4o-mini"], "weight": 1.0 }]
    },
    "anthropic": {
      "keys": [{ "value": "env.ANTHROPIC_API_KEY", "models": ["claude-3-5-haiku-20241022"], "weight": 1.0 }]
    }
  }
}
```

## Running tests

```bash
pytest -q
```

The tests use a stubbed OpenAI SDK — they don't touch the network or
require Bifrost to be running.

## Demo flow

1. **Home** — verifies Bifrost is reachable and that your keys are loaded.
2. **Chat through Bifrost** — pick a model, send a prompt, see real
   provider name + token usage + latency.
3. **Compare providers** — run the same prompt through `gpt-4o-mini`
   and `claude-3-5-haiku` side by side.
4. **Bifrost config** — view the live `config.json`.
5. **Audit log** — every call recorded in session state.

## Troubleshooting

- **"Bifrost not reachable"** — make sure Node.js is installed and
  `npx` is on your PATH. Inspect `bifrost.log` in the project root for
  the underlying error.
- **`401`/`429` from a provider** — your `.env` key is missing, wrong,
  or rate-limited. Bifrost forwards the upstream error verbatim.
- **First launch is slow** — `npx` downloads the Bifrost binary from
  `downloads.getmaxim.ai`. If your network blocks that host, install
  Bifrost another way (Docker / Go) and set `BIFROST_AUTOSTART=0`.
