"""Admin handler with LLM-based tool calling."""

import json
from collections import deque
from typing import TYPE_CHECKING

from discord import Message
from loguru import logger

from tokamak.admin.prompt import ADMIN_SYSTEM_PROMPT
from tokamak.admin.registry import AdminToolRegistry
from tokamak.config.schema import AdminConfig

if TYPE_CHECKING:
    from tokamak.app import TokamakApp


class AdminHandler:
    """Handles admin messages with LLM-based tool calling."""

    def __init__(self, config: AdminConfig, app: "TokamakApp"):
        self.config = config
        self.app = app
        self._channel_histories: dict[int, deque[dict]] = {}
        self._max_history = 100

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
        logger.info(
            f"Admin message from {message.author.display_name}: {content[:50]}..."
        )

        self._add_to_history(channel_id, {
            "role": "user",
            "content": content,
            "author": message.author.display_name,
        })

        try:
            response = await self._run_agent(channel_id, content, guild)

            if response:
                self._add_to_history(channel_id, {
                    "role": "assistant",
                    "content": response,
                })
                await message.reply(response)
            else:
                await message.reply("요청을 처리하는 중 문제가 발생했습니다.")

        except Exception as e:
            logger.error(f"Admin handler error: {e}")
            await message.reply(f"처리 중 오류 발생: {e}")

    async def _run_agent(
        self, channel_id: int, message: str, guild
    ) -> str | None:
        tools = AdminToolRegistry(self.app, guild)
        tool_definitions = tools.get_definitions()

        history = list(self._get_history(channel_id))
        history_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]

        messages = [
            {"role": "system", "content": ADMIN_SYSTEM_PROMPT},
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
                self._add_to_history(channel_id, {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": assistant_msg["tool_calls"],
                })

                for tc in response.tool_calls:
                    logger.info(f"Admin tool call: {tc.name}({tc.arguments})")
                    result = await tools.execute(tc.name, tc.arguments)
                    logger.info(f"Admin tool result: {result[:200]}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
                    self._add_to_history(channel_id, {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                continue

            return response.content.strip() if response.content else None

        return "처리 시간이 초과되었습니다. 다시 시도해주세요."
