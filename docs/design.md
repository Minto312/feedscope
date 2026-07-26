# feedscope 詳細設計

Google Discover 代替のパーソナライズ記事フィード。本書は設計判断の記録であり、実装の指針。

## 背景 — Google Discover の 2 つの不満とその原因

| 不満 | Discover 側の原因 |
|---|---|
| ① 後で読む記事が消える | フィードが永続リストではなく、アクセス時に都度ランキングし直す**短命キャッシュ**。既読/保存の状態を持たない。鮮度比重が高く、少し前の記事が押し出される。 |
| ② 分野が表示枠を奪い合う | **全体で表示数が固定**の単一ストリームに全分野を混ぜている。 |

> 補足: Google Discover 自体を RSS/API で取り出す公式・非公式手段は事実上存在しない（個人ログイン依存で動的生成され、安定した公開エンドポイントが無い）。よって本プロジェクトは **Discover の複製ではなく、自分専用フィードの再構築**を狙う。

## 解法の芯

**Discover の体験（興味に合う記事が集まる）だけ借り、器は従来型 RSS の「永続化 + 分野分離」モデルに戻す。**

- ① は「記事を DB に追記して消さない」「更新タイミングを自分が握る」「明示保存で永続ライブラリへ」。
- ② は「分野 = 独立チャンネル（独立の未読・閾値・嗜好プロファイル・件数上限）」。

## アーキテクチャ（3 層 + ビューア）

### ① 収集 (collector)

- `feedparser` で各ソースを取得 → 正規化 → 重複除去 → `articles` に追記。
- cron / systemd user timer で 15–30 分毎に実行（**更新タイミングを自分が握る** = ① の要）。
- 収集元タイプ: `rss` / `gnews`(Google News RSS 検索) / `hnrss` / `reddit` / `rss_bridge`。
- 実際に使う収集元の台帳（検証済み・生存フィードのみ）と取得時の注意は [sources.md](sources.md) に集約。
  - **全取得でブラウザ相当 User-Agent 必須**（Reddit はデフォルト UA で 403）。
  - **Reddit は 429 頻発**（このマシンの IP がレート制限）→ ソース間ディレイ + 指数バックオフ。
  - リダイレクトは追う。gnews は `query` から URL を組み立てる。

### ② 選別 (classifier)

- `codex exec` をサブプロセス起動し、記事本文 + 分野定義 + 嗜好プロファイルを渡して分類させる。
- 返り値は `{category, score(0-10), reason, summary}` を要素とする JSON。
  - **Codex CLI は構造化出力の機構的保証が無い**ため、こちら側で JSON パース + スキーマ検証し、失敗時はリトライ（最大 N 回、ダメなら未分類キューへ）。
  - **プロンプトインジェクション対策**: 記事本文は外部の攻撃者が書ける入力。本文を明示デリミタ（例: `<article>…</article>`）で囲い、出力を JSON のみに制約し、本文中の指示は無視するようシステム側で明記。
- 1 記事が**複数分野に属せる**（`scores` は article×category）。
- フィードバック学習: like/dislike を `feedback` に蓄積し、一定数たまったら分野ごとの `profile`（自然言語の嗜好サマリ）を codex 自身に書き直させる（newscope 方式）。
- セレンディピティ: 各分野に低スコア/ランダム記事を `discovery_ratio` ぶん混ぜる（rssfilter 方式）。

### ③ ビューア (web)

- Flask + HTMX。PWA 化してスマホのホーム画面から Discover 代替として開ける。
- **画面1: フィード** — 上部に分野タブ（独立未読カウント）。各タブは縦スクロールのカード。
  - カード: サムネ / 見出し / 出典 / LLM 要約 / 興味度。
  - アクション: `♥保存`（→ライブラリ永続）/ `✕興味なし`（→feedback 負）/ `既読`（消さずグレーで残す）。
  - 更新は Pull-to-refresh か「新着を取り込む」ボタン（**開くたびに入れ替わらない** = ① の要）。
- **画面2: ライブラリ** — Inbox → Later → Archive のトリアージ（Readwise Reader モデル）。保存記事は絶対に消えない。

### ④ 互換出力 (feed)

- `python-feedgen` で分野ごとに `/feed/{category}.xml`（RSS/Atom）を生成。
- 既存 RSS リーダー（Miniflux / FreshRSS / NetNewsWire 等）からも読める。**あくまで互換用のオマケ**で、主役は Web ビューア。

## データモデル (SQLite)

```sql
articles (
  id INTEGER PRIMARY KEY,
  guid TEXT UNIQUE,          -- 重複除去キー
  url TEXT,
  title TEXT,
  source TEXT,
  published_at TEXT,
  fetched_at TEXT,
  content TEXT,
  summary TEXT               -- classifier が生成
);

scores (
  article_id INTEGER,
  category TEXT,
  score REAL,                -- 0-10
  reason TEXT,
  PRIMARY KEY (article_id, category)
);

states (
  article_id INTEGER PRIMARY KEY,
  state TEXT                 -- unread / saved / read（案C の肝: 消さない管理）
);

categories (
  name TEXT PRIMARY KEY,
  profile_text TEXT,         -- 自然言語の嗜好プロファイル
  threshold REAL,            -- フィード表示の下限スコア
  max_items INTEGER
);

feedback (
  article_id INTEGER,
  category TEXT,
  signal TEXT,               -- like / dislike
  ts TEXT
);
```

## 参考にした先行実装

- **umputun/newscope** — Go+SQLite。記事を 0-10 採点、閾値付き RSS 出力、自然言語プロファイルをフィードバックで更新。要件にほぼ一致。
- **sxntixgo/betternews** — Flask+HTMX+SQLite+ローカル Ollama。UI 付き・プロンプトインジェクション対策あり。UI 層の直接の手本。
- **finaldie/auto-news** — マルチソース収集 + LLM 要約/フィルタ。収集の幅の参考。
- **Readwise Reader** — Feed→Library(Inbox/Later/Archive) トリアージ。① の UX モデル。

## ロードマップ

1. ~~収集元リストと分野定義を確定~~ ✅（4分野・生存フィードを検証。[sources.md](sources.md) / `config.example.yaml`）
2. ~~collector: feedparser 収集→SQLite 追記（UA/バックオフ・重複除去）~~ ✅（3,334件で実機確認）
3. ~~classifier: `codex exec --output-schema` ラッパ + JSON 検証 + 採点~~ ✅（複数分野分類を確認）
4. ~~web: 分野タブ + 縦カードの最小ビューア（保存/既読/興味なし・独立未読カウント）~~ ✅
5. feed: python-feedgen で分野別 RSS 出力（互換エクスポート）
6. ~~collect / classify の定期実行（systemd user timer）~~ ✅（[deploy/](deploy/README.md)。collect 20分毎、classify 30分毎に各分野5件ずつ＝20件を新着優先で採点）
7. ~~スマホからの共有（PWA Web Share Target + iOS ショートカット代替）~~ ✅（`/add`。Android Chrome は実機で動作確認済み）
8. フィードバック学習（feedback→profile 自動更新）/ サムネイル取得 / discovery 枠

## 共有受け口 `/add` のセキュリティ設計

`/add` は無認証で攻撃者が選んだ URL を受け取るため、タイトル取得は次の前提で書かれている:

- **allowlist 方式**: `ipaddress.is_global` を満たすユニキャストのみ fetch。loopback・RFC1918・
  link-local（クラウドメタデータ）・**CGNAT 100.64/10（= tailnet 帯）** を拒否。
  multicast は `is_global` が True を返すため別途除外する。
- **リダイレクトは手動追従**し、毎ホップ再検証する。urllib の自動追従に任せると
  302 を 1 段挟むだけで上記チェックを完全に回避され、内部サービスの `<title>` を持ち出せる
  （実際に検証で `127.0.0.1:5057` の `<title>` を奪取できることを確認 → 修正済み）。
- **取得はリクエストスレッド外**（`ThreadPoolExecutor(max_workers=2)`, 上限 8 件待ち）。
  同期取得のままだと遅い URL を並べるだけでワーカーを枯渇させられる。
