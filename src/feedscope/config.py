"""Load and parse config.yaml into typed objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Source:
    type: str
    name: str
    lang: str = "ja"
    url: str | None = None
    query: str | None = None


@dataclass
class Category:
    name: str
    label: str
    threshold: float
    max_items: int
    profile: str
    sources: list[Source]


@dataclass
class Config:
    categories: list[Category]
    classifier: dict
    fetch: dict
    schedule: dict
    database: dict
    path: Path

    @property
    def db_path(self) -> Path:
        p = Path(self.database.get("path", "feedscope.db"))
        if not p.is_absolute():
            p = self.path.parent / p
        return p

    @property
    def user_agent(self) -> str:
        return self.fetch.get("user_agent", "feedscope/0.1 (+https://github.com/Minto312/feedscope)")


def load_config(path: str | Path = "config.yaml") -> Config:
    path = Path(path).resolve()
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    categories: list[Category] = []
    for c in raw.get("categories", []):
        sources = [Source(**s) for s in c.get("sources", [])]
        categories.append(
            Category(
                name=c["name"],
                label=c.get("label", c["name"]),
                threshold=float(c.get("threshold", 6)),
                max_items=int(c.get("max_items", 60)),
                profile=(c.get("profile") or "").strip(),
                sources=sources,
            )
        )

    return Config(
        categories=categories,
        classifier=raw.get("classifier", {}) or {},
        fetch=raw.get("fetch", {}) or {},
        schedule=raw.get("schedule", {}) or {},
        database=raw.get("database", {}) or {},
        path=path,
    )
