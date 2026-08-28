# 1 冊（または複数冊）を読む

入口は `read_books.py` である。PDF のパスを引数に渡す。

## 手順

```bash
./run.sh read_books.py /path/to/book.pdf
```

複数冊やディレクトリも渡せる。

```bash
./run.sh read_books.py a.pdf b.pdf
./run.sh read_books.py kindle_pdfs/
```

ディレクトリは直下の `*.pdf` だけを読む。サブディレクトリは見ない。
Enter 待ちは無い。既定は全書である。

## オプション

| 引数 | 意味 |
| --- | --- |
| `--pages N` | 先頭 N ページだけ読む。省略時は全書 |
| `--interval N` | N ページごとに区間要約を書く。既定 20。`0` で最終要約だけ |

先頭 60 ページの試し読みは次である。

```bash
./run.sh read_books.py meditations.pdf --pages 60
```

## 途中で止めたとき

同じ `book_key`（既定は PDF の stem）で再実行すると、`*_progress.json` の `last_page` から再開する。
完了すると progress ファイルは消える。
