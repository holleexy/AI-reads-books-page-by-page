# Kindle 自動めくりスクリーンショット（Windows）

DeDRM は使わない。
Kindle for PC のウィンドウを前面にして、見えているページを PNG に保存し、次のページへ送る。
右めくり（右キー／画面右端クリック）と左めくり（左キー／画面左端クリック）の両方に対応する。
ファイルを復号しない。
弁護士ではないので合法性は保証しない。
撮った画像の配布はしない。

このスクリプトは **Windows だけで** 動く。
Linux 上のエージェントからは Kindle アプリを撮れない。

## 準備

1. Kindle for PC で対象の本を開き、全文表示にする（サイドバーは畳む）
2. 1 ページずつ進む表示にする（見開きだと 1 枚に 2 ページ入る）
3. 次のページが右タップか左タップかを手で 1 回確認する

## 実行

Windows でこのリポジトリを最新にしてから、**リポジトリ直下の `KindleCapture.bat` をダブルクリック**する。
黒い窓に `R = Right page-turn` と `L = Left page-turn` が出る。
本を開いた状態で `R` か `L` を押す。
5 秒後に撮影が始まる。

方向が決まっているときは次でもよい。

- `scripts/KindleCapture-Right.bat` … 右めくり一発
- `scripts/KindleCapture-Left.bat` … 左めくり一発

コマンドを打つ必要はない。
画面が変わらないときは、矢印、ページ送り、クリック位置、ホイールを順に試す。
描画が落ち着いてから次を撮る。
ツールバーの表示／非表示だけの差は同一ページとして扱う。
それでも同じページ内容が続くときだけ、本の末尾とみなして止まる。
コンソールで `Ctrl+C` でも止められる。

キャプチャは Kindle ウィンドウだけを、ディスプレイの物理解像度で撮る（200% 表示でも欠けない）。
デスクトップ全体が欲しいときは `-FullScreen` を付ける。

詳細な引数が必要なときだけ `kindle_capture.ps1` を直接呼ぶ。

| 引数 | 意味 |
| --- | --- |
| `-OutDir` | PNG の出力先。既定は `Downloads\kindle_pages` |
| `-Title` | ウィンドウタイトルの部分一致。既定 `Kindle` |
| `-ProcessName` | プロセス名の部分一致。既定 `Kindle` |
| `-Direction` | `Right` で右めくり、`Left` で左めくり。既定 `Right` |
| `-TurnMethod` | `Key` / `Click` / `Both`。既定 `Both`（先にキー、だめならクリックとホイール） |
| `-Keys` | 省略時は Direction に従い `{RIGHT}` または `{LEFT}` |
| `-StartDelaySec` | 開始前の待ち秒 |
| `-IntervalMs` | めくり後の待ち。既定 2000。描画が遅いときは増やす |
| `-RenderWaitMs` | 同じ画面になるまで待つ間隔。既定 400 |
| `-MaxPages` | 安全上限。既定 2500 |
| `-StopOnDuplicate` | めくり手段を一通り試しても本文が変わらない回数がこの値になったら終了。既定 4。0 で無効 |
| `-Crop` | 左,上,右,下 の余白ピクセル。ツールバーを落とす |
| `-CopyFromScreen` | 互換用。既定で画面コピーする |
| `-FullScreen` | Kindle ウィンドウではなく、そのディスプレイ全体を撮る |
| `-SelfTest` | DPI と同一ページ判定の自己診断。Kindle は不要 |

出力は `0001.png`, `0002.png`, … である。

## 動かないとき

黒い窓が赤い ParserError で即終了する場合、古いスクリプトが残っている。
`git pull` してから、もう一度リポジトリ直下の `KindleCapture.bat` を使う。

「パラメーター -STA に引数が必要です」と出る場合も同じである。
`#Requires -STA` は Windows PowerShell 5.1 では無効なので、現行版では削除してある。

Windows PowerShell 5.1 は BOM なし UTF-8 の日本語を壊して読む。
そのため `.ps1` は ASCII 本文と UTF-8 BOM に固定してある。
既定の起動は WinForms ではなく `cmd` の `choice` である。

## このあと

画像フォルダを Linux へ渡し、[スクリーンショットから PDF](11-screenshot-to-pdf.md) の 2 以降（PDF 化 → OCR → `read_books.py`）へ進む。
