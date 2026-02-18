"""Internal state management tool."""

import json
from typing import TYPE_CHECKING, Any

from tokamak.agent.tools.base import Tool

if TYPE_CHECKING:
    from tokamak.app import TokamakApp


class InternalStateTool(Tool):
    """Manage internal bot state: sessions, status, etc."""

    @property
    def name(self) -> str:
        return "internal_state"

    @property
    def description(self) -> str:
        return "봇 내부 상태 관리. 세션 목록 조회, 상태 확인, 세션 삭제 등."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_status", "list_sessions", "delete_session"],
                    "description": "수행할 작업",
                },
                "session_key": {
                    "type": "string",
                    "description": "세션 키 (delete_session 액션에서 필요)",
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 세션 수 (list_sessions에서 사용, 기본 10)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        app: "TokamakApp | None" = kwargs.get("_app")
        if not app:
            return json.dumps({"error": "앱 정보를 찾을 수 없습니다."}, ensure_ascii=False)

        action = kwargs.get("action")

        if action == "get_status":
            return self._get_status(app)
        elif action == "list_sessions":
            return self._list_sessions(app, kwargs.get("limit", 10))
        elif action == "delete_session":
            session_key = kwargs.get("session_key")
            if not session_key:
                return json.dumps({"error": "session_key가 필요합니다."}, ensure_ascii=False)
            return self._delete_session(app, session_key)
        else:
            return json.dumps({"error": f"알 수 없는 액션: {action}"}, ensure_ascii=False)

    def _get_status(self, app: "TokamakApp") -> str:
        session_count = len(app.session_manager._sessions)
        conversation_count = app.discord.active_conversation_count
        news_feed_status = "활성" if app.news_feed else "비활성"

        return json.dumps(
            {
                "success": True,
                "active_sessions": session_count,
                "active_conversations": conversation_count,
                "news_feed": news_feed_status,
            },
            ensure_ascii=False,
        )

    def _list_sessions(self, app: "TokamakApp", limit: int) -> str:
        limit = min(limit, 50)
        sessions = list(app.session_manager._sessions.items())[:limit]

        if not sessions:
            return json.dumps(
                {"success": True, "sessions": [], "message": "활성 세션이 없습니다."},
                ensure_ascii=False,
            )

        session_list = []
        for key, session in sessions:
            msg_count = len(session.messages)
            status = "ended" if session.is_ended else "active"
            session_list.append({
                "key": key,
                "message_count": msg_count,
                "status": status,
            })

        return json.dumps({"success": True, "sessions": session_list}, ensure_ascii=False)

    def _delete_session(self, app: "TokamakApp", session_key: str) -> str:
        sessions = app.session_manager._sessions

        if session_key not in sessions:
            return json.dumps(
                {"error": f"세션을 찾을 수 없습니다: `{session_key}`"}, ensure_ascii=False
            )

        del sessions[session_key]
        return json.dumps(
            {"success": True, "message": f"세션이 삭제되었습니다: `{session_key}`"},
            ensure_ascii=False,
        )