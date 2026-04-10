"""
Internal helper shared by all agents.
Not part of the public API — do not import from outside openai_runtime.
"""
from __future__ import annotations

from .config import AgentConfig
from .provider import LLMResponse, Message, ToolDefinition, get_provider
from typing import Optional


def call_llm(
    agent: str,
    messages: list[Message],
    model: str,
    cfg: AgentConfig,
    tools: Optional[list[ToolDefinition]] = None,
    json_mode: bool = False,
) -> LLMResponse:
    """
    Single LLM call routed through the active provider.

    Propagates exceptions — callers handle retries or failures.
    """
    provider = get_provider()
    return provider.complete(
        messages=messages,
        model=model,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        tools=tools,
        json_mode=json_mode,
    )
