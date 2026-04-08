from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from .config import LLMConfig
from .token_tracker import get_token_tracker

try:
    import litellm
except Exception:  # noqa: BLE001
    litellm = None


@dataclass(slots=True)
class LLMResponse:
    content: str | None
    tool_calls: list[dict] | None = None
    usage: dict | None = None
    model: str | None = None
    finish_reason: str | None = None


class LLMProtocol(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...


class LLMClient:
    """LiteLLM wrapper with deterministic fallback for local tests."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.load()

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if self.config.model.startswith("mock/"):
            return self._fallback_response()

        if litellm is None:
            return self._fallback_response("LiteLLM is not installed; using fallback response")

        temp = self.config.temperature if temperature is None else temperature
        token_limit = self.config.max_tokens if max_tokens is None else max_tokens

        if self.config.api_key:
            litellm.api_key = self.config.api_key
        if self.config.api_base:
            litellm.api_base = self.config.api_base

        delay = 5
        for attempt in range(self.config.max_retries + 1):
            try:
                response: Any = await litellm.acompletion(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=token_limit,
                    drop_params=True,
                )
                message = response.choices[0].message
                usage = getattr(response, "usage", None)
                usage_dict = dict(usage) if usage is not None else {}
                resp = LLMResponse(
                    content=getattr(message, "content", ""),
                    tool_calls=getattr(message, "tool_calls", []),
                    usage=usage_dict,
                    model=getattr(response, "model", self.config.model),
                    finish_reason=getattr(response.choices[0], "finish_reason", "stop"),
                )
                # Record token usage and cost
                await get_token_tracker().record(usage_dict, model=resp.model or self.config.model)
                return resp
            except Exception as exc:  # noqa: BLE001
                if attempt >= self.config.max_retries:
                    return self._fallback_response(f"LiteLLM failure: {exc}")
                await asyncio.sleep(delay)
                delay *= 2

        return self._fallback_response()

    def _fallback_response(self, note: str | None = None) -> LLMResponse:
        content = "<function=agent_finish><parameter=report>Fallback completion"
        if note:
            content += f" ({note})"
        content += "</parameter></function>"
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.config.model,
            finish_reason="stop",
        )
