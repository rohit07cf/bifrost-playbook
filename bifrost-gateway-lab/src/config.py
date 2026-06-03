"""Environment + model catalog for the app.

Loads `.env` once at import time (idempotent) and exposes a small set of
typed constants the rest of the code reads from.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import ModelChoice

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = PROJECT_ROOT / "config.json"

load_dotenv(ENV_FILE, override=False)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


BIFROST_HOST = os.getenv("BIFROST_HOST", "127.0.0.1")
BIFROST_PORT = int(os.getenv("BIFROST_PORT", "8080"))
BIFROST_AUTOSTART = _bool_env("BIFROST_AUTOSTART", True)

BIFROST_BASE_URL = f"http://{BIFROST_HOST}:{BIFROST_PORT}"
# OpenAI-compatible endpoint exposed by Bifrost.
BIFROST_OPENAI_BASE = f"{BIFROST_BASE_URL}/v1"


# Surfaced in the UI dropdown. `bifrost_id` is what we put in the
# `model` field of the request — Bifrost routes by the `<provider>/`
# prefix.
MODEL_CATALOG: list[ModelChoice] = [
    ModelChoice(label="OpenAI · gpt-4o-mini (fast, cheap)", provider="openai", bifrost_id="openai/gpt-4o-mini"),
    ModelChoice(label="OpenAI · gpt-4o (premium)", provider="openai", bifrost_id="openai/gpt-4o"),
    ModelChoice(label="Anthropic · claude-3-5-haiku (fast, cheap)", provider="anthropic", bifrost_id="anthropic/claude-3-5-haiku-20241022"),
    ModelChoice(label="Anthropic · claude-3-5-sonnet (premium)", provider="anthropic", bifrost_id="anthropic/claude-3-5-sonnet-20241022"),
]


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))
