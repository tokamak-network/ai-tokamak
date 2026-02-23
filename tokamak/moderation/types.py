"""Data types for content moderation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ModerationSeverity(str, Enum):
    """Severity level of toxic content."""

    LOW = "low"  # Mild profanity
    MEDIUM = "medium"  # Moderate insults
    HIGH = "high"  # Severe defamation/threats


@dataclass
class ModerationResult:
    """Result of toxicity detection."""

    is_toxic: bool
    severity: ModerationSeverity | None = None
    category: str | None = None  # e.g., "profanity", "defamation", "threat"
    confidence: float = 0.0
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_toxic": self.is_toxic,
            "severity": self.severity.value if self.severity else None,
            "category": self.category,
            "confidence": self.confidence,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModerationResult":
        """Deserialize from dictionary."""
        severity = None
        if data.get("severity"):
            try:
                severity = ModerationSeverity(data["severity"])
            except ValueError:
                pass
        return cls(
            is_toxic=data.get("is_toxic", False),
            severity=severity,
            category=data.get("category"),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason"),
        )


@dataclass
class ToxicContentEvent:
    """Event data for toxic content detection."""

    guild_id: int
    channel_id: int
    user_id: int
    user_name: str
    message_id: int
    message_content: str
    result: ModerationResult
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "message_id": self.message_id,
            "message_content": self.message_content,
            "result": self.result.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToxicContentEvent":
        """Deserialize from dictionary."""
        return cls(
            guild_id=data["guild_id"],
            channel_id=data["channel_id"],
            user_id=data["user_id"],
            user_name=data["user_name"],
            message_id=data["message_id"],
            message_content=data["message_content"],
            result=ModerationResult.from_dict(data["result"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )
