"""
OpenAI Chat Completions adapter.

The ONLY file in this codebase that imports `openai`.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

import boto3
from openai import OpenAI

from ..provider import LLMProvider, LLMResponse, Message, ToolCall, ToolDefinition, Usage


def _fetch_secret(secret_name: str) -> str:
    sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    raw = sm.get_secret_value(SecretId=secret_name)["SecretString"]
    try:
        return json.loads(raw)["api_key"]
    except (json.JSONDecodeError, KeyError):
        return raw.strip()


class OpenAIAdapter:
    """Wraps OpenAI Chat Completions API to satisfy LLMProvider."""

    def __init__(self, api_key_secret: str):
        self._secret_name = api_key_secret
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            # Allow direct env-var override for local dev (avoids Secrets Manager call)
            key = os.environ.get("OPENAI_API_KEY") or _fetch_secret(self._secret_name)
            self._client = OpenAI(api_key=key)
        return self._client

    def get_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY") or _fetch_secret(self._secret_name)

    def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()

        oai_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": model,
            "messages": oai_messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
            ),
            model=resp.model,
            finish_reason=choice.finish_reason or "stop",
        )
