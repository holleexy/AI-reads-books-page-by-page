# 取り込み判断（2026-08-22）

## 判断

**マージしない。**

理由:

1. 機能改善・バグ修正・依存関係の更新が一切ない。
2. 差分は原作者の Patreon 宣伝文の差し替えだけ。
3. この fork はすでに `read_books.py` を独自改修しており、README の How to Use も fork 側の運用（Z.AI、バッチ処理）とずれている。宣伝文だけ追従する価値は低い。

## 実施した準備

再チェックしやすいよう、remote `upstream` を追加済み。

```
upstream  https://github.com/echohive42/AI-reads-books-page-by-page.git
```

次回は `git fetch upstream` のあと `git log HEAD..upstream/main` で足りる。

## やらなかったこと

- `git merge upstream/main`
- origin への push
- 未コミットの `read_books.py` / `requirements.txt` の整理
