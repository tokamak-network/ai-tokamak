"""Web tools for HTTP requests."""

import html
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from tokamak.agent.tools.base import Tool

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"

DISCORD_USER_AGENT = "DiscordBot (https://github.com/tokamak-network/ai-tokamak, 1.0)"


def _strip_tags(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _build_url_with_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    parsed = urlparse(url)
    query_dict = {}
    if parsed.query:
        for pair in parsed.query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                query_dict[k] = v
    for k, v in params.items():
        query_dict[k] = str(v)
    new_query = urlencode(query_dict)
    return urlunparse(parsed._replace(query=new_query))


class WebFetchTool(Tool):
    """GET request tool with query params support."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch URL content with GET request. "
            "Use 'params' for query parameters (e.g., ?query=value). "
            "Use auth_provider='discord' for Discord Bot API calls."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "params": {
                    "type": "object",
                    "description": "Query parameters as key-value pairs (e.g., {'query': 'bhlee', 'limit': 10})",
                    "additionalProperties": {"type": "string"},
                },
                "headers": {
                    "type": "object",
                    "description": "Custom headers as key-value pairs",
                    "additionalProperties": {"type": "string"},
                },
                "auth_provider": {
                    "type": "string",
                    "enum": ["discord"],
                    "description": "Pre-configured auth provider. Use 'discord' for Discord Bot API.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 100,
                    "description": "Max characters to return (default: 50000)",
                },
            },
            "required": ["url"],
        }

    def __init__(self, max_chars: int = 50000, auth_tokens: dict[str, str] | None = None):
        self.max_chars = max_chars
        self.auth_tokens = auth_tokens or {}

    def _is_safe_url(self, url: str) -> str | None:
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

    def _get_auth_headers(self, auth_provider: str) -> dict[str, str]:
        if auth_provider == "discord":
            token = self.auth_tokens.get("discord")
            if token:
                return {"Authorization": f"Bot {token}"}
        return {}

    async def execute(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        auth_provider: str | None = None,
        max_chars: int | None = None,
        **kwargs: Any,
    ) -> str:
        max_chars = max_chars or self.max_chars

        safety_error = self._is_safe_url(url)
        if safety_error:
            return json.dumps({"error": safety_error, "url": url})

        url = _build_url_with_params(url, params)

        if auth_provider == "discord":
            request_headers = {"User-Agent": DISCORD_USER_AGENT}
        else:
            request_headers = {"User-Agent": USER_AGENT}

        if auth_provider:
            auth_headers = self._get_auth_headers(auth_provider)
            request_headers.update(auth_headers)

        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    url, headers=request_headers, follow_redirects=True, timeout=30.0
                )

            ctype = r.headers.get("content-type", "")

            if "application/json" in ctype:
                try:
                    text = json.dumps(r.json(), indent=2, ensure_ascii=False)
                    extractor = "json"
                except Exception:
                    text = r.text
                    extractor = "raw"
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                text, extractor = self._extract_html(r.text)
            else:
                text = r.text
                extractor = "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            response_headers = dict(r.headers)
            for key in response_headers:
                if key.lower() in ("authorization", "set-cookie", "x-api-key"):
                    response_headers[key] = "[REDACTED]"

            return json.dumps(
                {
                    "url": url,
                    "final_url": str(r.url),
                    "method": "GET",
                    "status": r.status_code,
                    "extractor": extractor,
                    "truncated": truncated,
                    "length": len(text),
                    "text": text,
                    "headers": response_headers,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

    def _extract_html(self, html_content: str) -> tuple[str, str]:
        try:
            from readability import Document

            doc = Document(html_content)
            content = self._to_markdown(doc.summary())
            text = f"# {doc.title()}\n\n{content}" if doc.title() else content
            return text, "readability"
        except ImportError:
            return _normalize(_strip_tags(html_content)), "fallback"

    def _to_markdown(self, html: str) -> str:
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


class WebPostTool(Tool):
    """POST/PUT/PATCH/DELETE request tool for API calls."""

    @property
    def name(self) -> str:
        return "web_post"

    @property
    def description(self) -> str:
        return (
            "Send HTTP POST/PUT/PATCH/DELETE request. "
            "Use 'body' for JSON request data. "
            "Use auth_provider='discord' for Discord Bot API calls."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to send request to"},
                "method": {
                    "type": "string",
                    "enum": ["POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method (default: POST)",
                },
                "body": {
                    "type": "object",
                    "description": "JSON body as key-value pairs (will be sent as JSON)",
                },
                "headers": {
                    "type": "object",
                    "description": "Custom headers as key-value pairs",
                    "additionalProperties": {"type": "string"},
                },
                "auth_provider": {
                    "type": "string",
                    "enum": ["discord"],
                    "description": "Pre-configured auth provider. Use 'discord' for Discord Bot API.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 100,
                    "description": "Max characters to return (default: 50000)",
                },
            },
            "required": ["url"],
        }

    def __init__(self, max_chars: int = 50000, auth_tokens: dict[str, str] | None = None):
        self.max_chars = max_chars
        self.auth_tokens = auth_tokens or {}

    def _is_safe_url(self, url: str) -> str | None:
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

    def _get_auth_headers(self, auth_provider: str) -> dict[str, str]:
        if auth_provider == "discord":
            token = self.auth_tokens.get("discord")
            if token:
                return {"Authorization": f"Bot {token}"}
        return {}

    async def execute(
        self,
        url: str,
        method: str = "POST",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        auth_provider: str | None = None,
        max_chars: int | None = None,
        **kwargs: Any,
    ) -> str:
        max_chars = max_chars or self.max_chars
        method = method.upper()

        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            return json.dumps(
                {
                    "error": f"Unsupported method: {method}. Use POST, PUT, PATCH, or DELETE.",
                    "url": url,
                }
            )

        safety_error = self._is_safe_url(url)
        if safety_error:
            return json.dumps({"error": safety_error, "url": url})

        if auth_provider == "discord":
            request_headers = {"User-Agent": DISCORD_USER_AGENT, "Content-Type": "application/json"}
        else:
            request_headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}

        if auth_provider:
            auth_headers = self._get_auth_headers(auth_provider)
            request_headers.update(auth_headers)

        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient() as client:
                if method == "POST":
                    r = await client.post(
                        url, headers=request_headers, json=body, follow_redirects=True, timeout=30.0
                    )
                elif method == "PUT":
                    r = await client.put(
                        url, headers=request_headers, json=body, follow_redirects=True, timeout=30.0
                    )
                elif method == "PATCH":
                    r = await client.patch(
                        url, headers=request_headers, json=body, follow_redirects=True, timeout=30.0
                    )
                elif method == "DELETE":
                    r = await client.delete(
                        url, headers=request_headers, follow_redirects=True, timeout=30.0
                    )
                else:
                    return json.dumps({"error": f"Unsupported method: {method}", "url": url})

            ctype = r.headers.get("content-type", "")

            if "application/json" in ctype:
                try:
                    text = json.dumps(r.json(), indent=2, ensure_ascii=False)
                    extractor = "json"
                except Exception:
                    text = r.text
                    extractor = "raw"
            else:
                text = r.text
                extractor = "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            response_headers = dict(r.headers)
            for key in response_headers:
                if key.lower() in ("authorization", "set-cookie", "x-api-key"):
                    response_headers[key] = "[REDACTED]"

            return json.dumps(
                {
                    "url": url,
                    "final_url": str(r.url),
                    "method": method,
                    "status": r.status_code,
                    "extractor": extractor,
                    "truncated": truncated,
                    "length": len(text),
                    "text": text,
                    "headers": response_headers,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})
