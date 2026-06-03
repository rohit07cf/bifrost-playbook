"""Thin OpenAI-SDK client pointed at the local Bifrost gateway.

We deliberately use the official `openai` SDK because Bifrost speaks
the OpenAI Chat Completions wire format on `/v1/chat/completions`.
Provider routing is encoded in the `model` field as `<provider>/<id>`.
The real provider API keys live with Bifrost (loaded from .env via
config.json), so the SDK only needs a placeholder key.
"""

from __future__ import annotations

import time

from openai import OpenAI, OpenAIError

from . import config
from .models import ChatRequest, ChatResponse


def _make_client() -> OpenAI:
    """Construct an OpenAI client that talks to Bifrost.

    Bifrost authenticates the *upstream* call (OpenAI, Anthropic) using
    the keys in its own config — the SDK key here is unused but
    required by the SDK constructor, so we pass a sentinel.
    """
    return OpenAI(base_url=config.BIFROST_OPENAI_BASE, api_key="bifrost-local")


def chat(request: ChatRequest) -> ChatResponse:
    """Send one chat request through Bifrost and adapt the reply."""
    client = _make_client()
    started = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=request.model.bifrost_id,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        )
    except OpenAIError as exc:
        raise GatewayError(str(exc)) from exc

    latency_ms = (time.perf_counter() - started) * 1000
    choice = completion.choices[0]
    text = choice.message.content or ""
    usage = completion.usage
    return ChatResponse(
        provider=request.model.provider,
        model=completion.model or request.model.bifrost_id,
        text=text,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        latency_ms=round(latency_ms, 1),
    )


class GatewayError(RuntimeError):
    """Raised when Bifrost or the upstream provider returns an error."""
