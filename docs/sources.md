# 収集元台帳（検証済み）

2026-07-18 に develop マシンから各フィードを実際に `curl`（ブラウザ UA）して**生存・フィード形式・item 件数を確認**した結果。`config.example.yaml` に載っているのはここで `OK` だったソースのみ。

## 取得時の注意（collector 実装の前提）

- **ブラウザ相当の User-Agent を必須にする。** 特に Reddit はデフォルト UA だと 403。
  `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36`
- **Reddit は 429（Too Many Requests）が頻発。** このマシンの IP がレート制限を受けており、`r/programming`・`r/webdev`・`r/gadgets` は数十秒のクールダウンで通ったが、`r/anime`・`r/gaming`・`r/Android`・`r/apple`・`r/economics`・`r/geopolitics` 等は一貫して 429。
  → ソース間にディレイ（例 500ms〜）、429 は指数バックオフでリトライ。恒常的に無理なら認証付き（OAuth）取得か Reddit ソースを外す。
- **リダイレクトは追う**（`-L` 相当）。NHK は `www.nhk.or.jp` が 301 で内部へ飛ぶので `www3.nhk.or.jp` を直接使う。
- **Google News RSS** は `query` から URL を組み立てる:
  `https://news.google.com/rss/search?q=<URLエンコード>&hl=ja&gl=JP&ceid=JP:ja`（1 クエリ最大 ~100 件・鮮度は中程度）。
- 一部フィードは `<title>` の先頭がチャンネル名（フィード名）なので、記事タイトルは item 単位で取る。

## エンジニア

| ソース | type | lang | 状態 | items |
|---|---|---|---|---|
| はてブ テクノロジー(人気) | rss | ja | ✅ | 30 |
| Publickey | rss | ja | ✅ | 15 |
| gihyo.jp | rss | ja | ✅ | 779 |
| Zenn | rss | ja | ✅ | 20 |
| Qiita 人気 | rss | ja | ✅ | 30 |
| ASCII.jp | rss | ja | ✅ | 30 |
| Think IT | rss | ja | ✅ | 30 |
| InfoQ Japan | rss | ja | ✅ | 12 |
| @IT | rss | ja | ✅ | 30 |
| Lobsters | rss | en | ✅ | 25 |
| HN programming(>=50) | hnrss | en | ✅ | 20 |
| HN frontpage | hnrss | en | ✅ | 20 |
| r/programming | reddit | en | ✅(要スロットル) | 25 |
| r/webdev | reddit | en | ✅(429後再試行で成功) | 25 |
| GNews ソフトウェア開発/プログラミング | gnews | ja | ✅ | 100 |
| GNews Web開発/フロントエンド | gnews | ja | ✅ | 77 |
| GNews 生成AI開発 | gnews | ja | ✅ | 100 |
| CodeZine | rss | ja | ⚠️ 502(混雑) | 0 |

- CodeZine (`https://codezine.jp/rss/new/20/index.xml`) は検証時「翔泳社：混雑中」の 502。URL は正しいので後で再有効化可（config ではコメントアウト）。

## ガジェット

| ソース | type | lang | 状態 | items |
|---|---|---|---|---|
| GIZMODO Japan | rss | ja | ✅ | 20 |
| ITmedia Mobile | rss | ja | ✅ | 20 |
| ITmedia PC USER | rss | ja | ✅ | 20 |
| Impress PC Watch | rss | ja | ✅ | 20 |
| Impress ケータイ Watch | rss | ja | ✅ | 30 |
| Impress AV Watch | rss | ja | ✅ | 20 |
| ガジェット通信 | rss | ja | ✅ | 10 |
| roomie | rss | ja | ✅ | 20 |
| The Verge | rss | en | ✅ | 10 |
| Engadget (英語版) | rss | en | ✅ | 20 |
| r/gadgets | reddit | en | ✅ | 25 |
| HN gadget | hnrss | en | ✅ | 20 |
| HN smartphone | hnrss | en | ✅ | 20 |
| GNews ガジェット新製品 | gnews | ja | ✅ | 100 |
| Impress Watch 総合 | rss | ja | ✅(重複) | 20 |
| r/Android | reddit | en | ⚠️ 429 | 0 |
| r/apple | reddit | en | ⚠️ 429 | 0 |

- Impress Watch 総合 (`.../ipw/feed.rdf`) は PC/ケータイ/AV Watch と記事が重複するため config ではコメントアウト。
- Engadget **日本版は 2023 年終了**。英語版 `https://www.engadget.com/rss.xml` は存続。

## アニメ・ゲーム

| ソース | type | lang | 状態 | items |
|---|---|---|---|---|
| アニメ!アニメ! | rss | ja | ✅ | 50 |
| 4Gamer.net | rss | ja | ✅ | 100 |
| Game*Spark | rss | ja | ✅ | 50 |
| AUTOMATON | rss | ja | ✅ | 60 |
| 電ファミニコゲーマー | rss | ja | ✅ | 50 |
| IGN Japan | rss | ja | ✅ | 40 |
| Anime News Network (all) | rss | en | ✅ | 126 |
| ANN Newsroom | rss | en | ✅(allと重複) | 40 |
| Gematsu | rss | en | ✅ | 20 |
| Polygon | rss | en | ✅ | 10 |
| HN game engine | hnrss | en | ✅(周辺的) | 20 |
| GNews ファミ通 | gnews | ja | ✅ | 100 |
| GNews アニメ新作 | gnews | ja | ✅ | 100 |
| GNews ゲーム新作 | gnews | ja | ✅ | 100 |
| r/anime, r/Games, r/gaming, r/JRPG | reddit | en | ⚠️ 429 | 0 |

- **ファミ通は直接の RSS を確認できず**、Google News の `q=ファミ通` で代替。
- ANN は all と newsroom が重複するので config では all のみ有効。

## 政治・経済

| ソース | type | lang | 状態 | items |
|---|---|---|---|---|
| NHK 主要 | rss | ja | ✅ | 7 |
| NHK 政治 | rss | ja | ✅ | 87 |
| NHK 経済 | rss | ja | ✅ | 77 |
| NHK 国際 | rss | ja | ✅ | 116 |
| 東洋経済オンライン | rss | ja | ✅ | 20 |
| ダイヤモンド・オンライン | rss | ja | ✅ | 25 |
| 時事通信 ランキング | rss | ja | ✅(カテゴリ混在) | 10 |
| WSJ World News | rss | en | ✅ | 20 |
| NYT Economy | rss | en | ✅ | 20 |
| GNews 政治 | gnews | ja | ✅ | 102 |
| GNews 経済/金融政策 | gnews | ja | ✅ | 100 |
| GNews ビジネス/決算 | gnews | ja | ✅ | 100 |
| GNews 国際情勢 | gnews | ja | ✅ | 100 |
| GNews ロイター/ブルームバーグ | gnews | ja | ✅ | 100 |
| 日経（非公式ミラー wor.jp） | rss | ja | ✅(非公式・混在) | 30 |
| HN economy(>=100) | hnrss | en | ✅(周辺的) | 20 |
| r/economics, r/geopolitics | reddit | en | ⚠️ 429 | 0 |

- **日経は公式の無料 RSS が無い。** `assets.wor.jp/rss/rdf/nikkei/news.rdf` は非公式ミラーで全カテゴリ混在（サンプルにスポーツ見出しが混入）。使うなら自己責任、config ではコメントアウト。
- ロイター/ブルームバーグも公式日本語 RSS が不安定なため Google News 経由で代替。
