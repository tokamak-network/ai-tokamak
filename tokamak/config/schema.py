"""Configuration schema using Pydantic."""

from pydantic import BaseModel, Field


class DiscordConfig(BaseModel):
    """Discord bot configuration."""

    token: str = Field(description="Discord bot token")
    monitor_channel_ids: list[int] = Field(
        default_factory=list, description="Channel IDs to monitor for conversations"
    )
    allow_guilds: list[int] = Field(
        default_factory=list, description="Guild IDs allowed (empty = all)"
    )
    conversation_timeout_seconds: int = Field(
        default=300, description="Seconds before conversation timeout (default 5 min)"
    )


class SessionConfig(BaseModel):
    """Session management configuration."""

    max_messages: int = Field(default=100, description="Maximum messages to store per session")


class ProviderConfig(BaseModel):
    """Single provider configuration."""

    api_key: str = Field(description="API key for the provider")
    api_base: str | None = Field(default=None, description="Custom API base URL")


class ProvidersConfig(BaseModel):
    """LLM providers configuration."""

    openrouter: ProviderConfig | None = None
    anthropic: ProviderConfig | None = None
    openai: ProviderConfig | None = None


class AgentConfig(BaseModel):
    """Agent configuration."""

    model: str = Field(default="anthropic/claude-sonnet-4", description="LLM model to use")
    max_tokens: int = Field(default=4096, description="Maximum tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    enable_korean_review: bool = Field(
        default=True, description="Enable Korean language quality review"
    )
    korean_review_model: str | None = Field(
        default=None,
        description="Model for Korean review (defaults to agent model if not specified)",
    )


class NewsFeedConfig(BaseModel):
    """News feed configuration for automated crypto news summaries."""

    enabled: bool = Field(default=False, description="Enable automated news feed")
    interval_seconds: int = Field(
        default=300, ge=30, description="News fetch interval in seconds (default 5 min)"
    )

    news_sources: list[str] = Field(
        default_factory=lambda: [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
        ],
        description="RSS feed URLs for news collection",
    )
    korean_channel_id: int | None = Field(
        default=None, description="Discord channel ID for Korean summaries"
    )
    english_channel_id: int | None = Field(
        default=None, description="Discord channel ID for English summaries"
    )
    max_news_per_fetch: int = Field(
        default=15, ge=5, le=50, description="Maximum news items to include in each summary"
    )
    summary_model: str | None = Field(
        default=None, description="Model for summarization (defaults to agent model)"
    )


class AdminConfig(BaseModel):
    """Admin configuration for LLM-based tool calling."""

    admin_channel_ids: list[int] = Field(
        default_factory=list,
        description="Channel IDs where admin commands are accepted",
    )


class TelegramConfig(BaseModel):
    """Telegram bot configuration for admin notifications."""

    enabled: bool = Field(default=False, description="Enable Telegram notifications")
    bot_token: str = Field(default="", description="Telegram bot token")
    admin_chat_id: int | None = Field(
        default=None, description="Telegram chat ID for admin notifications"
    )
    webhook_url: str | None = Field(default=None, description="Webhook URL for Telegram callbacks")
    webhook_port: int = Field(default=8443, description="Port for webhook server")


class ModerationConfig(BaseModel):
    """Content moderation configuration."""

    enabled: bool = Field(default=False, description="Enable content moderation")
    toxicity_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Threshold for toxicity detection (0-1)"
    )
    ban_duration_minutes: int = Field(
        default=60, description="Default ban duration in minutes (0 = permanent)"
    )


class Config(BaseModel):
    """Root configuration."""

    discord: DiscordConfig
    session: SessionConfig = Field(default_factory=SessionConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    news_feed: NewsFeedConfig = Field(default_factory=NewsFeedConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    moderation: ModerationConfig = Field(default_factory=ModerationConfig)
