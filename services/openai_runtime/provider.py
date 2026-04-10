"""
LLM provider abstraction layer.

All agent code talks to `LLMProvider` — never to a vendor SDK directly.

ADDING A NEW PROVIDER
---------------------
1. Create `adapters/<vendor>_adapter.py` and implement `LLMProvider`
2. Add the provider name + class to `_PROVIDER_REGISTRY`
3. Add the provider config block to `model_config.yaml`
4. Change `active_provider` in model_config.yaml

Nothing else needs to change.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional, Protocol


# ── Value objects ─────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str    # "system" | "user" | "assistant"
    content: str


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict   # JSON Schema for the function arguments


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict    # parsed JSON


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=lambda: Usage(0, 0))
    model: str = ""
    finish_reason: str = "stop"   # "stop" | "tool_calls" | "length"


# ── Protocol ──────────────────────────────────────────────────────────────────

class LLMProvider(Protocol):
    """
    Minimal interface every LLM adapter must satisfy.

    `complete()` performs a single round-trip to the LLM.
    For agentic loops (tool use), callers manage the loop themselves.
    """

    def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        ...

    def get_api_key(self) -> str:
        """Return the API key (may trigger a Secrets Manager read)."""
        ...


# ── Secrets Manager helper ────────────────────────────────────────────────────

def _fetch_secret(secret_name: str, region: str = "us-east-1") -> str:
    """Read a secret from AWS Secrets Manager. Caches the result in-process."""
    import boto3

    sm = boto3.client("secretsmanager", region_name=region)
    resp = sm.get_secret_value(SecretId=secret_name)
    raw = resp["SecretString"]
    # Secret may be plain string or JSON {"api_key": "sk-..."}
    try:
        return json.loads(raw)["api_key"]
    except (json.JSONDecodeError, KeyError):
        return raw.strip()


# ── Provider factory ──────────────────────────────────────────────────────────

def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Return the active provider adapter.

    provider_name defaults to `active_provider` from model_config.yaml.
    """
    from .config import active_provider_name, load_config

    name = provider_name or active_provider_name()
    cfg = load_config().providers[name]

    if name == "openai":
        from .adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(api_key_secret=cfg.api_key_secret)

    if name == "anthropic":
        from .adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(api_key_secret=cfg.api_key_secret)

    if name == "gemini":
        from .adapters.gemini_adapter import GeminiAdapter
        return GeminiAdapter(api_key_secret=cfg.api_key_secret)

    raise ValueError(f"Unknown provider '{name}'. Supported: openai, anthropic, gemini.")
