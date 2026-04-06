# V3: 意味的重複検出

新規抽出された学習項目と既存ストック済み項目を LLM で意味的に照合し、重複と再出を正しく判定できるかを検証する。

検証結果レポート: [docs/verification/v3-duplicate-detection/result-2026-04-06.md](../../docs/verification/v3-duplicate-detection/result-2026-04-06.md)

---

## ファイル構成

```
verification/v3-duplicate-detection/
├── README.md              ← このファイル
├── config.py              設定（モデル名、リトライ数、パス定義）
├── models.py              Pydantic モデル定義（入出力の型）
├── prompts.py             LLM に渡すプロンプトテンプレート
├── llm_client.py          LiteLLM 経由の LLM 呼び出し
├── run_experiment.py      メイン実験スクリプト（CLI）
├── evaluate.py            結果 JSON を集計し合格基準と照合
├── test_data/
│   ├── stock_items_10.json      ストック済み学習項目（10個）
│   ├── stock_items_50.json      同（50個、10のスーパーセット）
│   ├── stock_items_100.json     同（100個、50のスーパーセット）
│   ├── duplicate_pairs.json     重複ペア: 同一と判定すべきケース（5件）
│   ├── non_duplicate_pairs.json 非重複ペア: 別物と判定すべきケース（10件）
│   ├── reappearance_cases.json  再出ケース: ストック済み項目の再検出（4件）
│   └── scenarios.json           テストシナリオ（戦略A用の発話文脈）
└── results/                     実験結果 JSON の出力先
```

### 各ファイルの役割

**config.py** — 環境変数 `GEMINI_API_KEY` の読み込み、デフォルトモデル名（`DEFAULT_MODEL`）、リトライ回数、ディレクトリパスを定義。モデルを変更したい場合はここの `DEFAULT_MODEL` を書き換える。

**models.py** — 実験で使う全てのデータ構造を Pydantic モデルとして定義。テストデータの読み込み用（`StockItem`, `DuplicatePairCase` 等）、LLM 出力のパース用（`FeedbackOutput`, `FocusedOutput`）、実験結果の記録用（`ExperimentResult`）の3グループ。

**prompts.py** — 2つの戦略のプロンプトテンプレートを管理。
- **戦略A** (`STRATEGY_A_*`): 本番の LLM #4 と同等のフルパイプライン。発話テキストからフィードバック生成全体をシミュレーションし、その中で重複判定を行う。
- **戦略B** (`STRATEGY_B_*`): 重複検出のみに特化。「この新規パターンは既存リスト内のどれかと同一か？」を直接問う。精度の上限を測定する目的。

**llm_client.py** — LiteLLM の `completion()` を呼び出し、Pydantic の構造化出力（`response_format`）でパースする。バリデーション失敗時は `MAX_RETRIES` 回リトライ。

**run_experiment.py** — メインの実験スクリプト。テストデータを読み込み、ストックサイズ × テストケース × 実行回数のループで LLM を呼び出し、判定結果を JSON に保存する。

**evaluate.py** — 結果 JSON を読み込み、ケースタイプ別 × ストックサイズ別の正答率を集計。合格基準との照合、失敗ケースの詳細表示、レイテンシ統計を出力する。

---

## 前提

- `uv sync` 済み（litellm, pydantic が dev 依存に含まれている）
- 環境変数 `GEMINI_API_KEY` が設定されていること

---

## 動かし方

### 実験の実行

```bash
# プロジェクトルートから実行する

# 戦略B（重複検出特化）— 基本はこちらを使う
uv run python verification/v3-duplicate-detection/run_experiment.py --strategy focused

# 戦略A（フル LLM #4 シミュレーション）
uv run python verification/v3-duplicate-detection/run_experiment.py --strategy full
```

#### オプション

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--strategy` | `full` | `full`（戦略A）or `focused`（戦略B） |
| `--stock-sizes` | `10,50,100` | カンマ区切りでストックサイズを指定 |
| `--model` | config.py の `DEFAULT_MODEL` | LiteLLM のモデル名 |
| `--runs` | `3` | 各ケースの実行回数（LLM の非決定性を測定） |
| `--output-dir` | `results/` | 結果 JSON の出力先 |

#### 実行例

```bash
# stock=100 のみ、1回だけ試す（最小限の確認）
uv run python verification/v3-duplicate-detection/run_experiment.py \
  --strategy focused --stock-sizes 100 --runs 1

# 別モデルで比較
uv run python verification/v3-duplicate-detection/run_experiment.py \
  --strategy focused --model gemini/gemini-2.5-flash --runs 3
```

### 結果の評価

```bash
uv run python verification/v3-duplicate-detection/evaluate.py \
  verification/v3-duplicate-detection/results/<result-file>.json
```

合格基準を満たせば exit code 0、未達なら exit code 1 を返す。

---

## 合格基準

| 指標 | 基準 |
|------|------|
| 重複ペア正答率 | 80%+ |
| 非重複ペア正答率 | 90%+（過剰統合は学習に悪影響が大きいため厳しめ） |
| 再出検知率 | 85%+ |
| スケール維持 | ストック100個でも上記を維持 |

---

## テストデータの編集

テストケースを追加・修正する場合は `test_data/` 配下の JSON を編集する。

- **ストック項目を増やす**: `stock_items_*.json` に追加。入れ子構造（10 ⊂ 50 ⊂ 100）を維持すること。
- **テストケースを追加する**: `duplicate_pairs.json` / `non_duplicate_pairs.json` / `reappearance_cases.json` に追加し、対応するシナリオを `scenarios.json` に追加する（戦略Bではシナリオ不要だが、戦略Aで使う）。
- **特定ストックサイズでのみ有効なケース**: `min_stock_size` フィールドを指定すると、それ未満のストックサイズではスキップされる。
