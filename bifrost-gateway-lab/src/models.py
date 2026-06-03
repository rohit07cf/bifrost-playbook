"""Pydantic v2 models for chat requests and audit events.

These are the only shapes the Streamlit app cares about. The OpenAI
SDK gives back its own response objects — we adapt them into
`ChatResponse` so the UI stays decoupled from SDK version churn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt

Provider = Literal["openai", "anthropic"]
Decision = Literal["ok", "error"]


class ModelChoice(BaseModel):
    """One model exposed in the UI dropdown."""

    label: str
    provider: Provider
    # Bifrost expects `<provider>/<model>` in the `model` field.
    bifrost_id: str


class ChatRequest(BaseModel):
    """A chat request the UI hands to the gateway client."""

    prompt: str = Field(min_length=1)
    model: ModelChoice
    system: str = "You are a concise, helpful assistant."


class ChatResponse(BaseModel):
    """Adapted OpenAI-compatible response."""

    provider: Provider
    model: str
    text: str
    prompt_tokens: NonNegativeInt = 0
    completion_tokens: NonNegativeInt = 0
    latency_ms: NonNegativeFloat = 0.0


class AuditEvent(BaseModel):
    """One row in the in-session audit log."""

    timestamp: datetime
    provider: Provider
    model: str
    decision: Decision
    latency_ms: NonNegativeFloat = 0.0
    prompt_tokens: NonNegativeInt = 0
    completion_tokens: NonNegativeInt = 0
    note: str = ""
    prompt_preview: str = ""


class BifrostStatus(BaseModel):
    """Health snapshot of the local Bifrost gateway."""

    reachable: bool
    base_url: str
    detail: Optional[str] = None
