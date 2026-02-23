"""Telegram channel implementation with inline buttons for admin actions."""

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from loguru import logger

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Application = None
    ContextTypes = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Update = None

from tokamak.bus.events import OutboundMessage
from tokamak.bus.queue import MessageBus
from tokamak.channels.base import BaseChannel
from tokamak.config.schema import TelegramConfig

if TYPE_CHECKING:
    from tokamak.moderation.types import ToxicContentEvent


class TelegramChannel(BaseChannel):
    """Telegram channel for admin notifications with inline buttons."""

    name = "telegram"

    def __init__(
        self,
        config: TelegramConfig,
        bus: MessageBus,
        on_ban_callback: Callable[["ToxicContentEvent"], Awaitable[None]] | None = None,
        on_dismiss_callback: Callable[["ToxicContentEvent"], Awaitable[None]] | None = None,
        store_path: Path | None = None,
    ):
        """
        Initialize Telegram channel.

        Args:
            config: Telegram configuration
            bus: Message bus for communication
            on_ban_callback: Async callback(event: ToxicContentEvent) for ban action
            on_dismiss_callback: Async callback(event: ToxicContentEvent) for dismiss action
            store_path: Path for persisting pending events
        """
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError(
                "python-telegram-bot not installed. Run: pip install python-telegram-bot"
            )

        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.on_ban_callback = on_ban_callback
        self.on_dismiss_callback = on_dismiss_callback
        self.store_path = store_path

        self._app: Application | None = None
        self._pending_events: dict[str, "ToxicContentEvent"] = {}
        self._load_pending_events()

    async def start(self) -> None:
        """Start the Telegram bot with webhook."""
        if not self.config.enabled:
            logger.info("Telegram notifications disabled")
            return

        logger.info("Starting Telegram channel...")

        self._app = Application.builder().token(self.config.bot_token).build()

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))

        # Start webhook or polling
        if self.config.webhook_url:
            await self._app.bot.set_webhook(
                url=self.config.webhook_url,
                port=self.config.webhook_port,
            )
            await self._app.start()
            logger.info(f"Telegram webhook set: {self.config.webhook_url}")
        else:
            # Fallback to polling for development
            await self._app.initialize()
            await self._app.start()
            if self._app.updater:
                await self._app.updater.start_polling()
            logger.info("Telegram bot started in polling mode")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            if self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        logger.info("Telegram channel stopped")

    async def _handle_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /start command."""
        if update.effective_chat and update.message:
            await update.message.reply_text(
                "🤖 Tokamak 관리자 봇\n\n"
                "이 봇은 유해 콘텐츠 감지 알림을 받습니다.\n"
                "Discord에서 문제가 감지되면 여기로 알림이 전송됩니다."
            )

    async def _handle_callback(
        self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"
    ) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        callback_data = query.data
        if not callback_data:
            return

        parts = callback_data.split(":", 1)
        if len(parts) != 2:
            return

        action, event_id = parts
        event = self._pending_events.get(event_id, None)

        if not event:
            await query.edit_message_text("⚠️ 이미 처리된 요청입니다.")
            return

        if action == "ban":
            await query.edit_message_text(
                f"✅ 사용자 차단 처리 중...\n사용자: {event.user_name} ({event.user_id})"
            )
            if self.on_ban_callback:
                try:
                    await self.on_ban_callback(event)

                    cancelled_count = self._cancel_pending_events_for_user(
                        guild_id=event.guild_id,
                        user_id=event.user_id,
                        exclude_event_id=event_id,
                    )

                    self._pending_events.pop(event_id, None)
                    self._save_pending_events()

                    msg = f"✅ 차단 완료\n사용자: {event.user_name} ({event.user_id})"
                    if cancelled_count > 0:
                        msg += f"\n📋 다른 {cancelled_count}개의 대기 중인 알림이 취소되었습니다."
                    await query.edit_message_text(msg)

                except Exception as e:
                    logger.error(f"Ban callback error: {e}")
                    await query.edit_message_text(
                        f"❌ 차단 실패: {e}\n⚠️ 이벤트가 대기열에 유지됩니다. 다시 시도해주세요."
                    )
            else:
                self._pending_events.pop(event_id, None)
                self._save_pending_events()
                await query.edit_message_text("⚠️ 차단 콜백이 설정되지 않았습니다.")

        elif action == "dismiss":
            self._pending_events.pop(event_id, None)
            self._save_pending_events()

            await query.edit_message_text(
                f"📋 요청이 무시되었습니다.\n사용자: {event.user_name} ({event.user_id})"
            )
            if self.on_dismiss_callback:
                try:
                    await self.on_dismiss_callback(event)
                except Exception as e:
                    logger.error(f"Dismiss callback error: {e}")

    def _cancel_pending_events_for_user(
        self,
        guild_id: int,
        user_id: int,
        exclude_event_id: str | None = None,
    ) -> int:
        """
        Cancel all pending events for a specific user in a guild.

        Args:
            guild_id: The guild ID
            user_id: The user ID
            exclude_event_id: Event ID to exclude from cancellation

        Returns:
            Number of events cancelled
        """
        keys_to_remove = [
            eid
            for eid, evt in self._pending_events.items()
            if evt.guild_id == guild_id and evt.user_id == user_id and eid != exclude_event_id
        ]

        for key in keys_to_remove:
            del self._pending_events[key]

        return len(keys_to_remove)

    def _generate_event_id(self, event: "ToxicContentEvent") -> str:
        """Generate unique ID for callback tracking."""
        data = f"{event.guild_id}:{event.user_id}:{event.message_id}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def _load_pending_events(self) -> None:
        """Load pending events from disk."""
        if not self.store_path or not self.store_path.exists():
            return

        try:
            from tokamak.moderation.types import ToxicContentEvent

            data = json.loads(self.store_path.read_text())
            for event_id, event_data in data.get("pending_events", {}).items():
                self._pending_events[event_id] = ToxicContentEvent.from_dict(event_data)
            if self._pending_events:
                logger.info(f"Loaded {len(self._pending_events)} pending moderation events")
        except Exception as e:
            logger.warning(f"Failed to load pending events: {e}")

    def _save_pending_events(self) -> None:
        """Save pending events to disk."""
        if not self.store_path:
            return

        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "pending_events": {
                event_id: event.to_dict() for event_id, event in self._pending_events.items()
            }
        }

        self.store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    async def send_toxic_alert(self, event: "ToxicContentEvent") -> None:
        """
        Send a toxic content alert with inline buttons.

        Args:
            event: The toxic content event to report
        """
        if not self._app or not self.config.admin_chat_id:
            logger.warning("Telegram not configured or not started")
            return

        event_id = self._generate_event_id(event)

        if event_id in self._pending_events:
            logger.warning(
                f"Event {event_id} already pending for user {event.user_id}, "
                "skipping duplicate alert"
            )
            return

        self._pending_events[event_id] = event
        self._save_pending_events()

        severity_emoji = {
            "low": "⚠️",
            "medium": "🔶",
            "high": "🔴",
        }
        emoji = severity_emoji.get(str(event.severity) if event.severity else "low", "⚠️")

        message = (
            f"{emoji} **유해 콘텐츠 감지**\n\n"
            f"**사용자**: {event.user_name} (`{event.user_id}`)\n"
            f"**채널 ID**: `{event.channel_id}`\n"
            f"**심각도**: {event.severity or 'low'}\n"
            f"**카테고리**: {event.category or 'unknown'}\n"
            f"**사유**: {event.reason or 'N/A'}\n\n"
            f"**메시지**:\n```\n{event.message_content[:500]}{'...' if len(event.message_content) > 500 else ''}\n```"
        )

        keyboard = [
            [
                InlineKeyboardButton("🚫 즉시 차단", callback_data=f"ban:{event_id}"),
                InlineKeyboardButton("✓ 무시", callback_data=f"dismiss:{event_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await self._app.bot.send_message(
                chat_id=self.config.admin_chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            logger.info(f"Sent toxic alert to Telegram for user {event.user_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message to Telegram (generic send method for bus compatibility).

        Args:
            msg: Outbound message with chat_id as Telegram chat ID
        """
        if not self._app:
            return

        try:
            chat_id = int(msg.chat_id)
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=msg.content,
                parse_mode="Markdown",
            )
            logger.debug(f"Sent message to Telegram chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
