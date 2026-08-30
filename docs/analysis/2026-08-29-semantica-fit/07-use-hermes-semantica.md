# Hermes 側の Semantica を使うか

調査日は 2026-08-30 である。

**結論**：パッケージそのものは Hermes の venv を使う。
ハーネスの書き込み口と本番グラフは使わない。

## 何が入っているか

`/opt/hermes-cli` に Semantica の Git ソースは無い。
入っているのは次である。

| もの | 場所 | 役割 |
| --- | --- | --- |
| 公式パッケージ 0.6.5 | `/var/lib/happy/.local/share/semantica/venv` | 6.0G。`semantica` CLI と Python |
| 薄いアダプタ | `/opt/hermes-cli/.hermes/scripts/semantica_*.py` | `brain_write`、MCP、Oxigraph 移行 |
| 本番グラフ | `/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json` | エージェント記憶。ノード 165、辺 217 |
| パッチ | `/opt/hermes-cli/patches/semantica/` | 公式 API の欠落だけを埋める |

本番グラフの型は Fact、Decision、LessonCandidate、Person、Commitment である。
本の概念（労務、人材マネジメント）は入っていない。

Hermes の方針は「公式 API を先に呼び、足りない点だけ patch」である。
二個目の venv を本読みリポへ作ることは、その方針にも反する。

## 使うもの、使わないもの

使う。

- `/var/lib/happy/.local/share/semantica/venv/bin/python`
- 同じ venv の `NamedEntityRecognizer`、`RelationExtractor`、`LLMOntologyGenerator`、`GraphBuilder`

使わない。

- `brain_write` と 8 クラス封筒（Decision / Commitment / Person）
- `SEMANTICA_GRAPH_PATH` が指す knowledge-work.json
- named graph の personal / org / shared
- 本読みリポへの `pip install semantica`

本のグラフは別ファイルに書く。
例は `book_analysis/semantica/` である。
エージェント記憶に 8 万件の知識点を混ぜると、既存の Decision 契約が壊れる。

## 残る作業

venv の doctor は OpenAI、Anthropic、Groq のキーが無いと警告する。
日本語のオントロジーは LLM 経路が要る。
本読みリポの xAI を、その venv から呼ぶ薄いアダプタが必要である。
公式 Semantica の既定プロバイダはその 3 社である。
