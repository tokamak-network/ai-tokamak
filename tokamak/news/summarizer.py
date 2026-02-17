import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger

from tokamak.news.fetcher import NewsItem
from tokamak.news.prompts import NEWS_SUMMARY_PROMPT
from tokamak.providers import LLMProvider

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


@dataclass
class NewsSummary:
    korean: str
    english: str
    sources: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NewsSummarizer:
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> None:
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def summarize(self, news_items: list[NewsItem]) -> NewsSummary | None:
        if not news_items:
            return None

        news_content = self._format_news(news_items)
        prompt = NEWS_SUMMARY_PROMPT.format(news_content=news_content)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                if not response.content:
                    logger.warning("Empty response from LLM for news summary")
                    return None

                korean_summary, english_summary = self._parse_response(response.content)

                return NewsSummary(
                    korean=korean_summary,
                    english=english_summary,
                    sources=[item.url for item in news_items[:5]],
                )

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"LLM request failed, retry {attempt + 1}/{MAX_RETRIES} in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to generate news summary after {MAX_RETRIES} retries: {e}")

        return None

    def _format_news(self, items: list[NewsItem]) -> str:
        formatted = []
        for i, item in enumerate(items, 1):
            content_preview = item.content[:300] if item.content else ""
            formatted.append(
                f"{i}. [{item.source}] {item.title}\n"
                f"   URL: {item.url}\n"
                f"   Preview: {content_preview}...\n"
            )
        return "\n".join(formatted)

    def _parse_response(self, content: str) -> tuple[str, str]:
        korean = ""
        english = ""

        lines = content.split("\n")

        in_korean = False
        in_english = False
        korean_lines: list[str] = []
        english_lines: list[str] = []

        for line in lines:
            if "## 📰 주요 뉴스" in line or "##📰 주요 뉴스" in line:
                in_korean = True
                in_english = False
                continue
            elif "## 📰 Top News" in line or "##📰 Top News" in line:
                in_korean = False
                in_english = True
                continue

            if in_korean:
                korean_lines.append(line)
            elif in_english:
                english_lines.append(line)

        korean = "\n".join(korean_lines).strip()
        english = "\n".join(english_lines).strip()

        return korean, english
