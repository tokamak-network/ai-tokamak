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
