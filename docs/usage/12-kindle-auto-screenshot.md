# Kindle 自動めくりスクリーンショット（Windows）

DeDRM は使わない。Kindle for PC のウィンドウを前面にして、見えているページを PNG に保存し、次のページへ送る。
右めくり（右キー／画面右端クリック）と左めくり（左キー／画面左端クリック）の両方に対応する。
ファイルを復号しない。弁護士ではないので合法性は保証しない。撮った画像の配布はしない。

このスクリプトは **Windows だけで** 動く。Linux 上のエージェントからは Kindle アプリを撮れない。

## 準備

1. Kindle for PC で対象の本を開き、全文表示にする（サイドバーは畳む）
2. 1 ページずつ進む表示にする（見開きだと 1 枚に 2 ページ入る）
3. 次のページが右タップか左タップかを手で 1 回確認する

## 実行

Windows にこのリポジトリ（または `scripts` フォルダ）を置いて、**`KindleCapture.bat` をダブルクリック**する。
右めくり／左めくりのボタンが出る。Kindle で本を開いてから押す。5 秒後に撮影が始まる。

方向が決まっているときは次でもよい。

- `scripts/KindleCapture-Right.bat` … 右めくり一発
- `scripts/KindleCapture-Left.bat` … 左めくり一発

コマンドを打つ必要はない。同じ画面が 3 回続いたら本の末尾とみなして止まる。コンソールで `Ctrl+C` でも止められる。

詳細な引数が必要なときだけ `kindle_capture.ps1` を直接呼ぶ。

| 引数 | 意味 |
| --- | --- |
| `-OutDir` | PNG の出力先。既定は `Downloads\kindle_pages` |
| `-Title` | ウィンドウタイトルの部分一致。既定 `Kindle` |
| `-ProcessName` | プロセス名の部分一致。既定 `Kindle` |
| `-Direction` | `Right` で右めくり、`Left` で左めくり。既定 `Right` |
| `-TurnMethod` | `Key` / `Click` / `Both`。既定 `Both`（キーとめくり側クリック） |
| `-Keys` | 省略時は Direction に従い `{RIGHT}` または `{LEFT}` |
| `-StartDelaySec` | 開始前の待ち秒 |
| `-IntervalMs` | めくり後の待ち。描画が遅いときは増やす |
| `-MaxPages` | 安全上限。既定 2500 |
| `-StopOnDuplicate` | 同一画像が続いたら終了。既定 3 |
| `-Crop` | 左,上,右,下 の余白ピクセル。ツールバーを落とす |
| `-CopyFromScreen` | PrintWindow が真っ黒なときの画面コピー |

出力は `0001.png`, `0002.png`, … である。

## このあと

画像フォルダを Linux へ渡し、[スクリーンショットから PDF](11-screenshot-to-pdf.md) の 2 以降（PDF 化 → OCR → `read_books.py`）へ進む。
