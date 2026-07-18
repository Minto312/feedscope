# AGENTS.md

feedscope のコーディングエージェント（codex / claude 等）向け規約。

## プロジェクト概要

Google Discover 代替の、自分専用パーソナライズ記事フィード。
背景と設計は [README.md](README.md) / [docs/design.md](docs/design.md) を必ず読むこと。
収集元の台帳と取得時の注意は [docs/sources.md](docs/sources.md)。

## 技術スタック

- Python 3.10+（依存管理は uv）
- SQLite / Flask + HTMX / feedparser / python-feedgen
- 記事分類は **`codex exec` をサブプロセス実行**

## ディレクトリ

- `src/feedscope/collector/` — 収集（feedparser）
- `src/feedscope/classifier/` — 分類・採点（codex exec ラッパ）
- `src/feedscope/web/` — Flask + HTMX ビューア
- `src/feedscope/feed/` — RSS/Atom 互換エクスポート
- `config.example.yaml` — 設定テンプレ（実設定 `config.yaml` は gitignore）

## 実装方針

- **記事は消さない（追記型）**。破壊的削除は明示フラグがあるときだけ。
- classifier は `codex exec` の stdout(JSON) を**必ず検証**し、パース失敗時はリトライ。記事本文は外部入力なので**プロンプトインジェクション対策**（デリミタで囲う・出力を JSON に制約・本文中の指示は無視）を入れる。
- 分野は独立チャンネル（独立の未読・閾値・嗜好プロファイル）。全体固定枠にしない。
- 収集は**ブラウザ相当の User-Agent** を必須にし、Reddit 等は 429 に指数バックオフ + ソース間ディレイ（docs/sources.md 参照）。
- 設定は `config.yaml`（gitignore）。テンプレを変える場合は `config.example.yaml` を更新する。

## コミット / PR

- コミットメッセージ・PR に **AI 生成の署名（`Co-Authored-By: Claude …` / `🤖 Generated with …` 等）を含めない**。
- 変更前に `git pull` で最新化する。

## 環境の注意（develop マシン固有）

- このマシンの Bash は zsh の `cd` ラッパーで出力が汚染されることがある。シェル実行は **`bash -c '...'` でラップ**し、git/gh は結果を別コマンドで**必ず検証**する（例: push 後に `gh api` で remote sha を照合）。

## テスト / 検証

- 方針は実装着手時に追記する。
