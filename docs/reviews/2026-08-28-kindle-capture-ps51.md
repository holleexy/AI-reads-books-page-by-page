# Kindle キャプチャ起動スクリプトのレビューと修正（2026-08-28）

Windows PowerShell 5.1 で `KindleCapture.bat` が ParserError で落ちた。
原因は GUI の日本語ではなく、UTF-8（BOM なし）を CP932 として読んだ結果、閉じ引用符が次バイトとして消費されたことである。

## 症状

ファイルは `scripts/kindle_capture_gui.ps1` の 26 行目だった。

```
$btnRight.Add_Click({ $script:chosen = "Right"; $form.Close() })
```

エラーは `Right"; $form.Close() })` を式として使えない、という ParserError である。
26 行目の `"Right"` 自体は正しい。
壊れていたのは直前の `"Right  /  右めくり"` である。

## 原因

Windows PowerShell 5.1 の `-File` は、BOM が無いとシステム ANSI でパースする。
日本語 Windows ではそれが CP932 である。
`右めくり` の UTF-8 末尾 `E3 82 8A` を CP932 が読むと、閉じ `"`（`0x22`）がトレイルバイトになる。
パーサはまだ文字列の中にいて、次の `"Right"` の開き引用符で初めて閉じる。
だからエラー行は 26 行目にずれる。

`chcp 65001` では `-File` のパースは直らない。

## レビューで出た他の欠陥

起動経路を直したあとに、キャプチャ本体が 5.1 で落ちる項目が残っていた。

1. `Set-StrictMode` のあとで `$IsWindows` を読む。これは PowerShell 6 以降の自動変数であり、5.1 には無い。
2. `Add-Type -TypeDefinition` は同一セッションで二度目に失敗する。
3. `ReferencedAssemblies System.Drawing`（拡張子なし）は 5.1 の CodeDom で解決できないことがある。
4. `$matches` は `-match` 用の自動変数を上書きする。
5. StrictMode 下の `Format-Table` が内部プロパティ参照で落ちることがある。
6. `.bat` が LF のみだと、環境によって最終行が欠けることがある。

## 採った修正

WinForms GUI を既定の起動経路から外した。
`scripts/KindleCapture.bat` は `cmd` の `choice` で R / L を選び、`kindle_capture.ps1` を `-STA` で呼ぶ。

キャプチャ本体は次を直した。

- Windows 判定を `$env:OS -ne "Windows_NT"` にする
- `KindleWin` 型の存在チェックを入れる
- `System.Drawing.Bitmap` のアセンブリパスを `Add-Type` に渡す
- `$matches` を `$found` に改名する
- 一覧表示を `Out-String` にする
- hwnd がゼロなら throw する
- `#Requires -Version 5.1` を付ける。`#Requires -STA` は 5.1 では無効なので使わない
- `.ps1` は UTF-8 BOM + CRLF + ASCII 本文にする
- `.bat` は ASCII + CRLF にする。`powershell.exe` に `-STA` を付ける

`kindle_capture_gui.ps1` は ASCII のみの任意 GUI として残した。
既定のダブルクリック経路は使わない。

## 再レビュー

実装後の再確認では、上記 7 件はいずれも FIXED だった。
既定経路に GUI は残っていない。

## `#Requires -STA` による再発（2026-08-28 追記）

Windows 実機で `R` を押した直後、`kindle_capture.ps1` 2 行目が ParserError になった。
メッセージは「パラメーター -STA に引数が必要です」である。

`#Requires` が受け付けるのは `-Version` や `-Modules` などであり、`-STA` は無い。
パーサは `-STA` を値付きパラメータと見なし、引数不足で止まる。

STA は `#Requires` ではなく、`.bat` の `powershell.exe -STA` と、未 STA なら自分を `-STA` で呼び直す処理に移した。

## 検証の範囲

Linux 上では Kindle for PC も Windows PowerShell 5.1 も動かない。
代わりに次を固定した。

- 旧 GUI 断片が CP932 で引用符数を崩すこと
- 現行 `.ps1` がその罠に入らないこと
- BOM / CRLF / ASCII / 禁止トークン / CHOICE 起動

Windows 実機では、本を開いた状態で `KindleCapture.bat` をダブルクリックし、R または L のあと 5 秒で PNG が `Downloads\kindle_pages` に増えることまで確認する。
