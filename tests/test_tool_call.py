"""Integration test: 실제 LLM이 web_fetch tool call을 생성하는지 검증.

config.json의 provider 설정을 사용해서 실제 API를 호출합니다.
web_fetch 실행은 mock 처리하여 네트워크 의존성을 최소화합니다.

Usage:
    uv run pytest tests/test_tool_call.py -v -s
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tokamak.agent.loop import AgentLoop
from tokamak.agent.tools import ToolRegistry, WebFetchTool
from tokamak.config import Config
from tokamak.providers import OpenAICompatibleProvider
from tokamak.session import Session


def load_config() -> Config:
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        pytest.skip("config.json not found")
    return Config.model_validate_json(config_path.read_text())


def create_provider(config: Config) -> OpenAICompatibleProvider:
    if config.providers.openrouter:
        p = config.providers.openrouter
    elif config.providers.anthropic:
        p = config.providers.anthropic
    elif config.providers.openai:
        p = config.providers.openai
    else:
        pytest.skip("No provider configured")
    return OpenAICompatibleProvider(
        api_key=p.api_key,
        api_base=p.api_base,
        default_model=config.agent.model,
    )


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def provider(config):
    return create_provider(config)


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(WebFetchTool())
    return reg


@pytest.fixture
def session():
    return Session(key="test:channel:user")


class TestModelToolCall:
    """실제 LLM 모델이 web_fetch tool call을 생성하는지 검증."""

    @pytest.mark.asyncio
    async def test_model_calls_web_fetch_for_url_check(self, provider, registry, session):
        """URL 확인 요청 시 모델이 web_fetch를 호출하는지 검증."""
        agent = AgentLoop(
            provider=provider,
            tools=registry,
            model=provider.default_model,
            enable_korean_review=False,
        )

        # web_fetch 실행만 mock (실제 HTTP 호출 방지)
        mock_result = json.dumps({
            "url": "https://docs.tokamak.network",
            "status": 200,
            "text": "Tokamak Network Documentation",
        })
        tool_called = False
        original_execute = registry.execute

        async def track_execute(name, params):
            nonlocal tool_called
            if name == "web_fetch":
                tool_called = True
                return mock_result
            return await original_execute(name, params)

        with patch.object(registry, "execute", side_effect=track_execute):
            result = await agent.run(
                session,
                "https://docs.tokamak.network 이 링크 내용 좀 확인해줘",
            )

        assert tool_called, (
            f"모델이 web_fetch를 호출하지 않았습니다. 응답: {result}"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_model_does_not_call_tool_for_simple_greeting(self, provider, registry, session):
        """단순 인사에는 tool call 없이 바로 응답해야 한다."""
        agent = AgentLoop(
            provider=provider,
            tools=registry,
            model=provider.default_model,
            enable_korean_review=False,
        )

        tool_called = False
        original_execute = registry.execute

        async def track_execute(name, params):
            nonlocal tool_called
            tool_called = True
            return await original_execute(name, params)

        with patch.object(registry, "execute", side_effect=track_execute):
            result = await agent.run(session, "안녕하세요")

        assert not tool_called, (
            f"단순 인사인데 모델이 tool을 호출했습니다. 응답: {result}"
        )
        assert result is not None
