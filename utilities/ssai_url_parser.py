"""Parse AMGID / Channel_Code / Platform_ID from now3 Stream URLs."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_now3_stream_url(stream_url: str) -> Dict[str, Optional[str]]:
    """
    Extract Amagi IDs from a now3 playout Stream URL.

    Returns:
      {
        "ok": True/False,
        "triple": "amg-channel-platform" or None,
        "amg_id": ...,
        "channel_id": ...,
        "platform_id": ...,
        "error": None or str,
      }
    """

    def _success(triple: str, parts: Tuple[str, str, str]) -> Dict[str, Optional[str]]:
        amg, ch, plat = parts
        return {
            "ok": True,
            "triple": triple,
            "amg_id": amg,
            "channel_id": ch,
            "platform_id": plat,
            "error": None,
        }

    def _fail(msg: str) -> Dict[str, Optional[str]]:
        logger.warning("ssai_url_parser failed: %s (url=%s)", msg, stream_url)
        return {
            "ok": False,
            "triple": None,
            "amg_id": None,
            "channel_id": None,
            "platform_id": None,
            "error": msg,
        }

    if not stream_url or not isinstance(stream_url, str):
        return _fail("empty or invalid URL")

    test_url = stream_url if "://" in stream_url else f"http://{stream_url}"
    parsed = urlparse(test_url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").strip("/")

    if host and ".playout." in host:
        left = host.split(".playout.", 1)[0]
        left_last_label = left.split(".")[-1]
        if "-" in left_last_label:
            parts = left_last_label.split("-")
            if len(parts) == 3 and all(parts):
                result = _success(left_last_label, (parts[0], parts[1], parts[2]))
                logger.info(
                    "Parsed now3 IDs from host: amg_id=%s channel_id=%s platform_id=%s",
                    result["amg_id"],
                    result["channel_id"],
                    result["platform_id"],
                )
                return result

    if path:
        segs = path.split("/")
        try:
            i = segs.index("playout")
            if len(segs) >= i + 4:
                amg, ch, plat = segs[i + 1], segs[i + 2], segs[i + 3]
                if amg and ch and plat:
                    triple = f"{amg}-{ch}-{plat}"
                    result = _success(triple, (amg, ch, plat))
                    logger.info(
                        "Parsed now3 IDs from path: amg_id=%s channel_id=%s platform_id=%s",
                        result["amg_id"],
                        result["channel_id"],
                        result["platform_id"],
                    )
                    return result
        except ValueError:
            pass

    return _fail("could not locate <amg>-<channel>-<platform> in host or path")
