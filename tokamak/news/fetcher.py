import asyncio
import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime
    content: str = ""
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = hashlib.md5(f"{self.source}:{self.url}".encode()).hexdigest()[:12]


@dataclass
class FetchResult:
    items: list[NewsItem]
    errors: list[str] = field(default_factory=list)


class NewsFetcher:
    def __init__(
        self,
        sources: list[str],
        timeout_seconds: float = 10.0,
        max_items_per_source: int = 10,
    ) -> None:
        self.sources = sources
        self.timeout_seconds = timeout_seconds
        self.max_items_per_source = max_items_per_source

    async def fetch_all(self) -> FetchResult:
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            tasks = [self._fetch_feed(client, url) for url in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[NewsItem] = []
        errors: list[str] = []

        for source_url, result in zip(self.sources, results):
            if isinstance(result, Exception):
                errors.append(f"{source_url}: {result}")
                logger.warning(f"Failed to fetch {source_url}: {result}")
            else:
                all_items.extend(result)

        all_items.sort(key=lambda x: x.published_at, reverse=True)
        return FetchResult(items=all_items, errors=errors)

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> list[NewsItem]:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return self._parse_rss(response.text, url)
            except httpx.TimeoutException as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Timeout fetching {url}, retry {attempt + 1}/{MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise e
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Rate limited on {url}, retry {attempt + 1}/{MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                elif 500 <= e.response.status_code < 600 and attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Server error {e.response.status_code} on {url}, retry {attempt + 1}/{MAX_RETRIES} in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise e
        return []

    def _parse_rss(self, xml_content: str, source_url: str) -> list[NewsItem]:
        source_name = self._extract_domain(source_url)
        items: list[NewsItem] = []

        try:
            root = ET.fromstring(xml_content)
            channel = root.find("channel")
            if channel is None:
                return items

            for item in channel.findall("item")[: self.max_items_per_source]:
                news_item = self._parse_item(item, source_name)
                if news_item:
                    items.append(news_item)

        except ET.ParseError as e:
            logger.warning(f"Failed to parse RSS from {source_url}: {e}")

        return items

    def _parse_item(self, item: Any, source_name: str) -> NewsItem | None:
        title_elem = item.find("title")
        link_elem = item.find("link")
        pub_date_elem = item.find("pubDate")

        if title_elem is None or link_elem is None:
            return None

        title = title_elem.text or ""
        url = link_elem.text or ""

        pub_date = self._parse_date(pub_date_elem.text if pub_date_elem is not None else None)

        description_elem = item.find("description")
        content = description_elem.text if description_elem is not None else ""

        return NewsItem(
            title=title.strip(),
            url=url.strip(),
            source=source_name,
            published_at=pub_date,
            content=self._strip_html(content) if content else "",
        )

    def _parse_date(self, date_str: str | None) -> datetime:
        if not date_str:
            return datetime.now(timezone.utc)

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return datetime.now(timezone.utc)

    def _extract_domain(self, url: str) -> str:
        try:
            if "://" in url:
                domain = url.split("://")[1].split("/")[0]
                return domain.replace("www.", "")
            return url
        except Exception:
            return url

    def _strip_html(self, text: str) -> str:
        result = text
        for tag in ["<p>", "</p>", "<br>", "<br/>", "</br>", "<br />"]:
            result = result.replace(tag, " ")
        while "<" in result and ">" in result:
            start = result.find("<")
            end = result.find(">", start)
            if start != -1 and end != -1:
                result = result[:start] + result[end + 1 :]
            else:
                break
        return " ".join(result.split())
