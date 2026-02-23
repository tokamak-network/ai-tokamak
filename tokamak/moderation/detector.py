"""LLM-based toxicity detection."""

import json

from loguru import logger

from tokamak.config.schema import ModerationConfig
from tokamak.moderation.types import ModerationResult, ModerationSeverity
from tokamak.providers.base import LLMProvider

TOXICITY_PROMPT = """Analyze the following message for toxic content. Detect profanity, defamation, threats, and harassment in both Korean and English.

Message: {message}

Respond ONLY in the following JSON format:
{{
    "is_toxic": true/false,
    "severity": "low"/"medium"/"high"/null,
    "category": "profanity"/"defamation"/"threat"/"harassment"/null,
    "confidence": 0.0-1.0,
    "reason": "판단 이유 (한국어)"
}}

Criteria:
- low: Mild profanity, slang (가벼운 욕설, 비속어)
- medium: Offensive language, moderate insults (모욕적 표현, 중간 수준 비방)
- high: Severe profanity, clear defamation, threats, hate speech (심한 욕설, 명확한 비방, 위협, 혐오 발언)

If is_toxic is false, severity and category must be null.
Do not output any text other than JSON."""


class ToxicityDetector:
    """Detects toxic content using LLM."""

    def __init__(self, provider: LLMProvider, config: ModerationConfig):
        self.provider = provider
        self.config = config
        self._model = "qwen3-235b"  # Use fast model for detection

    async def detect(self, message: str) -> ModerationResult:
        """
        Analyze message for toxic content.

        Args:
            message: The message content to analyze

        Returns:
            ModerationResult with detection details
        """
        if not self.config.enabled:
            return ModerationResult(is_toxic=False)

        try:
            prompt = TOXICITY_PROMPT.format(message=message)
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
                max_tokens=256,
                temperature=0.1,  # Low temperature for consistent output
            )

            if response.finish_reason == "error":
                logger.error(f"LLM error in toxicity detection: {response.content}")
                return ModerationResult(is_toxic=False)

            # Parse JSON response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result_data = json.loads(content)

            severity = None
            if result_data.get("severity"):
                try:
                    severity = ModerationSeverity(result_data["severity"])
                except ValueError:
                    pass

            is_toxic = result_data.get("is_toxic", False)
            confidence = result_data.get("confidence", 0.0)

            # Apply threshold filter
            if is_toxic and confidence < self.config.toxicity_threshold:
                logger.debug(
                    f"Toxicity below threshold: confidence={confidence:.2f}, "
                    f"threshold={self.config.toxicity_threshold}"
                )
                is_toxic = False

            return ModerationResult(
                is_toxic=is_toxic,
                severity=severity if is_toxic else None,
                category=result_data.get("category") if is_toxic else None,
                confidence=confidence,
                reason=result_data.get("reason"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse toxicity result: {e}")
            return ModerationResult(is_toxic=False)
        except Exception as e:
            logger.error(f"Toxicity detection error: {e}")
            return ModerationResult(is_toxic=False)
