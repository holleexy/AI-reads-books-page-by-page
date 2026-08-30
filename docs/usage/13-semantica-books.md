# Semantica で1冊のグラフを作る

このリポジトリの知識 JSON と最終要約から、1冊分の型付き項目と結びを出す。
Hermes の作業記録（`semantica-knowledge-work.json`、ポート 8766）には書かない。

Semantica 0.6.5 は Hermes の venv にある。
このリポジトリの `.venv` へ `pip install semantica` しない。

## 何をするか

要約からクラス一覧（OWL と SHACL）を出す。
知識点の先頭 N 件から、LLM の NER と関係抽出で項目と辺を出す。
パターン NER は使わない。
LLM が失敗したら英語のパターン抽出へは落ちず、例外で止まる。

既定の1冊は『労務入門』（`労務入門.ocr`）である。
既定の件数は 80 である。
既存の約 10 万件を取り直さない。

OWL の `rdfs:label` は日本語の `label` を使う。
IRI の末尾だけが ASCII の `name` である。
SHACL の `xsd:xsd:string` は書き出し時に `xsd:string` へ直す。
`duplicates.json` は同一 id と `also_known_as` / `translated_as` をグループにする。
`conflicts.json` の null id と confidence だけの行は捨てる。
書き出しの最後にこの 4 点を検査する。違反なら例外で止まる。

## 起動

引数無しの既定サブコマンドは `run` である。
`run` は xAI へのライブ LLM 呼び出しである。
`--dry-run` は無い。

```bash
./scripts/run_book_semantica.sh --book-key 労務入門.ocr --limit 80
```

これは次と同じである。

```bash
./scripts/run_book_semantica.sh run --book-key 労務入門.ocr --limit 80
```

起動スクリプトは Semantica の Python（既定は `/var/lib/happy/.local/share/semantica/venv/bin/python`）を使う。
このリポジトリの `.venv` の site-packages は Semantica の `PYTHONPATH` に足さない。
認証は `read_books.py` と同じ順である。

1. すでに入っている `XAI_API_KEY`
2. Hermes の xAI OAuth（このリポの `.venv` で `xai_oauth` を呼び、取れたトークンを子プロセスの `XAI_API_KEY` にする）
3. `bws run` があるときは、その注入

件数を減らして試すときは `--limit 3` にする。

## 成果物

出力先は `book_analysis/semantica/{book_key}/` である。
`run` が成功するまで、このディレクトリにグラフは無い。

| ファイル | 中身 |
| --- | --- |
| `graph.json` | 項目と結び |
| `ontology.json` | 要約から推定したクラスとプロパティ |
| `ontology.owl` | OWL。クラス IRI は空にしない |
| `shapes.ttl` | SHACL |
| `graph.html` | 本用の画面。ポート 8766 ではない |
| `duplicates.json` | 重複検出 |
| `conflicts.json` | 矛盾検出 |
| `provenance.ttl` | 出典。`book_key` は必須。`page` は入力にあれば残る |

## 問い合わせと画面

`query` と `serve` は、先に `run` が `book_analysis/semantica/{book_key}/graph.json` を書いたときだけ動く。
そのファイルが無い状態で問い合わせできる、という意味ではない。

保存済みのグラフを LLM なしで直すときは `repair` である。
OWL の日本語ラベル、SHACL の datatype、重複グループ、矛盾のノイズ除去だけを書き直す。

```bash
./scripts/run_book_semantica.sh repair --book-key 労務入門.ocr
./scripts/run_book_semantica.sh query --book-key 労務入門.ocr --name 労務
./scripts/run_book_semantica.sh query --book-key 労務入門.ocr --source 労務 --target 人材マネジメント
./scripts/run_book_semantica.sh serve --book-key 労務入門.ocr
```

HTML の既定ポートは 8767 である。8766 は拒否する。
ブラウザで `http://127.0.0.1:8767/graph.html` を開く。
`graph.html` をファイルとして開いても辿れる。

## テスト

リポジトリの `.venv`（Python 3.10）では、パスと読込だけを見る。
Semantica を import するテストは、こちらでは skip する。

```bash
.venv/bin/python -m unittest \
  tests.test_book_semantica_paths \
  tests.test_book_semantica_load \
  tests.test_book_semantica_quality \
  tests.test_book_semantica_quality_gate \
  tests.test_book_semantica_xai
```

Semantica の venv（Python 3.11）では、xAI 登録とモックパイプラインを見る。
`PYTHONPATH` はリポジトリ根だけにする。`.venv` の site-packages は混ぜない。

```bash
PYTHONPATH=/opt/AI-reads-books-page-by-page \
  /var/lib/happy/.local/share/semantica/venv/bin/python -m unittest \
  tests.test_book_semantica_xai \
  tests.test_book_semantica_pipeline \
  tests.test_book_semantica_quality \
  tests.test_book_semantica_quality_gate
```

## 書いてはいけない場所

`/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json` へ書くと例外で止まる。
本のグラフはそのファイルではない。
