"""OpenAI-compatible provider for LiteLLM Proxy and other OpenAI-compatible endpoints."""

import json
import re
import uuid
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from tokamak.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class OpenAICompatibleProvider(LLMProvider):
    """
    LLM provider using OpenAI SDK for OpenAI-compatible APIs.

    Works with LiteLLM Proxy, vLLM, and any OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gpt-4",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.client = AsyncOpenAI(
            api_key=api_key or "dummy",
            base_url=api_base,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via OpenAI SDK.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = model or self.default_model

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return LLMResponse(
                content="LLM 호출 중 오류가 발생했습니다.",
                finish_reason="error",
            )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        content = message.content

        # 1. Native function calling (OpenAI style)
        if message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        # 2. Text-based tool calls (for models that don't support native function calling)
        if not tool_calls and content:
            parsed_calls, cleaned_content = self._parse_text_tool_calls(content)
            if parsed_calls:
                tool_calls = parsed_calls
                content = cleaned_content.strip() if cleaned_content else None

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    def _parse_text_tool_calls(self, content: str) -> tuple[list[ToolCallRequest], str]:
        """
        Parse text-based tool calls from content.

        Supports formats:
        - <tool_call>{"name": "...", "arguments": {...}}</tool_call>

        Returns:
            Tuple of (parsed tool calls, content with tool calls removed)
        """
        tool_calls = []
        cleaned_content = content

        # Pattern: <tool_call>...</tool_call>
        pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                name = data.get("name")
                arguments = data.get("arguments", {})

                if name:
                    tool_calls.append(
                        ToolCallRequest(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=name,
                            arguments=arguments,
                        )
                    )
            except json.JSONDecodeError:
                continue

        # Remove tool call tags from content
        if tool_calls:
            cleaned_content = re.sub(pattern, "", content, flags=re.DOTALL)

        return tool_calls, cleaned_content

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
