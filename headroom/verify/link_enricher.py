"""Link detection and content fetching for chat verification.

Extracts URLs from message text, fetches their content with a short
timeout, and returns a plain-text summary suitable for LLM context
injection.

Only the latest user message is scanned.  Historical messages are
left unchanged so the proxy doesn't re-fetch URLs from prior turns.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Matches http(s):// URLs including common punctuation while stopping
# before trailing ), ], ', ", or whitespace.
_URL_RE = re.compile(
    r"https?://[^\s\)\]\'\"\>]+"
)

# Maximum bytes to read from a fetched page — avoids pulling in giant
# HTML payloads.  ~30 KB is enough for article text extraction.
_MAX_RESPONSE_BYTES = 30_000

# Connect + read timeout seconds.
_FETCH_TIMEOUT = 8.0

# Number of chars of plain text to keep per URL in the injected block.
_MAX_PLAIN_TEXT_CHARS = 2_000


def extract_urls(text: str) -> list[str]:
    """Return all unique HTTP(S) URLs found in *text* preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _text_from_html(html: bytes) -> str:
    """Best-effort plain text extraction from raw HTML bytes."""
    try:
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.chunks: list[str] = []
                self._skip = False

            def handle_starttag(self, tag: str, attrs: Any) -> None:
                if tag in {"script", "style", "noscript"}:
                    self._skip = True

            def handle_endtag(self, tag: str) -> None:
                if tag in {"script", "style", "noscript"}:
                    self._skip = False

            def handle_data(self, data: str) -> None:
                if not self._skip:
                    stripped = data.strip()
                    if stripped:
                        self.chunks.append(stripped)

        parser = _Stripper()
        parser.feed(html.decode("utf-8", errors="replace"))
        return " ".join(parser.chunks)
    except Exception as exc:
        logger.debug("html strip failed: %s", exc)
        return html.decode("utf-8", errors="replace")


def fetch_url_text(url: str) -> str | None:
    """Fetch *url* and return up to ``_MAX_PLAIN_TEXT_CHARS`` of text.

    Returns *None* if the fetch fails or the response is binary.
    """
    try:
        import httpx

        with httpx.Client(follow_redirects=True, timeout=_FETCH_TIMEOUT) as client:
            resp = client.get(
                url,
                headers={"User-Agent": "Headroom-Verify/1.0 (content verification)"},
            )
            if resp.status_code >= 400:
                logger.debug("fetch %s → HTTP %d", url, resp.status_code)
                return None
            content_type = resp.headers.get("content-type", "")
            # Skip binary content types (images, videos, PDFs, etc.)
            if not any(t in content_type for t in ("text", "json", "xml", "html")):
                logger.debug("fetch %s → non-text content-type %s", url, content_type)
                return None
            raw = resp.content[:_MAX_RESPONSE_BYTES]
            if "html" in content_type:
                text = _text_from_html(raw)
            else:
                text = raw.decode("utf-8", errors="replace")
            return text[:_MAX_PLAIN_TEXT_CHARS].strip() or None
    except Exception as exc:
        logger.debug("fetch %s failed: %s", url, exc)
        return None


def enrich_urls_from_text(text: str) -> list[dict[str, str]]:
    """Return a list of ``{url, content}`` dicts for all URLs found in *text*.

    URLs that cannot be fetched are omitted from the result.
    """
    results: list[dict[str, str]] = []
    for url in extract_urls(text):
        content = fetch_url_text(url)
        if content:
            results.append({"url": url, "content": content})
    return results


def extract_text_from_latest_user_message(
    messages: list[dict[str, Any]],
) -> str:
    """Return the plain-text body of the last user message, or ``""``."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            return " ".join(parts)
    return ""
