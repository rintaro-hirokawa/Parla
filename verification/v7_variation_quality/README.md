# V7: 類題生成の品質と多様性

SRS レビュー用の類題生成（LLM #3）が、同一の学習項目に対して文法構造を含む多様なバリエーションを生成できるかを検証する。

- **定義**: `docs/verification/v7-variation-quality/definition.md`
- **結果レポート**: `docs/verification/v7-variation-quality/result-2026-04-06.md`

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | モデル名、CEFRレベル、学習項目定義、Phase D の次元制約セット |
| `models.py` | Pydantic 出力スキーマ（GrammarProfile, VariationItem, VariationResult） |
| `prompt.py` | 3パターンのプロンプトテンプレート（基本 / 履歴付き / 次元制約付き） |
| `generate.py` | LiteLLM 呼び出し + Pydantic バリデーション（リトライ付き） |
| `run.py` | Phase A〜E の実行オーケストレーション |
| `evaluate.py` | 自動評価（文法分布・エントロピー・TTR・Phase 間比較） |
| `source_texts/` | ソーステキスト 8 本（S1〜S8、各 200〜400 語の英文記事） |
| `outputs/` | 生成結果 JSON と評価レポート |

## 動かし方

### 1. モデル名の設定

`config.py` の `model` フィールドにモデル名を記入する:

```python
model: str = "gemini/gemini-3-flash-preview"
```

### 2. 全 Phase を一括実行

```bash
uv run python -m verification.v7_variation_quality.run
```

### 3. 特定の Phase のみ実行

```bash
uv run python -m verification.v7_variation_quality.run --phase A
uv run python -m verification.v7_variation_quality.run --phase B
uv run python -m verification.v7_variation_quality.run --phase C  # Phase B の結果が必要
uv run python -m verification.v7_variation_quality.run --phase D
uv run python -m verification.v7_variation_quality.run --phase E
```

Phase C は Phase B の結果を履歴として使用するため、先に Phase B を実行しておく必要がある（`outputs/phase_B_*.json` を自動で読み込む）。

### 4. 評価の実行

```bash
uv run python -m verification.v7_variation_quality.evaluate
```

`outputs/` にある各 Phase の最新結果を読み込み、以下を出力する:

- Phase ごとの文法分布・エントロピー・語彙多様性（TTR）・文長統計
- Phase 間比較（A vs B、B vs C、B vs D）
- 合格基準チェック（学習項目出現率 ≥ 90%、全次元 2 値以上）
- `outputs/evaluation_report.json` に評価結果を保存

## Phase の概要

| Phase | 条件 | 対象 | 問い |
|-------|------|------|------|
| A | 異なるソース × 3、制約なし | 全 4 項目 | ソース変更で文法も変わるか |
| B | 同一ソース × 3、制約なし | L1, L4 | ソース固定で文法が収束するか |
| C | 同一ソース × 3、履歴 + 文法分散指示 | L1, L4 | 履歴方式で分散が改善するか |
| D | 同一ソース × 3 制約、次元を明示指定 | L1, L4 | 明示制約で品質を保てるか |
| E | B1/B2 × 2 回 | L4 | CEFR レベルが反映されるか |
