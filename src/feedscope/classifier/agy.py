"""Wrapper around the Antigravity CLI (`agy`) for structured, batched classification.

## なぜ codex から移したのか

非対話の呼び出しを ChatGPT のサブスク枠から Antigravity 側へ逃がすため。
実測 (2026-08-24) で agy の quota は Gemini 系と Claude/GPT 系の 2 バケットに
完全に分かれており、Gemini 側は週次で Flash 換算 約 158M トークンぶんある。

## なぜ 1 記事 1 呼び出しをやめたのか

🔴 **agy は 1 ターンあたり input 約 13.8k トークンが固定で乗る** (実測: 「pong と
1 語返せ」で 13,846 tokens)。ツールが既定で 57 個露出しており、それを削る手段が
無いため、プロンプトの中身に関係なくこの床が付く。

一方 feedscope の記事本文は短い (median 75 文字 / p99 1,732 文字)。つまり
「1 記事 1 呼び出し」にすると **費用のほぼ全部がオーバーヘッド**になる。
1 回にまとめれば同じ 14k で 25 記事を裁けるので、桁で安くなる。

## agy 固有の注意 (どれも実測で踏んだ)

- 🔴 `-p` は**値を密着**させる (`-p=...`)。`-p "prompt" --output-format json` と
  書くと `-p` が `--output-format` をプロンプトとして食う。
- 🔴 `-p` は **stdin からプロンプトを読まない**。長文は argv 経由になるので
  **1 引数 128 KiB (MAX_ARG_STRLEN)** が上限。バッチはこの予算で分割する。
- 🔴 出力は `response` ではなく **`structured_output`** を読む。`response` には
  散文と tool の内部フィールド (`toolAction` 等) が混ざる。
- `--json-schema` を付けるとターンが 1 増える (= オーバーヘッドも 1 回ぶん増える)。
  パースの確実性のほうが大事なので受け入れる。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# 1 引数の上限は 128 KiB (MAX_ARG_STRLEN)。取りこぼしが出ないよう余裕を持たせる。
ARGV_BUDGET_BYTES = 96 * 1024


def build_batch_schema(category_names: list[str]) -> dict:
    """バッチ用スキーマ。入力の各記事に対して results の 1 要素が対応する。"""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "integer"},
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
                    "required": ["id", "summary", "scores"],
                },
            }
        },
        "required": ["results"],
    }


def run_agy(
    prompt: str,
    schema: dict,
    *,
    command: str = "agy",
    model: str | None = None,
    timeout: int = 600,
) -> dict:
    """agy を 1 回呼んで structured_output を返す。"""
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(
            f"{command!r} not found on PATH ({os.environ.get('PATH', '')!r}). "
            "Under systemd, set Environment=PATH=... in the unit, or use an "
            "absolute path via classifier.command in config.yaml."
        )

    encoded = len(prompt.encode("utf-8"))
    if encoded > ARGV_BUDGET_BYTES:
        # 呼び出し側が分割し損ねたときに、argv が溢れて出る意味不明なエラー
        # (E2BIG) ではなく原因の分かる例外にする。
        raise RuntimeError(
            f"prompt is {encoded} bytes, over the {ARGV_BUDGET_BYTES} byte argv budget; "
            "lower classifier.batch_size"
        )

    with tempfile.TemporaryDirectory() as td:
        schema_path = Path(td) / "schema.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

        args = [
            resolved,
            f"-p={prompt}",
            "--json-schema", str(schema_path),
            "--output-format", "json",
            # 自前の timeout より先に agy 側を切って、原因の分かるエラーで終わらせる。
            "--print-timeout", f"{max(1, timeout // 60 - 1)}m",
        ]
        if model:
            args += ["--model", model]

        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            # 記事本文は信頼できない入力なので、プロジェクトのルールや履歴を
            # 一切読ませない捨てディレクトリで走らせる。
            cwd=td,
        )

    if proc.returncode != 0:
        raise RuntimeError(
            f"agy exited {proc.returncode}: {(proc.stderr or '')[-400:]}"
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as ex:
        raise RuntimeError(f"agy output was not JSON: {(proc.stdout or '')[:300]}") from ex

    if envelope.get("status") != "SUCCESS":
        raise RuntimeError(f"agy failed: {str(envelope.get('error'))[:300]}")

    out = envelope.get("structured_output")
    if not isinstance(out, dict):
        raise RuntimeError(
            "agy returned no structured_output "
            f"(response={str(envelope.get('response'))[:200]})"
        )
    return out
