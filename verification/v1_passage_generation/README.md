# V1: パッセージ生成品質

ソーステキストから CEFR 準拠の学習用パッセージを生成し、品質を検証する。

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | 検証設定（モデル名、CEFR レベル、英語バリエーション、パッセージタイプ） |
| `models.py` | LLM 出力の Pydantic スキーマ（Passage, Sentence, Hint） |
| `prompt.py` | システムプロンプト / ユーザープロンプトのテンプレート |
| `generate.py` | LiteLLM 呼び出し + バリデーション（リトライ付き） |
| `run.py` | 実行エントリポイント |
| `source_texts/` | 入力ソーステキスト |
| `outputs/` | 生成結果 JSON（gitignore 推奨） |

## 動かし方

### 1. 依存インストール

```bash
uv sync
```

### 2. モデル名の設定

`config.py` の `model` フィールドにモデル名を記入する。LiteLLM の命名規則に従うこと。

```python
model: str = "gemini/gemini-2.0-flash"  # 例
```

### 3. ソーステキストの配置

`source_texts/sample_01.txt` にテキストファイルを配置する。

### 4. API キーの設定

使用するプロバイダーに応じた環境変数を設定する。

```bash
export GEMINI_API_KEY="..."     # Gemini の場合
export OPENAI_API_KEY="..."     # OpenAI の場合
```

### 5. 実行

```bash
uv run python -m verification.v1_passage_generation.run
```

結果はコンソールに表示され、`outputs/` に JSON として保存される。

## 関連ドキュメント

- 検証定義: `docs/verification/v1-passage-generation/definition.md`
- 検証レポート: `docs/verification/v1-passage-generation/result-2026-04-06.md`
