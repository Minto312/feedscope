"""HTTP feed fetching with a browser UA and 429/5xx backoff (see docs/sources.md)."""

from __future__ import annotations

import socket
import time

import feedparser

RETRY_STATUS = {429, 500, 502, 503, 504}


def fetch_feed(
    url: str,
    *,
    user_agent: str,
    timeout: int = 20,
    max_retries: int = 3,
    base_backoff: float = 2.0,
):
    """Return (parsed, error). parsed is a feedparser result on success, else None."""
    socket.setdefaulttimeout(timeout)
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        try:
            d = feedparser.parse(url, agent=user_agent)
        except Exception as ex:  # network / parser blow-up
            last_err = f"exception: {ex}"
            time.sleep(base_backoff**attempt)
            continue

        status = getattr(d, "status", None)
        if status in RETRY_STATUS:
            last_err = f"HTTP {status}"
            time.sleep(base_backoff**attempt)
            continue
        if getattr(d, "entries", None):
            return d, None
        # No entries: retry on transient parse/network noise, otherwise give up.
        if getattr(d, "bozo", 0) and not status:
            last_err = str(getattr(d, "bozo_exception", "parse error"))
            time.sleep(base_backoff**attempt)
            continue
        return None, last_err or (f"HTTP {status}" if status and status != 200 else "no entries")
    return None, last_err
