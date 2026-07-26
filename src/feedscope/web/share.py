"""Accept a page shared from a phone (Web Share Target) and save it to the library.

Security notes — /add is unauthenticated (anyone on the tailnet can POST to it) and
takes an attacker-chosen URL, so title fetching is deliberately conservative:

* Only globally-routable hosts are fetched. `is_global` rejects loopback, RFC1918,
  link-local (cloud metadata), and CGNAT 100.64/10 — which is the tailnet range,
  so a shared link cannot probe tailnet peers. Multicast is excluded separately
  because `is_global` considers it routable.
* Redirects are followed manually and every hop is re-validated. Letting urllib
  auto-follow would defeat the check above with a single 302 to 127.0.0.1.
* The fetch runs off the request thread on a small bounded pool, so a slow or
  silent URL can't tie up the server.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from ..db import connect, now_iso, upsert_article

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_WS_RE = re.compile(r"\s+")

FETCH_TIMEOUT = 5
MAX_REDIRECTS = 3
MAX_BYTES = 262144
MAX_PENDING = 8

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="share-title")
_pending = 0
_pending_lock = threading.Lock()


def extract_url(url: str | None, text: str | None) -> str | None:
    """Android often puts the link in `text` instead of `url`; accept either."""
    for candidate in (url, text):
        if not candidate:
            continue
        m = _URL_RE.search(candidate)
        if m:
            return m.group(0).rstrip(").,")
    return None


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface redirects instead of following them, so each hop can be checked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoAutoRedirect)


def _is_public_host(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except OSError:
        return False
    if not infos:
        return False
    for *_, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        # Allowlist: only globally routable unicast. Blocks loopback, RFC1918,
        # link-local, reserved, and CGNAT (tailnet). Multicast is "global" but
        # must not be fetched either.
        if not ip.is_global or ip.is_multicast:
            return False
    return True


def fetch_title(url: str) -> str | None:
    """Best-effort <title> of the shared page. Returns None on any problem."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_public_host(current):
            return None
        req = urllib.request.Request(current, headers={"User-Agent": UA})
        try:
            with _opener.open(req, timeout=FETCH_TIMEOUT) as resp:
                if "html" not in resp.headers.get("Content-Type", "").lower():
                    return None
                raw = resp.read(MAX_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
            break
        except urllib.error.HTTPError as ex:
            if ex.code in (301, 302, 303, 307, 308):
                location = ex.headers.get("Location")
                if not location:
                    return None
                current = urljoin(current, location)  # re-validated on next pass
                continue
            return None
        except Exception:
            return None
    else:
        return None  # too many redirects

    html = raw.decode(charset, errors="replace")
    m = _TITLE_RE.search(html)
    if not m:
        return None
    title = _WS_RE.sub(" ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
    return title or None


def _resolve_title_async(db_path, article_id: int, url: str) -> None:
    """Fill in the title after the share request has already returned."""
    global _pending
    try:
        title = fetch_title(url)
        if title:
            conn = connect(db_path)
            try:
                conn.execute(
                    "UPDATE articles SET title = ? WHERE id = ? AND title = ?",
                    (title, article_id, url),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass
    finally:
        with _pending_lock:
            _pending -= 1


def save_shared(conn, url: str, title: str | None = None, note: str | None = None,
                db_path=None) -> dict:
    """Save a shared URL straight into the library (state='saved').

    Returns immediately; if no title was supplied the page is fetched in the
    background and the row is updated when it arrives.
    """
    global _pending

    row = conn.execute(
        "SELECT a.id, a.title, st.state FROM articles a "
        "LEFT JOIN states st ON st.article_id = a.id WHERE a.url = ? OR a.guid = ? LIMIT 1",
        (url, url),
    ).fetchone()

    fetching = False
    if row:
        article_id = row["id"]
        resolved = row["title"]
        already = row["state"] == "saved"
    else:
        resolved = (title or "").strip() or url
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
        if resolved == url and db_path is not None:
            with _pending_lock:
                if _pending < MAX_PENDING:
                    _pending += 1
                    fetching = True
            if fetching:
                _pool.submit(_resolve_title_async, db_path, article_id, url)

    conn.execute(
        "INSERT INTO states(article_id, state) VALUES(?, 'saved') "
        "ON CONFLICT(article_id) DO UPDATE SET state='saved'",
        (article_id,),
    )
    # Record that this came from the share sheet. Kept separate from `source` so a
    # already-collected article keeps its original outlet (e.g. AUTOMATON) and just
    # gains a "shared" marker.
    conn.execute(
        "UPDATE articles SET shared_at = COALESCE(shared_at, ?) WHERE id = ?",
        (now_iso(), article_id),
    )
    conn.commit()
    return {
        "article_id": article_id,
        "title": resolved,
        "already_saved": already,
        "fetching_title": fetching,
    }
