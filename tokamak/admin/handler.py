"""Admin handler with LLM-based tool calling using skills."""

import json
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from discord import Message
from loguru import logger

from tokamak.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader
from tokamak.agent.tools import InternalStateTool, ToolRegistry, WebFetchTool, WebPostTool
from tokamak.config.schema import AdminConfig

if TYPE_CHECKING:
    from tokamak.app import TokamakApp


ADMIN_SYSTEM_PROMPT = """당신은 Tokamak Network Discord 봇의 관리자 어시스턴트입니다.

## 현재 컨텍스트
- 서버 ID (Guild ID): {guild_id}
- 서버 이름: {guild_name}
- 현재 시간 (UTC): {current_time}

## 중요: 도구 호출 규칙

작업을 수행할 때 반드시 **도구(tool)를 호출**하세요. JSON을 텍스트로 출력하지 마세요.

올바른 예:
- 사용자 검색: web_fetch 도구 호출 (url: "...members/search", params: {{"query": "홍길동"}})
- 타임아웃 설정: web_post 도구 호출 (url: "...members/{{user_id}}", method: "PATCH", body: {{...}})
- 채널 메시지: web_post 도구 호출 (url: "...channels/{{channel_id}}/messages", method: "POST", body: {{"content": "..."}})

잘못된 예:
- JSON을 텍스트로 출력: {{"url": "...", "method": "POST", ...}}  ← 이렇게 하지 마세요!

## 사용 가능한 도구

### web_fetch (GET 요청 - 데이터 조회)
```
web_fetch(
  url="https://discord.com/api/v10/...",
  params={{"query": "검색어", "limit": "10"}},  # 쿼리 파라미터
  auth_provider="discord"
)
```

### web_post (POST/PUT/PATCH/DELETE - 데이터 수정)
```
web_post(
  url="https://discord.com/api/v10/...",
  method="PATCH",  # POST, PUT, PATCH, DELETE 중 하나
  body={{"key": "value"}},  # JSON 본문
  auth_provider="discord"
)
```

### internal_state (봇 상태 관리)
```
internal_state(action="get_status")  # get_status, list_sessions, delete_session
```

## Discord API 엔드포인트

- 사용자 검색: GET /guilds/{{guild_id}}/members/search?query={{이름}}
- 타임아웃: PATCH /guilds/{{guild_id}}/members/{{user_id}}
- 채널 목록: GET /guilds/{{guild_id}}/channels
- 채널 메시지: POST /channels/{{channel_id}}/messages

## 타임아웃 시간 계산

현재 시간({current_time})을 기준으로 계산하세요:
- "1시간" → 현재 + 60분: ISO8601 형식으로 변환
- 최대 7일 (10080분)

⚠️ joined_at 등 과거 시간을 기준으로 계산하지 마세요!

## 사용 가능한 스킬

{skills_summary}

## 워크플로우

1. 사용자 요청 분석
2. **적절한 도구를 직접 호출** (JSON 텍스트 출력 금지)
3. 결과를 한국어로 응답"""

ADMIN_SKILLS = ["discord-admin", "internal"]


class AdminHandler:
    """Handles admin messages with LLM-based tool calling using skills."""

    def __init__(self, config: AdminConfig, app: "TokamakApp"):
        self.config = config
        self.app = app
        self._channel_histories: dict[int, deque[dict]] = {}
        self._max_history = 100

        self.skills_loader = SkillsLoader(
            workspace=app.data_dir,
            builtin_skills_dir=BUILTIN_SKILLS_DIR,
            env_overrides={"DISCORD_TOKEN": app.config.discord.token}
            if app.config.discord.token
            else {},
        )

        self.tools = self._create_tools()

    def _create_tools(self) -> ToolRegistry:
        registry = ToolRegistry()

        auth_tokens = {}
        if self.app.config.discord.token:
            auth_tokens["discord"] = self.app.config.discord.token

        registry.register(WebFetchTool(auth_tokens=auth_tokens))
        registry.register(WebPostTool(auth_tokens=auth_tokens))
        registry.register(InternalStateTool())

        return registry

    def _get_history(self, channel_id: int) -> deque[dict]:
        if channel_id not in self._channel_histories:
            self._channel_histories[channel_id] = deque(maxlen=self._max_history)
        return self._channel_histories[channel_id]

    def _add_to_history(self, channel_id: int, message: dict) -> None:
        history = self._get_history(channel_id)
        history.append(message)

    async def handle(self, message: Message) -> None:
        content = message.content.strip()

        if not content:
            return

        guild = message.guild
        if not guild:
            await message.reply("이 명령어는 서버 채널에서만 사용할 수 있습니다.")
            return

        channel_id = message.channel.id
        logger.info(f"Admin message from {message.author.display_name}: {content[:50]}...")

        self._add_to_history(
            channel_id,
            {
                "role": "user",
                "content": content,
                "author": message.author.display_name,
            },
        )

        try:
            response = await self._run_agent(channel_id, content, guild)

            if response:
                self._add_to_history(
                    channel_id,
                    {
                        "role": "assistant",
                        "content": response,
                    },
                )
                await message.reply(response)
            else:
                await message.reply("요청을 처리하는 중 문제가 발생했습니다.")

        except Exception as e:
            logger.error(f"Admin handler error: {e}")
            await message.reply(f"처리 중 오류 발생: {e}")

    async def _run_agent(self, channel_id: int, message: str, guild) -> str | None:
        tool_definitions = self.tools.get_definitions()

        skills_summary = self.skills_loader.build_skills_summary()

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        system_prompt = ADMIN_SYSTEM_PROMPT.format(
            guild_id=guild.id,
            guild_name=guild.name,
            skills_summary=skills_summary,
            current_time=current_time,
        )

        history = list(self._get_history(channel_id))
        history_messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]

        messages = [
            {"role": "system", "content": system_prompt},
            *history_messages,
        ]

        max_iterations = 5
        for _ in range(max_iterations):
            response = await self.app.provider.chat(
                messages=messages,
                tools=tool_definitions,
                model=self.app.config.agent.model,
                max_tokens=1024,
                temperature=0.3,
            )

            if response.finish_reason == "error":
                logger.error(f"LLM error: {response.content}")
                return "AI 응답 생성 중 오류가 발생했습니다."

            if response.has_tool_calls:
                assistant_msg = {"role": "assistant", "content": response.content}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append(assistant_msg)
                self._add_to_history(
                    channel_id,
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": assistant_msg["tool_calls"],
                    },
                )

                for tc in response.tool_calls:
                    logger.info(f"Admin tool call: {tc.name}({tc.arguments})")

                    params = dict(tc.arguments) if isinstance(tc.arguments, dict) else {}
                    if tc.name == "internal_state":
                        params["_app"] = self.app

                    result = await self.tools.execute(tc.name, params)
                    logger.info(f"Admin tool result: {result}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
                    self._add_to_history(
                        channel_id,
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        },
                    )

                continue

            return response.content.strip() if response.content else None

        return "처리 시간이 초과되었습니다. 다시 시도해주세요."
