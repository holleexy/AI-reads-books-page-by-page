# 動かないとき

## `XAI_API_KEY, xAI OAuth ..., or CURSOR_API_KEY is not set`

`./run.sh` は `bws` でキーを入れようとする。
このマシンでは Hermes の xAI OAuth があればそれが使われ、無ければ `CURSOR_API_KEY` に落ちる。
OAuth を無視したいときは `XAI_DISABLE_OAUTH=1` を付ける。
コンソールの API キーを使うときは `XAI_API_KEY` を export する。

値はファイルに残さない。

## `xAI OAuth failed`

access token の期限切れ後、refresh が 400/401 なら Hermes 側で xAI に再ログインする。
403 はプランが API を許していないことが多い。`XAI_API_KEY` か Cursor へ切り替える。

## OmniRoute / `20128` を探している

この fork は OmniRoute を使わない。
端点は `https://api.x.ai/v1` である。
ローカルの `20128` が空でも、xAI のキーがあれば動く。

## `No PDFs found in kindle_pdfs/`

バッチは `kindle_pdfs/*.pdf` だけを見る。
ディレクトリが無いか空だと即終了する。
単冊用に直下へ置いた PDF はバッチ対象ではない。

## 全部 `already processed`

`kindle_pdfs/` の stem が、既存の最終要約または完了 status と一致している。
再処理する冊の `*_status.json` と、必要なら `*_final_*.md` を退ける。

単冊の `test_pages=60` で作った status は `test_mode` が真なので、バッチの「済み」判定には使われない。
ただし最終要約ファイルがあると legacy 判定で飛ぶ。

## Enter 待ちのまま進まない

`read_books.py` に PDF を渡した場合は Enter 待ちは無い。
引数無しで起動すると使い方を出して終了する。

## ページが黄色い skip ばかり

ローカルヒューリスティックが短文や奥付を落としている。
本文なのに落ちるなら `_SKIP_PATTERNS` か文字数閾値を見直す。

## 依存が入っていない

```bash
.venv/bin/python -c "import openai, fitz, pydantic, termcolor, dotenv"
```

失敗したモジュールを `requirements.txt` から入れ直す。
