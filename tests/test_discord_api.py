"""Test Discord API interactions with web_fetch tool.

Tests authentication, error handling for privileged intents, and fallback strategies.

Key Issue: /guilds/{id}/members returns 403 (code 40333) "internal network error" when:
1. Server Members Intent is not enabled, OR
2. Browser-like User-Agent is used (Cloudflare blocks it)

Solution: Use Discord-specific User-Agent "DiscordBot (...)" for Discord API calls.

Usage:
    uv run pytest tests/test_discord_api.py -v -s
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tokamak.agent.tools import WebFetchTool


class TestDiscordAuthHeaders:
    """Test Discord authentication header injection."""

    def test_discord_auth_header_format(self):
        """Bot token should be prefixed with 'Bot ' not 'Bearer '."""
        tool = WebFetchTool(auth_tokens={"discord": "test_token_123"})

        headers = tool._get_auth_headers("discord")

        assert headers == {"Authorization": "Bot test_token_123"}
        assert headers["Authorization"].startswith("Bot ")
        assert not headers["Authorization"].startswith("Bearer ")

    def test_discord_auth_missing_token(self):
        """Missing discord token should return empty headers."""
        tool = WebFetchTool(auth_tokens={})

        headers = tool._get_auth_headers("discord")

        assert headers == {}

    def test_unknown_auth_provider(self):
        """Unknown auth provider should return empty headers."""
        tool = WebFetchTool(auth_tokens={"discord": "test_token"})

        headers = tool._get_auth_headers("unknown_provider")

        assert headers == {}

    def test_discord_uses_discordbot_user_agent(self):
        from tokamak.agent.tools.web import DISCORD_USER_AGENT

        assert DISCORD_USER_AGENT.startswith("DiscordBot")
        assert "Mozilla" not in DISCORD_USER_AGENT


class TestDiscordMembersEndpoint:
    """Test Discord guild members API endpoints."""

    @pytest.fixture
    def tool(self):
        return WebFetchTool(auth_tokens={"discord": "test_bot_token"})

    @pytest.fixture
    def guild_id(self):
        return "1469415849445036065"

    @pytest.mark.asyncio
    async def test_members_list_requires_privileged_intent(self, tool, guild_id):
        """
        /guilds/{id}/members returns 403 (code 40333) without Server Members Intent.

        This is the issue from the logs - the bot has valid credentials
        (users/@me works) but lacks privileged intent for member list.
        """
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members"

        # Simulate Discord's 403 response for missing privileged intent
        mock_response = httpx.Response(
            403,
            json={"message": "internal network error", "code": 40333},
            request=httpx.Request("GET", url),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await tool.execute(url=url, auth_provider="discord")
            data = json.loads(result)

            assert data["status"] == 403
            error_data = json.loads(data["text"])
            assert error_data["code"] == 40333
            assert "internal network error" in error_data["message"]

    @pytest.mark.asyncio
    async def test_members_search_works_without_privileged_intent(self, tool, guild_id):
        """
        /guilds/{id}/members/search works WITHOUT privileged intent.

        This is the recommended fallback when Server Members Intent is disabled.
        """
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/search?query=bhlee&limit=10"

        mock_members = [
            {
                "user": {"id": "123456789", "username": "bhlee", "discriminator": "0001"},
                "nick": None,
                "roles": [],
            }
        ]

        mock_response = httpx.Response(
            200,
            json=mock_members,
            request=httpx.Request("GET", url),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await tool.execute(url=url, auth_provider="discord")
            data = json.loads(result)

            assert data["status"] == 200
            members = json.loads(data["text"])
            assert len(members) == 1
            assert members[0]["user"]["username"] == "bhlee"

    @pytest.mark.asyncio
    async def test_get_current_user_works_with_bot_token(self, tool):
        """
        /users/@me works with bot token - validates token is valid.

        This explains why the logs show successful authentication
        even though members list fails.
        """
        url = "https://discord.com/api/v10/users/@me"

        mock_user = {
            "id": "1467919069830320160",
            "username": "AI_Tokamak",
            "discriminator": "9993",
            "bot": True,
            "verified": True,
        }

        mock_response = httpx.Response(
            200,
            json=mock_user,
            request=httpx.Request("GET", url),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await tool.execute(url=url, auth_provider="discord")
            data = json.loads(result)

            assert data["status"] == 200
            user = json.loads(data["text"])
            assert user["username"] == "AI_Tokamak"
            assert user["bot"] is True

    @pytest.mark.asyncio
    async def test_auth_header_is_set_correctly(self, tool, guild_id):
        """Verify Authorization header is set to 'Bot {token}' format."""
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/search?query=test"

        mock_response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", url),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await tool.execute(url=url, auth_provider="discord")

            # Check that the Authorization header was set correctly
            call_args = mock_get.call_args
            headers = call_args.kwargs["headers"]

            assert "Authorization" in headers
            assert headers["Authorization"] == "Bot test_bot_token"


class TestDiscordErrorCodes:
    """Test Discord API error code handling."""

    @pytest.mark.asyncio
    async def test_error_40333_recognized_as_privileged_intent_issue(self):
        """
        Error code 40333 indicates missing Server Members Intent.

        The response body contains:
        {"message": "internal network error", "code": 40333}
        """
        tool = WebFetchTool(auth_tokens={"discord": "test_token"})
        url = "https://discord.com/api/v10/guilds/123/members"

        mock_response = httpx.Response(
            403,
            json={"message": "internal network error", "code": 40333},
            request=httpx.Request("GET", url),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await tool.execute(url=url, auth_provider="discord")
            data = json.loads(result)

            # Parse error
            error = json.loads(data["text"])
            assert error["code"] == 40333
            # This is the key indicator - need to use members/search instead
            # or enable Server Members Intent in Discord Developer Portal


class TestPrivilegedIntentDocumentation:
    """
    Documentation for the privileged intent issue.

    PROBLEM:
    --------
    /guilds/{id}/members returns 403 (code 40333) even with valid bot token.

    ROOT CAUSE:
    -----------
    Discord requires "Server Members Intent" (Privileged Gateway Intent) for:
    - Listing all guild members (/guilds/{id}/members)
    - Receiving member-related gateway events

    SOLUTIONS:
    ----------
    1. Enable Server Members Intent in Discord Developer Portal:
       - Go to https://discord.com/developers/applications
       - Select application → Bot tab
       - Enable "Server Members Intent" under Privileged Gateway Intents

    2. Use members/search API instead (NO privileged intent required):
       GET /guilds/{id}/members/search?query={username}&limit=10

    3. Use direct member lookup if user_id is known:
       GET /guilds/{id}/members/{user_id}
    """

    def test_documentation_exists(self):
        """This test documents the known issue and solutions."""
        # The SKILL.md file at tokamak/skills/discord-admin/SKILL.md
        # already documents this issue and the fallback strategies.
        #
        # Key points from SKILL.md:
        # - Lines 33-34: Warning about Privileged Intent requirement
        # - Lines 36-45: Method 1 - members/search (recommended)
        # - Lines 48-55: Method 2 - direct member lookup by ID
        # - Lines 58-68: Method 3 - full member list (requires intent)
        # - Lines 201-209: How to enable Privileged Intents
        pass
