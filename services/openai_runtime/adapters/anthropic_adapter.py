"""
Anthropic adapter stub — implement when switching active_provider to 'anthropic'.

To activate:
  1. pip install anthropic
  2. Store API key in AWS Secrets Manager at the name in model_config.yaml
  3. Set active_provider: anthropic in model_config.yaml
  4. Uncomment the implementation below
"""
from __future__ import annotations

from typing import Optional

from ..provider import LLMProvider, LLMResponse, Message, ToolDefinition


class AnthropicAdapter:
    """Wraps Anthropic Messages API to satisfy LLMProvider."""

    def __init__(self, api_key_secret: str):
        self._secret_name = api_key_secret

    def get_api_key(self) -> str:
        raise NotImplementedError("Anthropic adapter not yet implemented.")

    def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Implementation outline when ready:
        #
        # import anthropic
        # client = anthropic.Anthropic(api_key=_fetch_secret(self._secret_name))
        #
        # system_msg, user_msgs = _split_system(messages)
        # resp = client.messages.create(
        #     model=model,
        #     max_tokens=max_tokens,
        #     temperature=temperature,
        #     system=system_msg,
        #     messages=user_msgs,
        #     tools=[_to_anthropic_tool(t) for t in (tools or [])],
        # )
        # return _from_anthropic_response(resp)
        raise NotImplementedError(
            "Anthropic adapter is not yet implemented. "
            "Set active_provider: openai in model_config.yaml to use OpenAI."
        )
