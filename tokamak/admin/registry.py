"""Admin tool registry with context injection."""

from typing import TYPE_CHECKING, Any

from tokamak.agent.tools.base import Tool
from tokamak.agent.tools.registry import ToolRegistry
from tokamak.admin.tools import ADMIN_TOOLS

if TYPE_CHECKING:
    import discord
    from tokamak.app import TokamakApp


class AdminToolRegistry:
    """Registry that injects guild/app context into admin tools."""

    def __init__(self, app: "TokamakApp", guild: "discord.Guild"):
        self._app = app
        self._guild = guild
        self._registry = ToolRegistry()

        for tool in ADMIN_TOOLS:
            self._registry.register(tool)

    def get_definitions(self) -> list[dict[str, Any]]:
        return self._registry.get_definitions()

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        params_with_context = {
            **params,
            "_app": self._app,
            "_guild": self._guild,
        }
        return await self._registry.execute(name, params_with_context)

    @property
    def tool_names(self) -> list[str]:
        return self._registry.tool_names
