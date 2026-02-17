"""Admin command handler."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from discord import Message
from loguru import logger

from tokamak.config.schema import AdminConfig

if TYPE_CHECKING:
    from tokamak.app import TokamakApp


@dataclass
class AdminContext:
    """Context passed to admin commands."""

    message: Message
    app: "TokamakApp"
    args: list[str]


class AdminCommand(ABC):
    """Base class for admin commands."""

    name: str = ""
    description: str = ""
    usage: str = ""

    @abstractmethod
    async def execute(self, ctx: AdminContext) -> str:
        """Execute the command and return response."""
        ...


class AdminHandler:
    """Handles admin commands from DMs."""

    def __init__(self, config: AdminConfig, app: "TokamakApp"):
        self.config = config
        self.app = app
        self._commands: dict[str, AdminCommand] = {}
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        from tokamak.admin.commands import (
            BroadcastCommand,
            ClearCommand,
            HelpCommand,
            SessionsCommand,
            StatusCommand,
            TimeoutCommand,
            UntimeoutCommand,
        )

        self.register(StatusCommand())
        self.register(SessionsCommand())
        self.register(ClearCommand())
        self.register(BroadcastCommand())
        self.register(TimeoutCommand())
        self.register(UntimeoutCommand())
        self.register(HelpCommand())

    def register(self, command: AdminCommand) -> None:
        """Register a command."""
        self._commands[command.name] = command
        logger.debug(f"Registered admin command: {command.name}")

    async def handle(self, message: Message) -> None:
        """Handle an admin DM message."""
        content = message.content.strip()
        prefix = self.config.command_prefix

        if not content.startswith(prefix):
            await message.reply(
                f"명령어는 `{prefix}`로 시작해야 합니다.\n"
                f"`{prefix}help`로 사용 가능한 명령어를 확인하세요."
            )
            return

        parts = content[len(prefix) :].split()
        if not parts:
            await message.reply("명령어를 입력해주세요.")
            return

        cmd_name = parts[0].lower()
        args = parts[1:]

        if cmd_name not in self._commands:
            await message.reply(f"알 수 없는 명령어: `{cmd_name}`\n`{prefix}help`를 참고하세요.")
            return

        command = self._commands[cmd_name]
        ctx = AdminContext(message=message, app=self.app, args=args)

        logger.info(
            f"Admin command executed: {cmd_name} "
            f"by user {message.author.id} ({message.author.display_name})"
        )

        try:
            response = await command.execute(ctx)
            if response:
                await message.reply(response)
        except Exception as e:
            logger.error(f"Error executing admin command {cmd_name}: {e}")
            await message.reply(f"명령 실행 중 오류 발생: {e}")

    def get_commands_info(self) -> list[dict[str, str]]:
        """Get list of all registered commands with their info."""
        return [
            {
                "name": cmd.name,
                "description": cmd.description,
                "usage": cmd.usage,
            }
            for cmd in self._commands.values()
        ]
