"""SQLite schema and helpers. Articles are append-only; nothing is deleted."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY,
  guid TEXT UNIQUE,
  url TEXT,
  title TEXT,
  source TEXT,
  source_category TEXT,
  published_at TEXT,
  fetched_at TEXT,
  content TEXT,
  summary TEXT,
  classified_at TEXT
);
CREATE TABLE IF NOT EXISTS scores (
  article_id INTEGER,
  category TEXT,
  score REAL,
  reason TEXT,
  PRIMARY KEY (article_id, category)
);
CREATE TABLE IF NOT EXISTS states (
  article_id INTEGER PRIMARY KEY,
  state TEXT
);
CREATE TABLE IF NOT EXISTS categories (
  name TEXT PRIMARY KEY,
  label TEXT,
  profile_text TEXT,
  threshold REAL,
  max_items INTEGER
);
CREATE TABLE IF NOT EXISTS feedback (
  article_id INTEGER,
  category TEXT,
  signal TEXT,
  ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_unclassified ON articles(classified_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def sync_categories(conn: sqlite3.Connection, categories) -> None:
    """Insert categories from config. On conflict keep the learned profile_text."""
    for c in categories:
        conn.execute(
            "INSERT INTO categories(name, label, profile_text, threshold, max_items) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "  label=excluded.label, threshold=excluded.threshold, max_items=excluded.max_items",
            (c.name, c.label, c.profile, c.threshold, c.max_items),
        )
    conn.commit()


def upsert_article(
    conn: sqlite3.Connection,
    *,
    guid: str,
    url: str,
    title: str,
    source: str,
    source_category: str,
    published_at: str,
    content: str,
    summary: str | None = None,
) -> tuple[int, bool]:
    """Insert an article if its guid is new. Returns (id, is_new). Never overwrites."""
    row = conn.execute("SELECT id FROM articles WHERE guid=?", (guid,)).fetchone()
    if row:
        return row["id"], False
    cur = conn.execute(
        "INSERT INTO articles(guid, url, title, source, source_category, "
        "published_at, fetched_at, content, summary, classified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,NULL)",
        (guid, url, title, source, source_category, published_at, now_iso(), content, summary),
    )
    aid = cur.lastrowid
    conn.execute("INSERT OR IGNORE INTO states(article_id, state) VALUES(?, 'unread')", (aid,))
    return aid, True


def get_unclassified(
    conn: sqlite3.Connection,
    limit: int | None = None,
    source_category: str | None = None,
):
    q = "SELECT * FROM articles WHERE classified_at IS NULL"
    params: list = []
    if source_category:
        q += " AND source_category=?"
        params.append(source_category)
    q += " ORDER BY id"
    if limit is not None:  # limit=0 means zero rows, not "no limit"
        q += f" LIMIT {int(limit)}"
    return conn.execute(q, params).fetchall()


def save_scores(conn: sqlite3.Connection, article_id: int, summary: str, scores: list[dict]) -> None:
    conn.execute(
        "UPDATE articles SET summary=?, classified_at=? WHERE id=?",
        (summary, now_iso(), article_id),
    )
    for s in scores:
        conn.execute(
            "INSERT INTO scores(article_id, category, score, reason) VALUES(?,?,?,?) "
            "ON CONFLICT(article_id, category) DO UPDATE SET "
            "  score=excluded.score, reason=excluded.reason",
            (article_id, s["category"], float(s["score"]), s.get("reason", "")),
        )
    conn.commit()
