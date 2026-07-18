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
        print(f"classifying (limit={args.limit}) ...")
        r = classify(cfg, limit=args.limit)
        print(f"\nclassify done: {r['classified']} ok / {r['failed']} failed / {r['total']} pending")


if __name__ == "__main__":
    main()
