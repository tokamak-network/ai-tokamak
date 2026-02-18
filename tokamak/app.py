"""Main application that integrates all components."""

import asyncio
from pathlib import Path

from loguru import logger

from tokamak.admin import AdminHandler
from tokamak.agent import AgentLoop
from tokamak.agent.tools import InternalStateTool, ToolRegistry, WebFetchTool
from tokamak.bus import MessageBus
from tokamak.channels import DiscordChannel
from tokamak.config import Config
from tokamak.cron.service import CronService
from tokamak.cron.types import CronSchedule
from tokamak.news import NewsFeedService, NewsFetcher, NewsSummarizer
from tokamak.providers import OpenAICompatibleProvider
from tokamak.session import Session, SessionManager


class TokamakApp:
    """Main application orchestrating all components."""

    def __init__(self, config: Config, data_dir: Path = Path("data")):
        self.config = config
        self.data_dir = data_dir

        self.bus = MessageBus()
        self.session_manager = SessionManager(max_messages=config.session.max_messages)

        self.provider = self._create_provider()

        self.tools = self._create_tools()

        self.agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            model=config.agent.model,
            max_tokens=config.agent.max_tokens,
            temperature=config.agent.temperature,
            enable_korean_review=config.agent.enable_korean_review,
            korean_review_model=config.agent.korean_review_model,
        )

        self.admin_handler: AdminHandler | None = None
        if config.admin.admin_channel_ids:
            self.admin_handler = AdminHandler(config.admin, self)

        self.discord = DiscordChannel(
            config=config.discord,
            bus=self.bus,
            session_manager=self.session_manager,
            on_message_callback=self._handle_message,
            admin_handler=self.admin_handler,
        )

        self._running = False
        self.cron: CronService | None = None
        self.news_feed: NewsFeedService | None = None

        if config.news_feed.enabled:
            self.news_feed = self._create_news_feed()

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
        registry = ToolRegistry()

        auth_tokens = {}
        if self.config.discord.token:
            auth_tokens["discord"] = self.config.discord.token

        registry.register(WebFetchTool(auth_tokens=auth_tokens))
        registry.register(InternalStateTool())

        return registry

    def _create_news_feed(self) -> NewsFeedService:
        """Create news feed service."""
        news_config = self.config.news_feed
        fetcher = NewsFetcher(sources=news_config.news_sources)
        summarizer = NewsSummarizer(
            provider=self.provider,
            model=news_config.summary_model or self.config.agent.model,
        )
        return NewsFeedService(
            fetcher=fetcher,
            summarizer=summarizer,
            bus=self.bus,
            state_path=self.data_dir / "news_state.json",
            korean_channel_id=news_config.korean_channel_id,
            english_channel_id=news_config.english_channel_id,
            max_news_per_fetch=news_config.max_news_per_fetch,
        )

    async def _handle_message(self, session: Session, content: str) -> str | None:
        """
        Handle incoming message from Discord.

        Args:
            session: User session
            content: Message content

        Returns:
            Bot response or None
        """
        return await self.agent.run_with_retry(
            session,
            content,
            max_retries=1,
        )

    async def _periodic_cleanup(self, interval_seconds: int = 600) -> None:
        """Periodically clean up stale sessions and expired conversations."""
        while self._running:
            await asyncio.sleep(interval_seconds)
            try:
                removed_sessions = self.session_manager.cleanup_stale(max_age_seconds=3600)
                removed_convos = self.discord.cleanup_expired_conversations()
                if removed_sessions or removed_convos:
                    logger.info(
                        f"Cleanup: removed {removed_sessions} stale sessions, "
                        f"{removed_convos} expired conversations"
                    )
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting Tokamak bot...")
        self._running = True

        bus_task = asyncio.create_task(self.bus.dispatch_outbound())
        cleanup_task = asyncio.create_task(self._periodic_cleanup())

        self.bus.subscribe_outbound("discord", self.discord.send)

        if self.news_feed:
            news_feed = self.news_feed
            self.cron = CronService(
                store_path=self.data_dir / "cron.json",
                on_job=lambda job: news_feed.run(job),
            )
            await self.cron.start()
            self.cron.add_job(
                name="news_feed",
                schedule=CronSchedule(
                    kind="every",
                    every_ms=self.config.news_feed.interval_seconds * 1000,
                ),
                message="news_feed",
            )

        try:
            await self.discord.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
            bus_task.cancel()
            cleanup_task.cancel()

    async def stop(self) -> None:
        """Stop all services (safe to call multiple times)."""
        if not self._running:
            return
        logger.info("Stopping Tokamak bot...")
        self._running = False

        if self.cron:
            self.cron.stop()

        self.bus.stop()
        await self.discord.stop()

        logger.info("Tokamak bot stopped")
