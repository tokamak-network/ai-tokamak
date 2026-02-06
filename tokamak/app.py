"""Main application that integrates all components."""

import asyncio
from pathlib import Path

from loguru import logger

from tokamak.agent import AgentLoop
from tokamak.agent.skills import SkillsLoader
from tokamak.agent.tools import ToolRegistry, WebFetchTool
from tokamak.bus import MessageBus
from tokamak.channels import DiscordChannel
from tokamak.config import Config
from tokamak.providers import OpenAICompatibleProvider
from tokamak.session import Session, SessionManager


class TokamakApp:
    """Main application orchestrating all components."""

    def __init__(self, config: Config, data_dir: Path = Path("data")):
        """
        Initialize the application.

        Args:
            config: Application configuration
            data_dir: Directory for runtime data
        """
        self.config = config
        self.data_dir = data_dir

        # Initialize components
        self.bus = MessageBus()
        self.session_manager = SessionManager(max_messages=config.session.max_messages)

        # Initialize LLM provider
        self.provider = self._create_provider()

        # Initialize tools
        self.tools = self._create_tools()

        # Initialize skills loader
        self.skills_loader = SkillsLoader(workspace=data_dir)

        # Initialize agent loop
        self.agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            skills_loader=self.skills_loader,
            model=config.agent.model,
            max_tokens=config.agent.max_tokens,
            temperature=config.agent.temperature,
            enable_korean_review=config.agent.enable_korean_review,
            korean_review_model=config.agent.korean_review_model,
        )

        # Initialize Discord channel
        self.discord = DiscordChannel(
            config=config.discord,
            bus=self.bus,
            session_manager=self.session_manager,
            on_message_callback=self._handle_message,
        )

        self._running = False

    def _create_provider(self) -> OpenAICompatibleProvider:
        """Create LLM provider from config."""
        api_key = None
        api_base = None

        # Try providers in order: openrouter, anthropic, openai
        if self.config.providers.openrouter:
            api_key = self.config.providers.openrouter.api_key
            api_base = self.config.providers.openrouter.api_base
        elif self.config.providers.anthropic:
            api_key = self.config.providers.anthropic.api_key
            api_base = self.config.providers.anthropic.api_base
        elif self.config.providers.openai:
            api_key = self.config.providers.openai.api_key
            api_base = self.config.providers.openai.api_base

        if not api_key:
            raise ValueError("No LLM provider API key configured")

        return OpenAICompatibleProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=self.config.agent.model,
        )

    def _create_tools(self) -> ToolRegistry:
        """Create and register tools."""
        registry = ToolRegistry()
        registry.register(WebFetchTool())
        return registry

    async def _handle_message(self, session: Session, content: str) -> str | None:
        """
        Handle incoming message from Discord.

        Args:
            session: User session
            content: Message content

        Returns:
            Bot response or None
        """
        # Detect if input is in English (no Korean characters)
        skip_korean_review = not self.agent._detect_korean(content)

        if skip_korean_review:
            logger.debug("English input detected - Korean review will be skipped")

        return await self.agent.run_with_retry(
            session,
            content,
            max_retries=1,
            skip_korean_review=skip_korean_review
        )

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting Tokamak bot...")
        self._running = True

        # Start message bus dispatcher
        bus_task = asyncio.create_task(self.bus.dispatch_outbound())

        # Subscribe Discord to outbound messages
        self.bus.subscribe_outbound("discord", self.discord.send)

        # Start Discord (this blocks until disconnected)
        try:
            await self.discord.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
            bus_task.cancel()

    async def stop(self) -> None:
        """Stop all services."""
        logger.info("Stopping Tokamak bot...")
        self._running = False

        self.bus.stop()
        await self.discord.stop()

        logger.info("Tokamak bot stopped")
