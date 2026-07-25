"""Wrapper around `codex exec` for structured article classification.

Uses `codex exec --output-schema <schema> -o <out>` to force the model's final
message into a JSON shape, then reads that file. The prompt is passed via stdin
(`-`) so long article bodies don't hit argv length limits.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def build_schema(category_names: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "category": {"type": "string", "enum": category_names},
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["category", "score", "reason"],
                },
            },
        },
        "required": ["summary", "scores"],
    }


def run_codex(
    prompt: str,
    schema: dict,
    *,
    command: str = "codex",
    model: str | None = None,
    timeout: int = 180,
) -> dict:
    if shutil.which(command) is None:
        raise RuntimeError(
            f"{command!r} not found on PATH ({os.environ.get('PATH', '')!r}). "
            "Under systemd, set Environment=PATH=... in the unit, or use an "
            "absolute path via classifier.command in config.yaml."
        )

    with tempfile.TemporaryDirectory() as td:
        schema_path = Path(td) / "schema.json"
        out_path = Path(td) / "out.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

        args = [
            command, "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-s", "read-only",
            "--color", "never",
        ]
        if model:
            args += ["-m", model]
        args += ["--output-schema", str(schema_path), "-o", str(out_path), "-"]

        proc = subprocess.run(
            args, input=prompt, text=True, capture_output=True, timeout=timeout
        )
        if not out_path.exists():
            raise RuntimeError(
                f"codex produced no output (rc={proc.returncode}): {(proc.stderr or '')[-400:]}"
            )
        raw = out_path.read_text(encoding="utf-8").strip()

    if not raw:
        raise RuntimeError("codex output was empty")
    return json.loads(raw)
