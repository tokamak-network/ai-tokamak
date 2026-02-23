"""Ban handler for executing Discord bans from Telegram callbacks."""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from loguru import logger

from tokamak.config.schema import ModerationConfig
from tokamak.moderation.types import ToxicContentEvent


class BanHandler:
    """Handles ban actions on Discord server."""

    def __init__(
        self,
        discord_client: discord.Client,
        config: ModerationConfig,
    ):
        """
        Initialize ban handler.

        Args:
            discord_client: Discord client instance
            config: Moderation configuration
        """
        self.discord_client = discord_client
        self.config = config

    async def execute_ban(self, event: ToxicContentEvent) -> bool:
        """
        Execute ban/timeout on the user.

        Args:
            event: The toxic content event with user details

        Returns:
            True if ban was successful, False otherwise
        """
        try:
            guild = self.discord_client.get_guild(event.guild_id)
            if not guild:
                logger.error(f"Guild {event.guild_id} not found")
                return False

            member = guild.get_member(event.user_id)
            if not member:
                # Try to fetch member if not in cache
                try:
                    member = await guild.fetch_member(event.user_id)
                except discord.NotFound:
                    logger.error(f"Member {event.user_id} not found in guild")
                    return False

            ban_duration = self.config.ban_duration_minutes

            if ban_duration == 0:
                # Permanent ban
                await guild.ban(
                    member,
                    reason=f"유해 콘텐츠: {event.category or 'unknown'} - {event.reason}",
                )
                logger.info(f"Permanently banned user {event.user_name} ({event.user_id})")
            else:
                # Timeout
                until = datetime.now(timezone.utc) + timedelta(minutes=ban_duration)
                await member.timeout(
                    until,
                    reason=f"유해 콘텐츠: {event.category or 'unknown'} - {event.reason}",
                )
                logger.info(
                    f"Timed out user {event.user_name} ({event.user_id}) "
                    f"for {ban_duration} minutes"
                )

            return True

        except discord.Forbidden:
            logger.error(f"Missing permissions to ban user {event.user_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to ban user {event.user_id}: {e}")
            return False

    async def execute_timeout(
        self,
        event: ToxicContentEvent,
        duration_minutes: int,
    ) -> bool:
        """
        Execute timeout on the user.

        Args:
            event: The toxic content event with user details
            duration_minutes: Timeout duration in minutes

        Returns:
            True if timeout was successful, False otherwise
        """
        try:
            guild = self.discord_client.get_guild(event.guild_id)
            if not guild:
                return False

            member = guild.get_member(event.user_id)
            if not member:
                try:
                    member = await guild.fetch_member(event.user_id)
                except discord.NotFound:
                    return False

            until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            await member.timeout(
                until,
                reason=f"유해 콘텐츠: {event.category or 'unknown'}",
            )
            logger.info(f"Timed out user {event.user_name} for {duration_minutes} minutes")
            return True

        except Exception as e:
            logger.error(f"Failed to timeout user: {e}")
            return False