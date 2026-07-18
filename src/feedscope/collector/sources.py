"""Resolve a Source into a fetchable URL and iterate config sources."""

from __future__ import annotations

from urllib.parse import quote

GNEWS_TMPL = "https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"


def source_url(src) -> str:
    if src.type == "gnews":
        return GNEWS_TMPL.format(q=quote(src.query or ""))
    return src.url


def iter_sources(config):
    for cat in config.categories:
        for src in cat.sources:
            yield cat, src
