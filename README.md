# feedscope

> Personalized, non-destructive article discovery feed — a self-hosted Google Discover alternative with per-topic channels and a keep-forever library.

Google Discover の「気づいたら記事が消えている」「分野の表示枠を奪い合う」を解消する、自分専用のパーソナライズ記事フィード。

## なぜ作るか

Google Discover には 2 つの構造的な不満がある:

1. **後で読もうとした記事が消える** — フィードが永続リストではなく、開くたびに再ランキングされる短命キャッシュだから。
2. **分野が表示枠を奪い合う** — 全分野が単一ストリームに固定枠で混在するため、片方を読むと他方が減る。

feedscope はこれを「**Discover の体験（興味に合う記事が集まる）は借り、器は従来型 RSS の永続・分野分離モデルに戻す**」ことで解決する。

## コンセプト / 解法

| Discover の不満 | feedscope の解法 |
|---|---|
| ① 記事が消える | 記事を SQLite に**追記して消さない**。更新は明示操作 or cron のみで勝手に入れ替わらない。既読は**グレー表示で残す**。「後で読む」は永続ライブラリへ。 |
| ② 枠の奪い合い | 分野を**独立チャンネル化**。分野ごとに独立した未読・スクロール位置・興味度閾値・嗜好プロファイルを持つ。片方を読んでも他方は減らない。 |

## アーキテクチャ

3 層パイプライン + Web ビューア:

```
① 収集 (cron / systemd timer, 15–30分毎)
   feedparser で 純正RSS / Google News RSS / hnrss / Reddit / RSS-Bridge
   → 正規化・重複除去 → articles (SQLite)

② 選別 (classifier)
   `codex exec` をサブプロセス起動し、記事本文を分類
   → 分野タグ + 興味度 0-10 + 要約 (JSON で受けて自前検証・リトライ)
   → scores (SQLite)、like/dislike で分野別プロファイルを更新

③ ビューア (web, Flask + HTMX, PWA)
   分野タブ + 縦カード UI。 ♥保存 / ✕興味なし / 既読
   ライブラリ (Inbox → Later → Archive)

④ 互換出力 (feed)
   python-feedgen で /feed/{分野}.xml（既存 RSS リーダー互換・オマケ）
```

## 技術スタック

- 言語: **Python 3.10+**（依存管理は uv）
- 収集: `feedparser`
- 分類: **`codex exec`**（OpenAI Codex CLI をサブプロセス実行。構造化出力は自前で JSON 検証）
- 保存: **SQLite**
- UI: **Flask + HTMX**（分野タブ + 縦カード、PWA）
- 互換出力: `python-feedgen`

## 分野（初期プリセット）

| 分野 | 収集元の例 |
|---|---|
| エンジニア | はてブ テクノロジー / Publickey / gihyo.jp / Zenn / Qiita / InfoQ Japan / Hacker News / Google News |
| ガジェット | GIZMODO / ITmedia Mobile・PC USER / Impress PC・ケータイ・AV Watch / The Verge / Google News |
| アニメ・ゲーム | アニメ!アニメ! / 4Gamer / Game*Spark / AUTOMATON / 電ファミ / IGN Japan / ANN / Google News |
| 政治・経済 | NHK(政治/経済/国際) / 東洋経済 / ダイヤモンド / 時事通信 / WSJ / NYT / Google News |

収録ソースはすべて develop から実際に curl 検証した「生存フィード」のみ。検証結果と実運用の注意は [docs/sources.md](docs/sources.md)。

## ディレクトリ構成

```
src/feedscope/
  collector/   # 収集 (feedparser)
  classifier/  # codex exec による分類・採点
  web/         # Flask + HTMX ビューア
  feed/        # RSS/Atom 互換エクスポート
docs/design.md          # 詳細設計
docs/sources.md         # 検証済みソース台帳 + 実運用の注意
config.example.yaml     # 分野・収集元・閾値（config.yaml にコピーして使う）
```

## セットアップ

```sh
cp config.example.yaml config.yaml        # 自分用に分野・ソースを調整
uv sync --extra web                       # 依存を導入（web ビューアも含める）
uv run feedscope collect                  # 全ソースを取得して SQLite に追記
uv run feedscope classify --limit 20      # codex で未分類記事を採点（小分け推奨）
uv run feedscope serve                    # http://127.0.0.1:5000 でビューアを起動
```

`classify` は 1 件あたり数秒・ChatGPT クォータを使うため `--limit` / `--source-category` で小分けにする。

`collect` の定期実行は systemd user timer を同梱（[deploy/](deploy/README.md)）:

```sh
cp deploy/feedscope-collect.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now feedscope-collect.timer
```

## ステータス

🚧 **開発中。** collector / classifier / web ビューア（分野タブ＋縦カード）まで動作。
残り: フィードバック学習・RSS 互換出力・PWA・systemd timer。詳細は [docs/design.md](docs/design.md)。

## License

[MIT](LICENSE)
