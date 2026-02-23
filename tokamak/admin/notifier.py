"""Admin notification service for toxic content alerts."""

from typing import TYPE_CHECKING

from loguru import logger

from tokamak.config.schema import Config
from tokamak.moderation.types import ToxicContentEvent

if TYPE_CHECKING:
    from tokamak.channels.telegram import TelegramChannel


class AdminNotifier:
    """Sends admin notifications for toxic content events."""

    def __init__(
        self,
        config: Config,
        telegram_channel: "TelegramChannel | None" = None,
    ):
        """
        Initialize admin notifier.

        Args:
            config: Application configuration
            telegram_channel: Telegram channel for notifications (optional)
        """
        self.config = config
        self.telegram_channel = telegram_channel

    async def notify_toxic_content(self, event: ToxicContentEvent) -> None:
        """
        Send notifications to all configured admin channels.

        Args:
            event: The toxic content event to report
        """
        logger.info(
            f"Notifying toxic content: user={event.user_name}, "
            f"severity={event.severity}, channel={event.channel_id}"
        )

        # Send to Telegram if configured
        if self.telegram_channel and self.config.telegram.enabled:
            try:
                await self.telegram_channel.send_toxic_alert(event)
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")

        # Note: Discord admin channel notification can be added here
        # by publishing to MessageBus with appropriate channel ID

    async def notify_ban_executed(self, event: ToxicContentEvent, success: bool) -> None:
        """
        Notify about ban execution result.

        Args:
            event: The original toxic content event
            success: Whether the ban was successful
        """
        status = "완료" if success else "실패"
        logger.info(f"Ban {status} for user {event.user_name} ({event.user_id})")

        # Could send confirmation to Discord admin channel here