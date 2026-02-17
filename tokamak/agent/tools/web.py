"""Web fetch tool for scraping URLs."""

import html
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from tokamak.agent.tools.base import Tool

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class WebFetchTool(Tool):
    """Fetch and extract content from a URL."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch URL and extract readable content (HTML to text)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {
                    "type": "integer",
                    "minimum": 100,
                    "description": "Max characters to return",
                },
            },
            "required": ["url"],
        }

    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars

    def _is_safe_url(self, url: str) -> str | None:
        """Validate URL is safe to fetch. Returns error message if unsafe, None if safe."""
        try:
            parsed = urlparse(url)
        except Exception:
            return "Invalid URL"

        if parsed.scheme not in ("http", "https"):
            return f"Unsupported scheme: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return "No hostname in URL"

        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return "Access to internal networks is not allowed"
        except (socket.gaierror, ValueError):
            return f"Cannot resolve hostname: {hostname}"

        return None

    async def execute(self, url: str, max_chars: int | None = None, **kwargs: Any) -> str:
        max_chars = max_chars or self.max_chars

        # SSRF protection: validate URL before fetching
        safety_error = self._is_safe_url(url)
        if safety_error:
            return json.dumps({"error": safety_error, "url": url})

        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0
                )
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            # JSON
            if "application/json" in ctype:
                text = json.dumps(r.json(), indent=2)
                extractor = "json"
            # HTML
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                text, extractor = self._extract_html(r.text)
            else:
                text = r.text
                extractor = "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return json.dumps(
                {
                    "url": url,
                    "final_url": str(r.url),
                    "status": r.status_code,
                    "extractor": extractor,
                    "truncated": truncated,
                    "length": len(text),
                    "text": text,
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

    def _extract_html(self, html_content: str) -> tuple[str, str]:
        """Extract readable content from HTML."""
        try:
            from readability import Document

            doc = Document(html_content)
            content = self._to_markdown(doc.summary())
            text = f"# {doc.title()}\n\n{content}" if doc.title() else content
            return text, "readability"
        except ImportError:
            return _normalize(_strip_tags(html_content)), "fallback"

    def _to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        text = re.sub(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            lambda m: f"[{_strip_tags(m[2])}]({m[1]})",
            html,
            flags=re.I,
        )
        text = re.sub(
            r"<h([1-6])[^>]*>([\s\S]*?)</h\1>",
            lambda m: f"\n{'#' * int(m[1])} {_strip_tags(m[2])}\n",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"<li[^>]*>([\s\S]*?)</li>", lambda m: f"\n- {_strip_tags(m[1])}", text, flags=re.I
        )
        text = re.sub(r"</(p|div|section|article)>", "\n\n", text, flags=re.I)
        text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.I)
        return _normalize(_strip_tags(text))
