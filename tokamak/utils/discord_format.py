"""Discord message formatting utilities."""

import re

DISCORD_MAX_LENGTH = 2000
DISCORD_SAFE_LENGTH = 1900


def format_discord_message(content: str) -> str:
    """
    Format message for Discord by removing unsupported markdown and fixing links.

    Args:
        content: Raw message content

    Returns:
        Formatted message content
    """
    content = re.sub(r"\n---+\n", "\n\n", content)
    content = re.sub(r"^---+$", "", content, flags=re.MULTILINE)

    masked_links = []
    markdown_link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"

    def protect_masked_link(match):
        text = match.group(1)
        url = match.group(2).strip("<>")
        masked_links.append((text, url))
        return f"__MASKED_LINK_{len(masked_links) - 1}__"

    content = re.sub(markdown_link_pattern, protect_masked_link, content)

    code_spans = []

    def protect_code_span(match):
        code_spans.append(match.group(0))
        return f"__CODE_SPAN_{len(code_spans) - 1}__"

    content = re.sub(r"`[^`]+`", protect_code_span, content)

    def replace_bare_urls(match):
        return f"<{match.group(0)}>"

    url_pattern = r"(?<!<)https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+(?!>)"
    content = re.sub(url_pattern, replace_bare_urls, content)

    for i, (text, url) in enumerate(masked_links):
        if text.startswith(("http://", "https://")):
            content = content.replace(f"__MASKED_LINK_{i}__", f"<{url}>")
        else:
            content = content.replace(f"__MASKED_LINK_{i}__", f"[{text}](<{url}>)")

    for i, span in enumerate(code_spans):
        content = content.replace(f"__CODE_SPAN_{i}__", span)

    content = re.sub(r" +$", "", content, flags=re.MULTILINE)

    content = re.sub(r"\n{3,}", "\n\n", content)

    return content


def split_message(content: str, max_length: int = DISCORD_SAFE_LENGTH) -> list[str]:
    """Split a message into chunks that fit within Discord's character limit.

    Splits on newline boundaries when possible, falling back to hard cut.
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    while content:
        if len(content) <= max_length:
            chunks.append(content)
            break

        cut = content.rfind("\n", 0, max_length)
        if cut <= 0:
            cut = max_length

        chunks.append(content[:cut])
        content = content[cut:].lstrip("\n")

    return chunks
