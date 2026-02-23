"""LLM-based toxicity detection."""

import json

from loguru import logger

from tokamak.config.schema import ModerationConfig
from tokamak.moderation.types import ModerationResult, ModerationSeverity
from tokamak.providers.base import LLMProvider


TOXICITY_PROMPT = """다음 메시지가 유해한지 분석하세요. 한국어 욕설, 비방, 혐오 표현을 감지합니다.

메시지: {message}

분석 결과를 다음 JSON 형식으로만 응답하세요:
{{
    "is_toxic": true/false,
    "severity": "low"/"medium"/"high"/null,
    "category": "profanity"/"defamation"/"threat"/"harassment"/null,
    "confidence": 0.0-1.0,
    "reason": "판단 이유 (한국어)"
}}

기준:
- low: 가벼운 욕설, 비속어
- medium: 모욕적 표현, 중간 수준 비방
- high: 심한 욕설, 명확한 비방, 위협, 혐오 발언

is_toxic가 false면 severity와 category는 null이어야 합니다.
JSON 외의 다른 텍스트는 출력하지 마세요."""


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

            return ModerationResult(
                is_toxic=result_data.get("is_toxic", False),
                severity=severity,
                category=result_data.get("category"),
                confidence=result_data.get("confidence", 0.0),
                reason=result_data.get("reason"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse toxicity result: {e}")
            return ModerationResult(is_toxic=False)
        except Exception as e:
            logger.error(f"Toxicity detection error: {e}")
            return ModerationResult(is_toxic=False)