# 動かす前に揃えるもの

次が揃っていれば、プロジェクト直下で `./run.sh` が通る。

## Python 環境

`.venv` が既にある。
依存は `requirements.txt` の `pydantic`、`openai`、`pymupdf`、`termcolor`、`python-dotenv` である。

入れ直すときは次で足りる。

```bash
cd /opt/AI-reads-books-page-by-page
.venv/bin/pip install -r requirements.txt
```

## xAI または Cursor の Grok

`create_client()` は次の順で認証する。

1. `XAI_API_KEY` があれば `https://api.x.ai/v1` の chat completions
2. 無ければ Hermes の xAI OAuth（`auth.json` の SuperGrok / X Premium+）
3. それも無ければ `CURSOR_API_KEY` で Cursor Agent SDK の `grok-4.6`

主モデルは `grok-4.6`、レート制限時の控えは `grok-4.5` である。
OmniRoute は使わない。
OAuth の置き場所と無効化は [xAI OAuth](08-xai-oauth.md) を見る。

`./run.sh` は可能なら Bitwarden Secrets Manager（`bws`）でキーを注入する。
このマシンでは `CURSOR_API_KEY` も入るが、OAuth が取れれば xAI が勝つ。

```bash
export XAI_API_KEY='...'   # あれば最優先。OAuth だけなら不要
./run.sh smoke_test.py
```

キーとトークンの値をリポジトリやガイドに書かない。

## PDF の置き場所

単冊はプロジェクト直下のファイル名を `read_books.py` の `pdf_name` に書く。
サンプルとして `meditations.pdf` と `infinite_math.pdf` がある。

バッチは `kindle_pdfs/*.pdf` だけを見る。
このディレクトリは `.gitignore` 対象なので、クローンしただけでは中身が無い。

## 疎通確認

```bash
./run.sh smoke_test.py
```

`SMOKE OK` と出れば、クライアント生成、1 ページ抽出、JSON パースまで通っている。
