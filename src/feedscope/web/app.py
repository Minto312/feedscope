"""Flask viewer: per-topic tabs, vertical card feed, keep-forever library."""

from __future__ import annotations

from flask import Flask, abort, redirect, render_template, request, url_for

from ..db import connect, init_schema
from . import queries


def create_app(config) -> Flask:
    app = Flask(__name__)

    def by_name(name):
        for c in config.categories:
            if c.name == name:
                return c
        return None

    @app.route("/")
    def index():
        if not config.categories:
            return "no categories configured", 200
        return redirect(url_for("feed", category=config.categories[0].name))

    @app.route("/c/<category>")
    def feed(category):
        cat = by_name(category)
        if not cat:
            abort(404)
        conn = connect(config.db_path)
        init_schema(conn)
        counts = queries.category_counts(conn, config.categories)
        articles = queries.feed_articles(conn, cat.name, cat.threshold, cat.max_items)
        conn.close()
        return render_template(
            "feed.html",
            categories=config.categories,
            counts=counts,
            current=cat,
            articles=articles,
        )

    @app.route("/library")
    def library():
        conn = connect(config.db_path)
        init_schema(conn)
        counts = queries.category_counts(conn, config.categories)
        articles = queries.saved_articles(conn)
        conn.close()
        return render_template(
            "library.html",
            categories=config.categories,
            counts=counts,
            articles=articles,
        )

    @app.route("/api/article/<int:article_id>/<action>", methods=["POST"])
    def article_action(article_id, action):
        category = request.form.get("category") or request.args.get("category")
        conn = connect(config.db_path)
        try:
            if action == "save":
                queries.set_state(conn, article_id, "saved")
                if category:
                    queries.add_feedback(conn, article_id, category, "like")
            elif action == "dislike":
                if category:
                    queries.add_feedback(conn, article_id, category, "dislike")
                queries.set_state(conn, article_id, "read")
            elif action == "read":
                queries.set_state(conn, article_id, "read")
            else:
                abort(400)
        finally:
            conn.close()
        return ("", 204)

    return app
