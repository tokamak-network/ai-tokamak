"""Built-in admin commands."""

from tokamak.admin.handler import AdminCommand, AdminContext


class StatusCommand(AdminCommand):
    """Show bot status."""

    name = "status"
    description = "봇 상태 확인"
    usage = "status"

    async def execute(self, ctx: AdminContext) -> str:
        app = ctx.app
        lines = [
            "**🤖 Tokamak Bot Status**",
            f"- 활성 세션: {len(ctx.app.session_manager._sessions)}개",
            f"- 활성 대화: {ctx.app.discord.active_conversation_count}개",
        ]

        if app.news_feed:
            lines.append("- 뉴스 피드: 활성")
        else:
            lines.append("- 뉴스 피드: 비활성")

        return "\n".join(lines)


class SessionsCommand(AdminCommand):
    """List active sessions."""

    name = "sessions"
    description = "활성 세션 목록"
    usage = "sessions [limit=10]"

    async def execute(self, ctx: AdminContext) -> str:
        limit = 10
        if ctx.args and ctx.args[0].isdigit():
            limit = min(int(ctx.args[0]), 50)

        sessions = list(ctx.app.session_manager._sessions.items())[:limit]

        if not sessions:
            return "활성 세션이 없습니다."

        lines = [f"**📋 활성 세션 ({len(sessions)}개)**"]
        for key, session in sessions:
            msg_count = len(session.messages)
            status = "종료됨" if session.is_ended else "활성"
            lines.append(f"- `{key}`: {msg_count}개 메시지 ({status})")

        return "\n".join(lines)


class ClearCommand(AdminCommand):
    """Clear a session."""

    name = "clear"
    description = "세션 삭제"
    usage = "clear <session_key>"

    async def execute(self, ctx: AdminContext) -> str:
        if not ctx.args:
            return f"사용법: `{ctx.app.config.admin.command_prefix}{self.usage}`"

        session_key = ctx.args[0]
        sessions = ctx.app.session_manager._sessions

        if session_key not in sessions:
            return f"세션을 찾을 수 없습니다: `{session_key}`"

        del sessions[session_key]
        return f"세션 삭제됨: `{session_key}`"


class BroadcastCommand(AdminCommand):
    """Send message to a channel."""

    name = "broadcast"
    description = "채널에 메시지 전송"
    usage = "broadcast <channel_id> <message>"

    async def execute(self, ctx: AdminContext) -> str:
        if len(ctx.args) < 2:
            return f"사용법: `{ctx.app.config.admin.command_prefix}{self.usage}`"

        try:
            channel_id = int(ctx.args[0])
        except ValueError:
            return "channel_id는 숫자여야 합니다."

        content = ctx.message.content

        code_block_start = content.find("```")
        if code_block_start == -1:
            return "메시지를 ``` 코드 블럭으로 감싸주세요."

        code_block_end = content.rfind("```")
        if code_block_end == code_block_start:
            return "코드 블럭이 올바르게 닫히지 않았습니다."

        message = content[code_block_start + 3 : code_block_end].strip()

        if not message:
            return "메시지 내용이 비어있습니다."

        from tokamak.bus.events import OutboundMessage

        msg = OutboundMessage(
            channel="discord",
            chat_id=str(channel_id),
            content=message,
        )
        await ctx.app.bus.publish_outbound(msg)

        return f"메시지 전송됨 to channel {channel_id}"


class TimeoutCommand(AdminCommand):
    """Timeout a user in a guild."""

    name = "timeout"
    description = "사용자 타임아웃"
    usage = "timeout <user_id> <duration_minutes> [reason]"

    async def execute(self, ctx: AdminContext) -> str:
        if len(ctx.args) < 2:
            return f"사용법: `{ctx.app.config.admin.command_prefix}{self.usage}`"

        try:
            user_id = int(ctx.args[0])
        except ValueError:
            return "user_id는 숫자여야 합니다."

        try:
            duration_minutes = int(ctx.args[1])
        except ValueError:
            return "duration_minutes는 숫자여야 합니다."

        if duration_minutes <= 0:
            return "duration_minutes는 0보다 커야 합니다."

        if duration_minutes > 10080:
            return "최대 타임아웃은 7일(10080분)까지 가능합니다."

        reason = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else None

        guild = ctx.message.guild
        if not guild:
            return "이 명령어는 서버 채널에서만 사용할 수 있습니다."

        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except Exception:
                return f"사용자 `{user_id}`를 찾을 수 없습니다."

        from datetime import datetime, timedelta, timezone

        until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        await member.timeout(until, reason=reason)
        reason_text = f" (사유: {reason})" if reason else ""
        return f"사용자 `{user_id}`가 {duration_minutes}분간 타임아웃되었습니다.{reason_text}"


class UntimeoutCommand(AdminCommand):
    """Remove timeout from a user."""

    name = "untimeout"
    description = "사용자 타임아웃 해제"
    usage = "untimeout <user_id>"

    async def execute(self, ctx: AdminContext) -> str:
        if not ctx.args:
            return f"사용법: `{ctx.app.config.admin.command_prefix}{self.usage}`"

        try:
            user_id = int(ctx.args[0])
        except ValueError:
            return "user_id는 숫자여야 합니다."

        guild = ctx.message.guild
        if not guild:
            return "이 명령어는 서버 채널에서만 사용할 수 있습니다."

        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except Exception:
                return f"사용자 `{user_id}`를 찾을 수 없습니다."

        await member.timeout(None)
        return f"사용자 `{user_id}`의 타임아웃이 해제되었습니다."


class HelpCommand(AdminCommand):
    """Show available commands."""

    name = "help"
    description = "명령어 도움말"
    usage = "help"

    async def execute(self, ctx: AdminContext) -> str:
        prefix = ctx.app.config.admin.command_prefix
        lines = ["**📚 관리자 명령어**"]

        for cmd_info in ctx.app.admin_handler.get_commands_info():
            usage_line = (
                f"`{prefix}{cmd_info['usage']}`"
                if cmd_info["usage"]
                else f"`{prefix}{cmd_info['name']}`"
            )
            lines.append(f"- {usage_line}: {cmd_info['description']}")

        return "\n".join(lines)
