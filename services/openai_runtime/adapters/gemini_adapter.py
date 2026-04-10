"""
Google Gemini adapter stub — implement when switching active_provider to 'gemini'.

To activate:
  1. pip install google-generativeai
  2. Store API key in AWS Secrets Manager at the name in model_config.yaml
  3. Set active_provider: gemini in model_config.yaml
  4. Uncomment the implementation below
"""
from __future__ import annotations

from typing import Optional

from ..provider import LLMProvider, LLMResponse, Message, ToolDefinition


class GeminiAdapter:
    """Wraps Google Generative AI SDK to satisfy LLMProvider."""

    def __init__(self, api_key_secret: str):
        self._secret_name = api_key_secret

    def get_api_key(self) -> str:
        raise NotImplementedError("Gemini adapter not yet implemented.")

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
        # import google.generativeai as genai
        # genai.configure(api_key=_fetch_secret(self._secret_name))
        # client = genai.GenerativeModel(model)
        # config = genai.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature)
        # chat = client.start_chat(history=_to_gemini_history(messages[:-1]))
        # resp = chat.send_message(messages[-1].content, generation_config=config)
        # return _from_gemini_response(resp)
        raise NotImplementedError(
            "Gemini adapter is not yet implemented. "
            "Set active_provider: openai in model_config.yaml to use OpenAI."
        )
