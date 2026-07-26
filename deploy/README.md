# deploy — 定期実行 (systemd user units)

feedscope を放っておいても回るようにする systemd **user** ユニット。

| ユニット | 種別 | 内容 | コスト |
|---|---|---|---|
| `feedscope-collect` | timer 20分毎 (`*:0/20`) | 57ソースを取得して SQLite に追記 | ネットワークのみ・無料 |
| `feedscope-classify` | timer 30分毎 (`*:10/30`) | codex で **各分野5件ずつ=20件** を採点（新着優先） | **時間 + ChatGPT クォータ** |
| `feedscope-serve` | 常駐 | web ビューア (`0.0.0.0:5057`)。異常終了時は自動再起動 | 常駐・軽量 |

classify は 1 件あたり約 9 秒。1 回 20 件 ≒ 3 分、1 日あたり最大 ~960 件。
クォータが気になる場合は `.service` の `--per-category` を減らすか、`.timer` の間隔を延ばす。

## インストール

```sh
./deploy/install.sh              # 3 ユニットを配置して有効化
./deploy/install.sh --no-serve   # 常駐ビューアなし（タイマーだけ）
```

チェックアウト先と `uv` の絶対パスはスクリプトが書き換えるので、別マシン・別ディレクトリでもそのまま動く。
手で置く場合は:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/feedscope-*.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now feedscope-collect.timer feedscope-classify.timer
systemctl --user enable --now feedscope-serve.service    # 常駐ビューア
```

> **ユニットは dotfiles で管理しない。** マシン固有の絶対パスを含むため、
> `~/dotfiles/.gitignore` で `.config/systemd/user/feedscope-*` を除外し、
> **この repo の `deploy/` を正として再作成する**運用にしている。

パスが `/home/karinto/workspace/feedscope` 前提なので、別の場所に置く場合は
`.service` の `WorkingDirectory` と `ExecStart`（`uv` の絶対パス）を書き換える。

ログアウト中も動かすには linger が必要:

```sh
loginctl enable-linger "$USER"   # 既に有効なら不要
```

## 確認

```sh
systemctl --user list-timers 'feedscope-*'                # 次回実行時刻
journalctl --user -u feedscope-collect.service -n 60      # 取得ログ（ソース別の件数）
journalctl --user -u feedscope-classify.service -n 60     # 採点ログ（記事ごとのスコア）
```

## 手動実行 / 停止

```sh
systemctl --user start feedscope-collect.service    # 今すぐ 1 回取得
systemctl --user start feedscope-classify.service   # 今すぐ 1 バッチ採点
systemctl --user stop feedscope-classify.timer      # 採点だけ一時停止（クォータ節約）
systemctl --user disable --now feedscope-classify.timer   # 採点の自動化をやめる
```

## ハマり所

- **`codex` が見つからない**: `systemd --user` の PATH は `~/.local/bin` を含まないため、
  素で動かすと全件 `[Errno 2] No such file or directory: 'codex'` で失敗する。
  `feedscope-classify.service` の `Environment=PATH=...` がこれの対策（codex の実体は
  `~/.local/bin/codex`）。codex を別の場所に入れている場合はここを直す。
- **`~/.config/systemd` が dotfiles へのシンボリックリンクの場合**、ここに `cp` したユニットは
  実体として dotfiles リポジトリ側に置かれる。dotfiles で追跡するか除外するかは各自で判断する。
- classify は「1 件も成功せず失敗だけ」の場合に終了コード 1 を返す。
  `systemctl --user status feedscope-classify.service` が failed になるので異常に気付ける。

## 調整

- **採点量**: `feedscope-classify.service` の `--per-category N`（分野ごとの件数）。
- **間隔**: `.timer` の `OnCalendar=`。変更後は
  `systemctl --user daemon-reload && systemctl --user restart feedscope-<name>.timer`。
- collect の `config.yaml` 側 `schedule.interval_minutes` は参考メモなので、間隔を変えたら合わせておくと混乱がない。
- classify は `Persistent=` を付けていない（停止中の追いつきで余計な codex バッチを走らせないため）。
