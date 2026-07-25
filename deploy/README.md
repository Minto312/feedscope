# deploy — 定期実行 (systemd user units)

`collect`（記事の取得）を定期実行するための systemd **user** ユニット。
`classify`（codex 採点）は時間とクォータを使うため、意図的に自動化していない。

## インストール

```sh
mkdir -p ~/.config/systemd/user
cp deploy/feedscope-collect.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now feedscope-collect.timer
```

パスが `/home/karinto/workspace/feedscope` 前提なので、別の場所に置く場合は
`.service` の `WorkingDirectory` と `ExecStart`（`uv` の絶対パス）を書き換える。

ログアウト中も動かすには linger が必要:

```sh
loginctl enable-linger "$USER"   # 既に有効なら不要
```

## 確認

```sh
systemctl --user list-timers feedscope-collect.timer   # 次回実行時刻
systemctl --user status feedscope-collect.service      # 直近の結果
journalctl --user -u feedscope-collect.service -n 50   # 取得ログ（ソース別の件数）
```

## 手動実行 / 停止

```sh
systemctl --user start feedscope-collect.service   # 今すぐ 1 回取得
systemctl --user stop feedscope-collect.timer      # 自動取得を一時停止
systemctl --user disable --now feedscope-collect.timer  # 自動取得をやめる
```

## 間隔の変更

`.timer` の `OnCalendar=` を編集して `systemctl --user daemon-reload && systemctl --user restart feedscope-collect.timer`。
（例: 1 時間ごとなら `OnCalendar=hourly`）
`config.yaml` の `schedule.interval_minutes` は参考メモなので、合わせて更新しておくと混乱がない。
