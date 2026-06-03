"""Gateway-client tests using a stubbed OpenAI client (no network).

We don't want pytest to hit Bifrost or OpenAI. Instead we monkeypatch
the SDK constructor so we can assert on the exact request our code
builds and verify it adapts a fake completion into the right
`ChatResponse`.
"""

from __future__ import annotations

from types import SimpleNamespace

from src import gateway_client
from src.models import ChatRequest, ModelChoice


class _FakeCompletions:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello world"))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=2),
        )


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeOpenAI:
    last_instance: "_FakeOpenAI | None" = None

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.chat = _FakeChat()
        _FakeOpenAI.last_instance = self


def test_chat_targets_bifrost_and_uses_prefixed_model(monkeypatch) -> None:
    monkeypatch.setattr(gateway_client, "OpenAI", _FakeOpenAI)
    request = ChatRequest(
        prompt="hi",
        system="be brief",
        model=ModelChoice(
            label="OpenAI · gpt-4o-mini",
            provider="openai",
            bifrost_id="openai/gpt-4o-mini",
        ),
    )

    response = gateway_client.chat(request)

    client = _FakeOpenAI.last_instance
    assert client is not None
    assert client.base_url.endswith("/v1")
    assert "127.0.0.1" in client.base_url or "localhost" in client.base_url

    kwargs = client.chat.completions.last_kwargs
    assert kwargs is not None
    assert kwargs["model"] == "openai/gpt-4o-mini"
    roles = [m["role"] for m in kwargs["messages"]]
    assert roles == ["system", "user"]
    assert kwargs["messages"][1]["content"] == "hi"

    assert response.provider == "openai"
    assert response.text == "hello world"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 2
    assert response.latency_ms >= 0


def test_chat_wraps_sdk_errors_in_gateway_error(monkeypatch) -> None:
    from openai import OpenAIError

    class _Boom(_FakeOpenAI):
        def __init__(self, base_url, api_key):
            super().__init__(base_url, api_key)
            self.chat.completions.create = self._raise  # type: ignore[assignment]

        @staticmethod
        def _raise(**_kwargs):
            raise OpenAIError("upstream unreachable")

    monkeypatch.setattr(gateway_client, "OpenAI", _Boom)
    request = ChatRequest(
        prompt="x",
        model=ModelChoice(
            label="OpenAI · gpt-4o-mini",
            provider="openai",
            bifrost_id="openai/gpt-4o-mini",
        ),
    )

    import pytest

    with pytest.raises(gateway_client.GatewayError, match="upstream unreachable"):
        gateway_client.chat(request)
