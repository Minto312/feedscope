"""feedscope CLI: initdb / collect / classify."""

from __future__ import annotations

import argparse

from .classifier.classify import classify
from .collector.collect import collect
from .config import load_config
from .db import connect, init_schema, sync_categories


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="feedscope")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("initdb", help="create the SQLite schema and sync categories")
    sub.add_parser("collect", help="fetch all sources and append new articles")
    pc = sub.add_parser("classify", help="classify unclassified articles via codex")
    pc.add_argument("--limit", type=int, default=None, help="max articles to classify")
    pc.add_argument("--source-category", default=None, help="only classify articles from this source category")
    pc.add_argument("--per-category", type=int, default=None,
                    help="classify N pending articles from EACH source category (fair share)")
    pc.add_argument("--order", choices=["newest", "oldest"], default="newest",
                    help="which pending articles to take first (default: newest)")
    ps = sub.add_parser("serve", help="run the web viewer")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=5000)

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "initdb":
        conn = connect(cfg.db_path)
        init_schema(conn)
        sync_categories(conn, cfg.categories)
        conn.close()
        print(f"initialized {cfg.db_path}")

    elif args.cmd == "collect":
        print(f"collecting into {cfg.db_path} ...")
        r = collect(cfg)
        print(
            f"\ncollect done: {r['total_new']} new / {r['total_seen']} seen "
            f"across {len(r['sources'])} sources"
        )

    elif args.cmd == "classify":
        print(
            f"classifying (limit={args.limit}, per_category={args.per_category}, "
            f"source_category={args.source_category}, order={args.order}) ..."
        )
        r = classify(
            cfg,
            limit=args.limit,
            source_category=args.source_category,
            per_category=args.per_category,
            order=args.order,
        )
        print(f"\nclassify done: {r['classified']} ok / {r['failed']} failed / {r['total']} pending")
        # Exit non-zero when nothing succeeded but work was attempted, so a
        # scheduler (systemd) surfaces the failure instead of reporting success.
        if r["failed"] and not r["classified"]:
            raise SystemExit(1)

    elif args.cmd == "serve":
        from .web.app import create_app

        app = create_app(cfg)
        print(f"serving on http://{args.host}:{args.port}  (db: {cfg.db_path})")
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
