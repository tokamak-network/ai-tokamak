"""Session management for conversation history (memory-based)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in memory for the duration of the bot's runtime.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    max_messages: int = 100

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

        # Trim old messages if exceeding max
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.

        Args:
            max_messages: Maximum messages to return.

        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages

        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions in memory.

    Sessions are stored only in memory and will be lost on restart.
    This is intentional for MVP simplicity.
    """

    def __init__(self, max_messages: int = 100):
        """
        Initialize the session manager.

        Args:
            max_messages: Maximum messages per session.
        """
        self.max_messages = max_messages
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:guild_id:user_id).

        Returns:
            The session.
        """
        if key not in self._sessions:
            self._sessions[key] = Session(key=key, max_messages=self.max_messages)
        return self._sessions[key]

    def get(self, key: str) -> Session | None:
        """Get a session by key, returns None if not found."""
        return self._sessions.get(key)

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        if key in self._sessions:
            del self._sessions[key]
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        return [
            {
                "key": s.key,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages),
            }
            for s in sorted(
                self._sessions.values(),
                key=lambda x: x.updated_at,
                reverse=True
            )
        ]

    def __len__(self) -> int:
        return len(self._sessions)
