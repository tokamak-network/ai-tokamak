"""Discord channel implementation."""

import re
import random
import time
from typing import Callable, Awaitable

import discord
from discord import Intents, Message
from loguru import logger

from tokamak.bus.events import OutboundMessage
from tokamak.bus.queue import MessageBus
from tokamak.channels.base import BaseChannel
from tokamak.config.schema import DiscordConfig
from tokamak.session import Session, SessionManager


def format_discord_message(content: str) -> str:
    """
    Format message for Discord by removing unsupported markdown and fixing links.

    Args:
        content: Raw message content

    Returns:
        Formatted message content
    """
    # Remove horizontal rules (---)
    content = re.sub(r'\n---+\n', '\n\n', content)
    content = re.sub(r'^---+$', '', content, flags=re.MULTILINE)

    # Step 1: Protect masked links [text](url) by replacing with placeholders
    masked_links = []
    markdown_link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'

    def protect_masked_link(match):
        text = match.group(1)
        url = match.group(2).strip('<>') # strip existing angle brackets if any
        masked_links.append((text, url))
        return f'__MASKED_LINK_{len(masked_links) - 1}__'

    content = re.sub(markdown_link_pattern, protect_masked_link, content)

    # Step 2: Convert bare URLs to <URL> format (to prevent embeds)
    def replace_bare_urls(match):
        return f'<{match.group(0)}>'

    url_pattern = r'(?<!<)https?://[^\s<>]+(?!>)'
    content = re.sub(url_pattern, replace_bare_urls, content)

    # Step 3: Restore masked links with [text](<url>) format to prevent embeds
    for i, (text, url) in enumerate(masked_links):
        content = content.replace(f'__MASKED_LINK_{i}__', f'[{text}](<{url}>)')

    # Replace multiple consecutive newlines with double newline (single blank line)
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


class DiscordChannel(BaseChannel):
    """Discord channel implementation with conversation tracking."""

    name = "discord"

    def __init__(
        self,
        config: DiscordConfig,
        bus: MessageBus,
        session_manager: SessionManager,
        on_message_callback: Callable[[Session, str], Awaitable[str | None]] | None = None,
    ):
        """
        Initialize Discord channel.

        Args:
            config: Discord configuration
            bus: Message bus for communication
            session_manager: Session manager for conversation history
            on_message_callback: Async callback(session, content) -> response
        """
        super().__init__(config, bus)
        self.config: DiscordConfig = config
        self.session_manager = session_manager
        self.on_message_callback = on_message_callback

        # Active conversation tracking: {user_key: last_message_timestamp}
        self._active_conversations: dict[str, float] = {}

        # Discord client setup
        intents = Intents.default()
        intents.message_content = True
        intents.guilds = True

        self._client = discord.Client(intents=intents)
        self._setup_events()

    def _setup_events(self) -> None:
        """Setup Discord event handlers."""

        @self._client.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self._client.user}")
            self._running = True

        @self._client.event
        async def on_message(message: Message):
            await self._on_message(message)

    async def start(self) -> None:
        """Start the Discord client."""
        logger.info("Starting Discord channel...")
        await self._client.start(self.config.token)

    async def stop(self) -> None:
        """Stop the Discord client."""
        self._running = False
        await self._client.close()
        logger.info("Discord channel stopped")

    def _get_session_key(self, guild_id: int, user_id: int) -> str:
        """Generate session key for a user in a guild."""
        return f"discord:{guild_id}:{user_id}"

    def _get_user_key(self, guild_id: int, user_id: int) -> str:
        """Generate user key for active conversation tracking."""
        return f"{guild_id}:{user_id}"

    def _is_bot_mentioned(self, message: Message) -> bool:
        """Check if the bot is mentioned in the message."""
        if not self._client.user:
            return False
        return self._client.user in message.mentions

    def _is_monitored_channel(self, channel_id: int) -> bool:
        """Check if channel is in the monitor list."""
        # If no channels specified, monitor all
        if not self.config.monitor_channel_ids:
            return True
        return channel_id in self.config.monitor_channel_ids

    def _is_allowed_guild(self, guild_id: int) -> bool:
        """Check if guild is allowed."""
        # If no guilds specified, allow all
        if not self.config.allow_guilds:
            return True
        return guild_id in self.config.allow_guilds

    def should_respond(self, user_key: str, is_mention: bool) -> bool:
        """
        Determine whether to respond to a message.

        Args:
            user_key: Unique key for the user (guild:user)
            is_mention: Whether the bot was mentioned

        Returns:
            True if should respond, False otherwise
        """
        now = time.time()
        timeout = self.config.conversation_timeout_seconds

        # 1. Check if user has active conversation
        if user_key in self._active_conversations:
            last_time = self._active_conversations[user_key]
            if now - last_time < timeout:
                # Still within timeout - continue conversation
                self._active_conversations[user_key] = now
                return True
            else:
                # Timeout expired - end conversation
                del self._active_conversations[user_key]

        # 2. Always respond to mentions
        if is_mention:
            self._active_conversations[user_key] = now
            return True

        # 3. Random probability for starting new conversation
        if random.random() < self.config.response_probability:
            self._active_conversations[user_key] = now
            return True

        return False

    async def _on_message(self, message: Message) -> None:
        """Handle incoming Discord message."""
        # Ignore bot's own messages
        if message.author == self._client.user:
            return

        # Ignore DMs (no guild)
        if not message.guild:
            return

        # Check guild allowlist
        if not self._is_allowed_guild(message.guild.id):
            return

        # Check if channel is monitored
        if not self._is_monitored_channel(message.channel.id):
            return

        guild_id = message.guild.id
        user_id = message.author.id
        user_key = self._get_user_key(guild_id, user_id)
        session_key = self._get_session_key(guild_id, user_id)
        content = message.content.strip()

        # Skip empty messages
        if not content:
            return

        # Get or create session
        session = self.session_manager.get_or_create(session_key)

        # Check if session was ended
        is_mention = self._is_bot_mentioned(message)
        if session.is_ended and (is_mention or random.random() < self.config.response_probability):
            # Reactivate session for new conversation
            session.reactivate()
            logger.info(f"Reactivating session for {user_key}")

        # Always save user message to session (for context)
        session.add_message(
            role="user",
            content=content,
            author_name=message.author.display_name,
            message_id=str(message.id),
        )

        # Check if we should respond (skip if session is ended)
        if session.is_ended:
            logger.debug(f"Session ended for {user_key}, not responding")
            return

        if not self.should_respond(user_key, is_mention):
            logger.debug(f"Not responding to {user_key}")
            return

        logger.info(f"Responding to {message.author.display_name} in {message.channel}")

        # Call the message callback if set
        if self.on_message_callback:
            try:
                response = await self.on_message_callback(session, content)
                if response:
                    # Save bot response to session
                    session.add_message(role="assistant", content=response)
                    # Format and send response using reply
                    formatted_response = format_discord_message(response)
                    await message.reply(formatted_response)

                    # If session was ended, remove from active conversations
                    if session.is_ended:
                        if user_key in self._active_conversations:
                            del self._active_conversations[user_key]
                            logger.info(f"Removed {user_key} from active conversations (session ended)")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
        else:
            # Fallback: publish to message bus
            await self._handle_message(
                sender_id=str(user_id),
                chat_id=str(message.channel.id),
                content=content,
                metadata={
                    "guild_id": str(guild_id),
                    "author_name": message.author.display_name,
                    "message_id": str(message.id),
                    "session_key": session_key,
                }
            )

    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message to Discord.

        Args:
            msg: Outbound message with chat_id as channel ID
        """
        try:
            channel_id = int(msg.chat_id)
            channel = self._client.get_channel(channel_id)

            if not channel:
                channel = await self._client.fetch_channel(channel_id)

            if channel and hasattr(channel, "send"):
                formatted_content = format_discord_message(msg.content)
                await channel.send(formatted_content)
                logger.debug(f"Sent message to channel {channel_id}")
            else:
                logger.error(f"Channel {channel_id} not found or not sendable")

        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")


    @property
    def client(self) -> discord.Client:
        """Get the Discord client instance."""
        return self._client

    @property
    def active_conversation_count(self) -> int:
        """Get number of active conversations."""
        return len(self._active_conversations)
