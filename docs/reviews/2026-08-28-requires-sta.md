# `#Requires -STA` は Windows PowerShell 5.1 でパースできない

`KindleCapture.bat` で方向を選んだ直後に、次の ParserError が出た。

```
kindle_capture.ps1:2
#Requires -STA
パラメーター -STA に引数が必要です。
```

`#Requires` のパラメータに `-STA` は無い。
有効なのは `-Version`、`-Modules`、`-RunAsAdministrator`、`-PSEdition` などである。
5.1 のパーサは `-STA` を「値が必要なパラメータ」と解釈して止まる。

STA アパートメントは次で確保する。

1. `.bat` が `powershell.exe -NoProfile -STA -File ...` で起動する
2. それでも STA でなければ、スクリプトが同じパスを `-STA` 付きで呼び直す

`#Requires -STA` は置かない。
