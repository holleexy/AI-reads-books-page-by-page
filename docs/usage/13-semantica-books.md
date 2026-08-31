# Semantica で1冊のグラフを作る

このリポジトリの知識 JSON と最終要約から、1冊分の型付き項目と結びを出す。
Hermes の作業記録（`semantica-knowledge-work.json`、ポート 8766）には書かない。

Semantica 0.6.5 は Hermes の venv にある。
このリポジトリの `.venv` へ `pip install semantica` しない。

`read_books.py` は変えない。
要約ができたあと、グラフ化は別ステップとして `plan` / `batch` / `run` を回す。
完了後フックは無い。

## 何をするか

要約からクラス一覧（OWL と SHACL）を出す。
知識点の先頭 N 件から、LLM の NER と関係抽出で項目と辺を出す。
パターン NER は使わない。
LLM が失敗したら英語のパターン抽出へは落ちず、例外で止まる。

既定の1冊は『労務入門』（`労務入門.ocr`）である。
単冊 `run` の既定件数は 80 である。
`batch` のチャンク既定も 80 である。
全件抽出は `--limit 0` または `--all-points` の明示が要る。黙って全コーパスへ LLM はかけない。
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
`--dry-run` は LLM を呼ばない。`plan` も LLM を呼ばない。

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
1冊の途中から再開するときは `--offset` を付ける。済みスライスは再抽出せず、蓄積した項目と結びからグラフを組み直す。

```bash
./scripts/run_book_semantica.sh run --book-key 採用入門.ocr --offset 80 --limit 80
./scripts/run_book_semantica.sh run --book-key 採用入門.ocr --all-points
./scripts/run_book_semantica.sh run --dry-run --book-key 採用入門.ocr --limit 80
```

`--all-points` は `--limit 0` と同じで、offset 以降の残り全部である。

## 量産（plan / batch）

知識 JSON と最終要約がある冊を列挙し、実体のある `graph.json`（1件以上の entity）がある冊は飛ばす。
0 バイトや `{"entities":[]}` の `graph.json` は失敗した書き出しとみなし、`--force` 無しでもやり直す。
`batch_state.json` が無くても、実体のある `graph.json` がある冊（試し読みの『労務入門』など）は skip である。
未完了（`complete` が false）の冊は次のチャンクから再開する。
既存の実体グラフを取り直すときは `--force` が要る。

未完了の `batch` は、CLI の `--offset` より `batch_state.json` の `next_offset` を優先する。
途中を飛ばして再開したいときは `--force` を付けるか、単冊 `run --offset` を使う。
`extract_cache.json` が無いときは、`next_offset` があっても済みスライスを空のまま飛ばさない。先頭（または CLI `--offset`）から取り直す。

`plan` はリポジトリの `.venv` で足りる。LLM を呼ばない。

```bash
.venv/bin/python -m book_semantica plan --repo-root /opt/AI-reads-books-page-by-page
./scripts/run_book_semantica.sh plan
./scripts/run_book_semantica.sh batch --dry-run
```

`batch` のライブ実行は Semantica の venv が要る。チャンク既定は 80 件である。
全件は `--all-points` または `--limit 0` を明示したときだけである。

```bash
./scripts/run_book_semantica.sh batch --limit 80
./scripts/run_book_semantica.sh batch --book-key 採用入門.ocr --offset 80 --limit 80
./scripts/run_book_semantica.sh batch --force --book-key 労務入門.ocr --limit 80
```

1冊を処理するたびに `book_analysis/semantica/manifest.jsonl` へ1行足す。
冊キー、件数（success 行の `item_count` は今回のチャンク長、`total_items` は冊全体）、offset、成否、時刻、出力ディレクトリを書く。
Hermes の作業記録パスは書かない。
出力ディレクトリ名が `.ocr` で終わっても、それは冊キーのディレクトリでありファイルではない。

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
| `batch_state.json` | 再開ポインタ。`next_offset`、`total_items`、`complete` |
| `extract_cache.json` | 蓄積した entities / relations。次チャンクはここへ足す |

横断のマニフェストは `book_analysis/semantica/manifest.jsonl` である。

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

リポジトリの `.venv`（Python 3.10）では、パスと読込、品質ゲート、バッチの列挙と再開キャッシュを見る。
Semantica を import するテストは、こちらでは skip する。
`tests.test_book_semantica_batch` は semantica を import しない。

```bash
.venv/bin/python -m unittest \
  tests.test_book_semantica_batch \
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
`batch` の `--output-dir` にこのパスを渡しても同じ例外である。
