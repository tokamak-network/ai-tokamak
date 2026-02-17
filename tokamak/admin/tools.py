"""Admin tools for LLM function calling."""

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import discord

from loguru import logger

from tokamak.agent.tools.base import Tool

if TYPE_CHECKING:
    from tokamak.app import TokamakApp


async def resolve_member(guild: discord.Guild, user_ref: str) -> discord.Member | None:
    """Resolve a member by ID or name.

    Search order:
    1. If numeric, try as ID
    2. Try get_member_named (username#discriminator or nickname)
    3. Search in cache (display_name, name, global_name)
    4. Fallback: query_members API call
    """
    if user_ref.isdigit():
        member = guild.get_member(int(user_ref))
        if member:
            return member
        try:
            return await guild.fetch_member(int(user_ref))
        except Exception:
            pass

    member = guild.get_member_named(user_ref)
    if member:
        return member

    user_lower = user_ref.lower()
    for m in guild.members:
        if (
            m.display_name.lower() == user_lower
            or m.name.lower() == user_lower
            or (m.global_name and m.global_name.lower() == user_lower)
        ):
            return m

    try:
        members = await guild.query_members(query=user_ref, limit=1)
        if members:
            return members[0]
    except Exception:
        pass

    return None


async def resolve_channel(guild: discord.Guild, channel_ref: str) -> discord.TextChannel | None:
    """Resolve a text channel by ID or name."""
    if channel_ref.isdigit():
        channel = guild.get_channel(int(channel_ref))
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    channel = discord.utils.get(guild.text_channels, name=channel_ref)
    return channel


class SearchUserTool(Tool):
    """Search for a user in the guild."""

    @property
    def name(self) -> str:
        return "search_user"

    @property
    def description(self) -> str:
        return "서버에서 사용자를 검색합니다. 사용자 ID, 사용자명, 닉네임, 표시 이름으로 검색할 수 있습니다. timeout, untimeout 등의 도구를 사용하기 전에 사용자 ID를 확인할 때 유용합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 사용자 ID, 사용자명, 닉네임 또는 표시 이름 (부분 일치 가능)",
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 검색 결과 수 (기본값: 5, 최대: 20)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        guild: discord.Guild | None = kwargs.get("_guild")
        if not guild:
            return '{"error": "서버 정보를 찾을 수 없습니다."}'

        query = kwargs.get("query", "").strip()
        if not query:
            return '{"error": "검색어를 입력해주세요."}'

        limit = min(kwargs.get("limit", 5), 20)
        results = []

        query_lower = query.lower()
        for member in guild.members:
            score = 0
            matched_field = ""

            if member.id == int(query) if query.isdigit() else False:
                score = 100
                matched_field = "id"
            elif member.display_name.lower() == query_lower:
                score = 90
                matched_field = "display_name"
            elif member.name.lower() == query_lower:
                score = 85
                matched_field = "username"
            elif member.display_name.lower().startswith(query_lower):
                score = 70
                matched_field = "display_name"
            elif member.name.lower().startswith(query_lower):
                score = 65
                matched_field = "username"
            elif query_lower in member.display_name.lower():
                score = 50
                matched_field = "display_name"
            elif query_lower in member.name.lower():
                score = 45
                matched_field = "username"
            elif member.global_name and query_lower in member.global_name.lower():
                score = 40
                matched_field = "global_name"

            if score > 0:
                results.append({
                    "score": score,
                    "user_id": str(member.id),
                    "username": member.name,
                    "display_name": member.display_name,
                    "matched_field": matched_field,
                })

        if not results and not query.isdigit():
            try:
                api_members = await guild.query_members(query=query, limit=limit)
                for member in api_members:
                    results.append({
                        "score": 30,
                        "user_id": str(member.id),
                        "username": member.name,
                        "display_name": member.display_name,
                        "matched_field": "api_search",
                    })
            except Exception:
                pass

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]

        if not results:
            return json.dumps({"success": True, "users": [], "message": f"'{query}'와 일치하는 사용자를 찾을 수 없습니다."}, ensure_ascii=False)

        return json.dumps({"success": True, "users": results}, ensure_ascii=False)


class SearchChannelTool(Tool):
    """Search for a channel in the guild."""

    @property
    def name(self) -> str:
        return "search_channel"

    @property
    def description(self) -> str:
        return "서버에서 채널을 검색합니다. 채널 ID 또는 채널명으로 검색할 수 있습니다. broadcast_message 도구를 사용하기 전에 채널 ID를 확인할 때 유용합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 채널 ID 또는 채널명",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        guild: discord.Guild | None = kwargs.get("_guild")
        if not guild:
            return '{"error": "서버 정보를 찾을 수 없습니다."}'

        query = kwargs.get("query", "").strip()
        if not query:
            return '{"error": "검색어를 입력해주세요."}'

        results = []
        query_lower = query.lower()

        for channel in guild.text_channels:
            score = 0

            if query.isdigit() and channel.id == int(query):
                score = 100
            elif channel.name.lower() == query_lower:
                score = 90
            elif channel.name.lower().startswith(query_lower):
                score = 70
            elif query_lower in channel.name.lower():
                score = 50

            if score > 0:
                results.append({
                    "score": score,
                    "channel_id": str(channel.id),
                    "name": channel.name,
                    "topic": channel.topic or "",
                })

        results.sort(key=lambda x: x["score"], reverse=True)

        if not results:
            return json.dumps({"success": True, "channels": [], "message": f"'{query}'와 일치하는 채널을 찾을 수 없습니다."}, ensure_ascii=False)

        return json.dumps({"success": True, "channels": results}, ensure_ascii=False)


class TimeoutTool(Tool):
    """Timeout a user in the guild."""

    @property
    def name(self) -> str:
        return "timeout_user"

    @property
    def description(self) -> str:
        return "Discord 서버에서 특정 사용자를 지정된 시간 동안 타임아웃(차단)합니다. 사용자가 메시지를 보내거나 음성 채널에 참여할 수 없게 됩니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_ref": {
                    "type": "string",
                    "description": "타임아웃할 사용자 ID, 사용자명 또는 닉네임",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "타임아웃 지속 시간 (분). 최대 10080분 (7일)",
                },
                "reason": {
                    "type": "string",
                    "description": "타임아웃 사유 (선택사항)",
                },
            },
            "required": ["user_ref", "duration_minutes"],
        }

    async def execute(self, **kwargs: Any) -> str:
        user_ref = kwargs.get("user_ref", "")
        duration_minutes = kwargs.get("duration_minutes", 0)
        reason = kwargs.get("reason")

        guild: discord.Guild | None = kwargs.get("_guild")
        if not guild:
            return '{"error": "서버 정보를 찾을 수 없습니다. 이 명령어는 서버 채널에서만 사용할 수 있습니다."}'

        if duration_minutes <= 0:
            return '{"error": "duration_minutes는 0보다 커야 합니다."}'

        if duration_minutes > 10080:
            return '{"error": "최대 타임아웃은 7일(10080분)까지 가능합니다."}'

        member = await resolve_member(guild, user_ref)
        if not member:
            return f'{{"error": "사용자 `{user_ref}`를 찾을 수 없습니다."}}'

        until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        try:
            await member.timeout(until, reason=reason)
            reason_text = f" (사유: {reason})" if reason else ""
            logger.info(f"Admin: Timed out {member.display_name} ({member.id}) for {duration_minutes} min")
            return f'{{"success": true, "user_id": "{member.id}", "display_name": "{member.display_name}", "message": "사용자 `{member.display_name}` ({member.id})가 {duration_minutes}분간 타임아웃되었습니다.{reason_text}"}}'
        except Exception as e:
            return f'{{"error": "타임아웃 실행 중 오류: {str(e)}"}}'


class UntimeoutTool(Tool):
    """Remove timeout from a user."""

    @property
    def name(self) -> str:
        return "untimeout_user"

    @property
    def description(self) -> str:
        return "Discord 서버에서 특정 사용자의 타임아웃을 해제합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_ref": {
                    "type": "string",
                    "description": "타임아웃을 해제할 사용자 ID, 사용자명 또는 닉네임",
                },
            },
            "required": ["user_ref"],
        }

    async def execute(self, **kwargs: Any) -> str:
        user_ref = kwargs.get("user_ref", "")

        guild: discord.Guild | None = kwargs.get("_guild")
        if not guild:
            return '{"error": "서버 정보를 찾을 수 없습니다."}'

        member = await resolve_member(guild, user_ref)
        if not member:
            return f'{{"error": "사용자 `{user_ref}`를 찾을 수 없습니다."}}'

        try:
            await member.timeout(None)
            logger.info(f"Admin: Removed timeout from {member.display_name} ({member.id})")
            return f'{{"success": true, "user_id": "{member.id}", "display_name": "{member.display_name}", "message": "사용자 `{member.display_name}` ({member.id})의 타임아웃이 해제되었습니다."}}'
        except Exception as e:
            return f'{{"error": "타임아웃 해제 중 오류: {str(e)}"}}'


class BroadcastTool(Tool):
    """Send a message to a channel."""

    @property
    def name(self) -> str:
        return "broadcast_message"

    @property
    def description(self) -> str:
        return "지정된 Discord 채널에 메시지를 전송합니다. 공지사항이나 알림을 보낼 때 사용합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel_ref": {
                    "type": "string",
                    "description": "메시지를 전송할 채널 ID 또는 채널명",
                },
                "message": {
                    "type": "string",
                    "description": "전송할 메시지 내용",
                },
            },
            "required": ["channel_ref", "message"],
        }

    async def execute(self, **kwargs: Any) -> str:
        channel_ref = kwargs.get("channel_ref", "")
        message = kwargs.get("message", "")

        guild: discord.Guild | None = kwargs.get("_guild")
        app: "TokamakApp | None" = kwargs.get("_app")
        if not app:
            return '{"error": "앱 정보를 찾을 수 없습니다."}'
        if not guild:
            return '{"error": "서버 정보를 찾을 수 없습니다."}'

        channel = await resolve_channel(guild, channel_ref)
        if not channel:
            return f'{{"error": "채널 `{channel_ref}`를 찾을 수 없습니다."}}'

        if not message or not message.strip():
            return '{"error": "메시지 내용이 비어있습니다."}'

        from tokamak.bus.events import OutboundMessage

        msg = OutboundMessage(
            channel="discord",
            chat_id=str(channel.id),
            content=message.strip(),
        )
        await app.bus.publish_outbound(msg)

        logger.info(f"Admin: Broadcast to channel {channel.name} ({channel.id})")
        return f'{{"success": true, "channel_id": "{channel.id}", "channel_name": "{channel.name}", "message": "메시지가 채널 `{channel.name}`에 전송되었습니다."}}'


class GetStatusTool(Tool):
    """Get bot status."""

    @property
    def name(self) -> str:
        return "get_bot_status"

    @property
    def description(self) -> str:
        return "봇의 현재 상태를 확인합니다. 활성 세션 수, 활성 대화 수, 뉴스 피드 상태 등을 반환합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs: Any) -> str:
        app: "TokamakApp | None" = kwargs.get("_app")
        if not app:
            return '{"error": "앱 정보를 찾을 수 없습니다."}'

        session_count = len(app.session_manager._sessions)
        conversation_count = app.discord.active_conversation_count
        news_feed_status = "활성" if app.news_feed else "비활성"

        return f'{{"success": true, "active_sessions": {session_count}, "active_conversations": {conversation_count}, "news_feed": "{news_feed_status}"}}'


class ListSessionsTool(Tool):
    """List active sessions."""

    @property
    def name(self) -> str:
        return "list_sessions"

    @property
    def description(self) -> str:
        return "현재 활성화된 사용자 세션 목록을 조회합니다. 각 세션의 키, 메시지 수, 상태를 반환합니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 세션 수 (기본값: 10, 최대: 50)",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        app: "TokamakApp | None" = kwargs.get("_app")
        if not app:
            return '{"error": "앱 정보를 찾을 수 없습니다."}'

        limit = min(kwargs.get("limit", 10), 50)
        sessions = list(app.session_manager._sessions.items())[:limit]

        if not sessions:
            return '{"success": true, "sessions": [], "message": "활성 세션이 없습니다."}'

        session_list = []
        for key, session in sessions:
            msg_count = len(session.messages)
            status = "ended" if session.is_ended else "active"
            session_list.append({
                "key": key,
                "message_count": msg_count,
                "status": status,
            })

        import json
        return json.dumps({"success": True, "sessions": session_list}, ensure_ascii=False)


class ClearSessionTool(Tool):
    """Clear a session."""

    @property
    def name(self) -> str:
        return "clear_session"

    @property
    def description(self) -> str:
        return "지정된 사용자 세션을 삭제합니다. 세션 키는 list_sessions 도구로 확인할 수 있습니다."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_key": {
                    "type": "string",
                    "description": "삭제할 세션의 키 (예: discord:123456789:987654321)",
                },
            },
            "required": ["session_key"],
        }

    async def execute(self, **kwargs: Any) -> str:
        session_key = kwargs.get("session_key", "")

        app: "TokamakApp | None" = kwargs.get("_app")
        if not app:
            return '{"error": "앱 정보를 찾을 수 없습니다."}'

        sessions = app.session_manager._sessions

        if session_key not in sessions:
            return f'{{"error": "세션을 찾을 수 없습니다: `{session_key}`"}}'

        del sessions[session_key]
        logger.info(f"Admin: Cleared session {session_key}")
        return f'{{"success": true, "message": "세션이 삭제되었습니다: `{session_key}`"}}'


ADMIN_TOOLS = [
    SearchUserTool(),
    SearchChannelTool(),
    TimeoutTool(),
    UntimeoutTool(),
    BroadcastTool(),
    GetStatusTool(),
    ListSessionsTool(),
    ClearSessionTool(),
]