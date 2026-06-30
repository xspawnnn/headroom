"""Screenshot / image OCR extraction for chat verification.

Finds base64-encoded images in the latest user message and extracts
their text via the existing Headroom OCR pipeline (RapidOCR).

Returns extracted text per image so the caller can inject it as
context before the message reaches the LLM.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _ocr_image_bytes(data: bytes) -> str | None:
    """Run OCR on raw image bytes and return the extracted text, or None."""
    try:
        from headroom.image.compressor import _resolve_rapidocr

        ocr_cls, api_version = _resolve_rapidocr()
        if ocr_cls is None:
            return None
        ocr = ocr_cls()
        result = ocr(data)
        if api_version == "v1":
            if result is None or not result[0]:
                return None
            lines = [item[1] for item in result[0] if item and len(item) > 1]
        else:
            if result is None or not result.txts:
                return None
            lines = list(result.txts)
        text = "\n".join(str(l) for l in lines if l).strip()
        return text or None
    except Exception as exc:
        logger.debug("OCR failed: %s", exc)
        return None


def _decode_base64_image(data_url_or_b64: str) -> bytes | None:
    """Decode a base64 image string (with or without data-URL prefix)."""
    try:
        if data_url_or_b64.startswith("data:"):
            _, encoded = data_url_or_b64.split(",", 1)
        else:
            encoded = data_url_or_b64
        return base64.b64decode(encoded)
    except Exception as exc:
        logger.debug("base64 decode failed: %s", exc)
        return None


def extract_images_from_message(
    message: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return a list of image blocks from an Anthropic-style message."""
    content = message.get("content", [])
    if not isinstance(content, list):
        return []
    images: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "image":
            src = block.get("source", {})
            if src.get("type") == "base64":
                images.append(block)
        elif btype == "image_url":
            url_val = block.get("image_url", {})
            url = url_val.get("url", "") if isinstance(url_val, dict) else str(url_val)
            if url.startswith("data:"):
                images.append(block)
    return images


def ocr_latest_user_images(
    messages: list[dict[str, Any]],
) -> list[str]:
    """OCR all images in the last user message.

    Returns a list of non-empty extracted text strings, one per image.
    """
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        image_blocks = extract_images_from_message(msg)
        texts: list[str] = []
        for block in image_blocks:
            btype = block.get("type")
            raw: bytes | None = None
            if btype == "image":
                src = block.get("source", {})
                raw = _decode_base64_image(src.get("data", ""))
            elif btype == "image_url":
                url_val = block.get("image_url", {})
                url = url_val.get("url", "") if isinstance(url_val, dict) else str(url_val)
                raw = _decode_base64_image(url)
            if raw:
                text = _ocr_image_bytes(raw)
                if text:
                    texts.append(text)
        return texts  # only process the latest user message
    return []
