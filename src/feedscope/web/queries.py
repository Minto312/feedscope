"""Read/write queries for the viewer. Per-category counts are independent."""

from __future__ import annotations

from ..db import now_iso


def category_counts(conn, categories) -> dict:
    """Unread count per category = unread articles whose score in that category >= threshold.

    Independent per category (Discover の「枠の奪い合い」対策): reading one category
    never changes another's count.
    """
    counts = {}
    for c in categories:
        row = conn.execute(
            "SELECT COUNT(DISTINCT a.id) FROM articles a "
            "JOIN scores s ON s.article_id = a.id "
            "JOIN states st ON st.article_id = a.id "
            "WHERE s.category = ? AND s.score >= ? AND st.state = 'unread'",
            (c.name, c.threshold),
        ).fetchone()
        counts[c.name] = row[0]
    return counts


def feed_articles(conn, category: str, threshold: float, limit: int):
    return conn.execute(
        "SELECT a.id, a.title, a.url, a.source, a.summary, s.score, s.reason "
        "FROM articles a "
        "JOIN scores s ON s.article_id = a.id "
        "JOIN states st ON st.article_id = a.id "
        "WHERE s.category = ? AND s.score >= ? AND st.state = 'unread' "
        "ORDER BY s.score DESC, a.id DESC LIMIT ?",
        (category, threshold, int(limit)),
    ).fetchall()


def saved_articles(conn, limit: int = 200):
    return conn.execute(
        "SELECT a.id, a.title, a.url, a.source, a.summary "
        "FROM articles a JOIN states st ON st.article_id = a.id "
        "WHERE st.state = 'saved' ORDER BY a.id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()


def set_state(conn, article_id: int, state: str) -> None:
    conn.execute(
        "INSERT INTO states(article_id, state) VALUES(?, ?) "
        "ON CONFLICT(article_id) DO UPDATE SET state = excluded.state",
        (article_id, state),
    )
    conn.commit()


def add_feedback(conn, article_id: int, category: str, signal: str) -> None:
    conn.execute(
        "INSERT INTO feedback(article_id, category, signal, ts) VALUES(?, ?, ?, ?)",
        (article_id, category, signal, now_iso()),
    )
    conn.commit()
