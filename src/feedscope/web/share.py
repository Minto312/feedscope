"""Accept a page shared from a phone (Web Share Target) and save it to the library."""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.request
from urllib.parse import urlparse

from ..db import now_iso, upsert_article

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_WS_RE = re.compile(r"\s+")


def extract_url(url: str | None, text: str | None) -> str | None:
    """Android often puts the link in `text` instead of `url`; accept either."""
    for candidate in (url, text):
        if not candidate:
            continue
        m = _URL_RE.search(candidate)
        if m:
            return m.group(0).rstrip(").,")
    return None


def _is_fetchable(url: str) -> bool:
    """Only fetch public http(s) hosts — don't let a shared link probe the LAN."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except OSError:
        return False
    for *_, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


def fetch_title(url: str, timeout: int = 8, max_bytes: int = 262144) -> str | None:
    """Best-effort <title> of the shared page. Returns None on any problem."""
    if not _is_fetchable(url):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower():
                return None
            raw = resp.read(max_bytes)
            charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    except Exception:
        return None

    m = _TITLE_RE.search(html)
    if not m:
        return None
    title = _WS_RE.sub(" ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
    return title or None


def save_shared(conn, url: str, title: str | None = None, note: str | None = None) -> dict:
    """Save a shared URL straight into the library (state='saved').

    Returns {'article_id', 'title', 'already_saved'}.
    """
    row = conn.execute(
        "SELECT a.id, a.title, st.state FROM articles a "
        "LEFT JOIN states st ON st.article_id = a.id WHERE a.url = ? OR a.guid = ? LIMIT 1",
        (url, url),
    ).fetchone()

    if row:
        article_id = row["id"]
        resolved = row["title"]
        already = row["state"] == "saved"
    else:
        resolved = (title or "").strip() or fetch_title(url) or url
        article_id, _ = upsert_article(
            conn,
            guid=url,
            url=url,
            title=resolved,
            source="共有",
            source_category="shared",
            published_at=now_iso(),
            content=(note or "").strip(),
        )
        already = False

    conn.execute(
        "INSERT INTO states(article_id, state) VALUES(?, 'saved') "
        "ON CONFLICT(article_id) DO UPDATE SET state='saved'",
        (article_id,),
    )
    conn.commit()
    return {"article_id": article_id, "title": resolved, "already_saved": already}
