"""ContentVerifyHook — pre_compress hook for auto link + screenshot verification.

When enabled, this hook intercepts the latest user message before
compression and:

1. Detects HTTP/HTTPS URLs → fetches each page → appends a
   ``[Headroom: Link Content]`` block so the LLM sees the page text.

2. Detects base64 images (screenshots) → runs OCR → appends a
   ``[Headroom: Screenshot Text]`` block with the extracted text.

The injected context is labelled clearly so the LLM knows the source.
Both steps are best-effort: failures are logged at DEBUG and skipped,
so a network hiccup or missing OCR dependency never breaks the request.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from headroom.hooks import CompressContext, CompressionHooks

from .link_enricher import enrich_urls_from_text, extract_text_from_latest_user_message
from .screenshot_reader import ocr_latest_user_images

logger = logging.getLogger(__name__)

# Separator used inside the injected block.
_SEP = "\n\n---\n"

# Maximum number of URLs to fetch per turn (avoids runaway latency on
# link-heavy messages).
_MAX_URLS_PER_TURN = 3


def _build_context_block(
    url_results: list[dict[str, str]],
    ocr_texts: list[str],
) -> str:
    """Format the enrichment context as a clear labelled text block."""
    parts: list[str] = []

    for item in url_results:
        url = item["url"]
        content = item["content"]
        parts.append(
            f"[Headroom: Link Content — {url}]\n{content}"
        )

    for i, text in enumerate(ocr_texts, start=1):
        label = "Screenshot" if len(ocr_texts) == 1 else f"Screenshot {i}"
        parts.append(f"[Headroom: {label} Text (OCR)]\n{text}")

    if not parts:
        return ""

    joined = _SEP.join(parts)
    return f"\n\n---\n[Headroom: Content Analysis]\n{joined}\n---"


def _append_to_latest_user_message(
    messages: list[dict[str, Any]],
    extra_text: str,
) -> list[dict[str, Any]]:
    """Return a shallow-copy of *messages* with *extra_text* appended to
    the last user message's text.  Returns the original list unchanged if
    no eligible user message is found."""
    if not extra_text:
        return messages

    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        new_msg = copy.copy(msg)

        if isinstance(content, str):
            new_msg["content"] = content + extra_text
            new_messages = list(messages)
            new_messages[i] = new_msg
            return new_messages

        if isinstance(content, list):
            new_content = list(content)
            # Find the last text block and append to it.
            for j in range(len(new_content) - 1, -1, -1):
                block = new_content[j]
                if isinstance(block, dict) and block.get("type") == "text":
                    new_block = dict(block)
                    new_block["text"] = str(block.get("text", "")) + extra_text
                    new_content[j] = new_block
                    new_msg["content"] = new_content
                    new_messages = list(messages)
                    new_messages[i] = new_msg
                    return new_messages
            # No text block found — add one.
            new_content.append({"type": "text", "text": extra_text.lstrip()})
            new_msg["content"] = new_content
            new_messages = list(messages)
            new_messages[i] = new_msg
            return new_messages

        break  # unrecognised content type

    return messages


class ContentVerifyHook(CompressionHooks):
    """Hook that enriches chat messages with fetched link/screenshot content.

    Designed to be composed with an existing hooks instance:

        class MyHooks(ContentVerifyHook, MyExistingHooks):
            ...

    Or used standalone:

        config = ProxyConfig(hooks=ContentVerifyHook())
    """

    def pre_compress(
        self,
        messages: list[dict[str, Any]],
        ctx: CompressContext,
    ) -> list[dict[str, Any]]:
        messages = super().pre_compress(messages, ctx)

        try:
            user_text = extract_text_from_latest_user_message(messages)

            url_results: list[dict[str, str]] = []
            if user_text:
                from .link_enricher import enrich_urls_from_text, extract_urls

                urls = extract_urls(user_text)[:_MAX_URLS_PER_TURN]
                if urls:
                    logger.debug(
                        "verify: fetching %d URL(s) from latest user message", len(urls)
                    )
                    url_results = enrich_urls_from_text(user_text)
                    if url_results:
                        logger.info(
                            "verify: enriched %d URL(s) in turn %d",
                            len(url_results),
                            ctx.turn_number,
                        )

            ocr_texts = ocr_latest_user_images(messages)
            if ocr_texts:
                logger.info(
                    "verify: OCR extracted text from %d image(s)", len(ocr_texts)
                )

            context_block = _build_context_block(url_results, ocr_texts)
            if context_block:
                messages = _append_to_latest_user_message(messages, context_block)

        except Exception as exc:
            logger.debug("verify: enrichment failed (skipping): %s", exc)

        return messages


def make_verify_hook(
    base_hooks: CompressionHooks | None = None,
) -> CompressionHooks:
    """Create a ``ContentVerifyHook`` that optionally wraps *base_hooks*.

    If *base_hooks* is provided its ``pre_compress`` / ``post_compress``
    etc. are called first, then the verify enrichment runs on the result.
    """
    if base_hooks is None:
        return ContentVerifyHook()

    # Dynamic subclass that delegates to base_hooks then runs enrichment.
    class _Combined(ContentVerifyHook):
        def pre_compress(
            self,
            messages: list[dict[str, Any]],
            ctx: CompressContext,
        ) -> list[dict[str, Any]]:
            messages = base_hooks.pre_compress(messages, ctx)
            return ContentVerifyHook.pre_compress(self, messages, ctx)

        def compute_biases(
            self,
            messages: list[dict[str, Any]],
            ctx: CompressContext,
        ) -> dict[int, float]:
            return base_hooks.compute_biases(messages, ctx)

        def post_compress(self, event: Any) -> None:
            base_hooks.post_compress(event)

        def on_pipeline_event(self, event: Any) -> Any:
            return base_hooks.on_pipeline_event(event)

    return _Combined()
