"""Content verification module for Headroom.

Automatically fetches linked URLs and extracts text from screenshots
posted in chat sessions, then injects the enriched context into the
message stream so the LLM can verify or research the content.

Usage (via ProxyConfig):
    config = ProxyConfig(verify_links_and_screenshots=True)

Usage (via hook directly):
    from headroom.verify import make_verify_hook
    config = ProxyConfig(hooks=make_verify_hook())
"""

from .enrichment_hook import ContentVerifyHook, make_verify_hook

__all__ = ["ContentVerifyHook", "make_verify_hook"]
