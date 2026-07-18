"""Collect: fetch every configured source, normalize, dedup by guid, append to SQLite."""

from __future__ import annotations

import re
import time

from ..db import connect, init_schema, sync_categories, upsert_article
from .fetch import fetch_feed
from .sources import iter_sources, source_url

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(s: str | None, limit: int = 6000) -> str:
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s[:limit]


def _entry_guid(e) -> str:
    return e.get("id") or e.get("link") or f"{e.get('title', '')}|{e.get('published', '')}"


def _entry_content(e) -> str:
    if e.get("content"):
        return e["content"][0].get("value", "")
    return e.get("summary", "") or e.get("description", "")


def collect(config, verbose: bool = True) -> dict:
    conn = connect(config.db_path)
    init_schema(conn)
    sync_categories(conn, config.categories)

    ua = config.user_agent
    fetch_cfg = config.fetch
    delay = float(fetch_cfg.get("per_request_delay_ms", 500)) / 1000.0
    max_retries = int(fetch_cfg.get("max_retries", 3))

    total_new = total_seen = 0
    per_source = []

    for cat, src in iter_sources(config):
        url = source_url(src)
        d, err = fetch_feed(url, user_agent=ua, max_retries=max_retries)
        n = n_new = 0
        if d and d.entries:
            for e in d.entries:
                n += 1
                _, is_new = upsert_article(
                    conn,
                    guid=_entry_guid(e),
                    url=e.get("link", ""),
                    title=(e.get("title", "") or "").strip(),
                    source=src.name,
                    source_category=cat.name,
                    published_at=e.get("published", e.get("updated", "")),
                    content=clean_text(_entry_content(e)),
                )
                if is_new:
                    n_new += 1
            conn.commit()

        total_new += n_new
        total_seen += n
        per_source.append((cat.name, src.name, n, n_new, err))
        if verbose:
            status = f"{n_new:+4d} new / {n:4d}" if (d and d.entries) else f"ERR: {err}"
            print(f"  [{cat.name:16}] {src.name:30} {status}")
        time.sleep(delay)

    conn.close()
    return {"total_seen": total_seen, "total_new": total_new, "sources": per_source}
