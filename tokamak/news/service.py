import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from tokamak.bus.events import OutboundMessage
from tokamak.bus.queue import MessageBus
from tokamak.cron.types import CronJob
from tokamak.news.fetcher import NewsFetcher, NewsItem
from tokamak.news.summarizer import NewsSummarizer, NewsSummary


@dataclass
class NewsFeedState:
    last_fetch_at: datetime | None = None
    processed_ids: list[str] = field(default_factory=list)

    MAX_PROCESSED_IDS = 500


class NewsFeedService:
    def __init__(
        self,
        fetcher: NewsFetcher,
        summarizer: NewsSummarizer,
        bus: MessageBus,
        state_path: Path,
        korean_channel_id: int | None,
        english_channel_id: int | None,
        max_news_per_fetch: int = 15,
    ) -> None:
        self.fetcher = fetcher
        self.summarizer = summarizer
        self.bus = bus
        self.state_path = state_path
        self.korean_channel_id = korean_channel_id
        self.english_channel_id = english_channel_id
        self.max_news_per_fetch = max_news_per_fetch
        self.state = self._load_state()

    def _load_state(self) -> NewsFeedState:
        if not self.state_path.exists():
            return NewsFeedState()

        try:
            data = json.loads(self.state_path.read_text())
            return NewsFeedState(
                last_fetch_at=datetime.fromisoformat(data["last_fetch_at"])
                if data.get("last_fetch_at")
                else None,
                processed_ids=data.get("processed_ids", []),
            )
        except Exception as e:
            logger.warning(f"Failed to load news feed state: {e}")
            return NewsFeedState()

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_fetch_at": self.state.last_fetch_at.isoformat()
            if self.state.last_fetch_at
            else None,
            "processed_ids": self.state.processed_ids[-NewsFeedState.MAX_PROCESSED_IDS :],
        }
        self.state_path.write_text(json.dumps(data, indent=2))

    async def run(self, job: CronJob | None = None) -> str | None:
        logger.info("News feed: starting fetch cycle")

        result = await self.fetcher.fetch_all()

        new_items = [item for item in result.items if item.id not in self.state.processed_ids]

        if result.errors:
            logger.warning(f"News feed: {len(result.errors)} sources failed")

        if not new_items:
            logger.info("News feed: no new items")
            self.state.last_fetch_at = datetime.now(timezone.utc)
            self._save_state()
            return None

        items_to_summarize = new_items[: self.max_news_per_fetch]

        summary = await self.summarizer.summarize(items_to_summarize)

        if summary:
            await self._send_summary(summary, items_to_summarize)
        else:
            logger.warning("News feed: failed to generate summary")

        processed_ids = [item.id for item in items_to_summarize]
        self.state.processed_ids.extend(processed_ids)
        self._trim_processed_ids()
        self.state.last_fetch_at = datetime.now(timezone.utc)
        self._save_state()

        logger.info(
            f"News feed: processed {len(items_to_summarize)} new items "
            f"(total fetched: {len(result.items)})"
        )
        return None

    async def _send_summary(self, summary: NewsSummary, items: list[NewsItem]) -> None:
        timestamp = summary.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        links_section = self._format_links(items)

        if self.korean_channel_id and summary.korean:
            korean_content = (
                f"## 📰 블록체인 뉴스 업데이트\n_({timestamp})_\n\n"
                f"{summary.korean}\n\n"
                f"---\n**📎 원문 링크**\n{links_section}"
            )
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel="discord",
                    chat_id=str(self.korean_channel_id),
                    content=korean_content,
                )
            )

        if self.english_channel_id and summary.english:
            english_content = (
                f"## 📰 Blockchain News Update\n_({timestamp})_\n\n"
                f"{summary.english}\n\n"
                f"---\n**📎 Source Links**\n{links_section}"
            )
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel="discord",
                    chat_id=str(self.english_channel_id),
                    content=english_content,
                )
            )

        logger.info("News feed: summaries sent to Discord channels")

    def _format_links(self, items: list[NewsItem], max_links: int = 10) -> str:
        links = []
        for item in items[:max_links]:
            links.append(
                f"• [{item.title[:50]}{'...' if len(item.title) > 50 else ''}]({item.url})"
            )
        return "\n".join(links)

    def _trim_processed_ids(self) -> None:
        if len(self.state.processed_ids) > NewsFeedState.MAX_PROCESSED_IDS:
            self.state.processed_ids = self.state.processed_ids[-NewsFeedState.MAX_PROCESSED_IDS :]
