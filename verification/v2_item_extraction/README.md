# V2: 学習項目抽出精度の検証

LLM Call #4（フィードバック生成）の2段階パイプラインを検証する。

```
音声ファイル + 日本語プロンプト
    ↓
[Stage 1] Gemini Flash Lite: 音声 → 書き起こし（日英混在 + ポーズマーカー）
    ↓
[Stage 2] Gemini Flash: 書き起こし → 模範解答 + 許容判定 + 学習項目（priority 2-5）
```

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | モデル名・CEFR・リトライ回数等の設定 |
| `models.py` | Pydantic スキーマ（TranscriptionResult, FeedbackResult, LearningItem） |
| `test_cases.py` | 6シナリオ x 2パターンのテストケース定義 + ストック済み項目リスト |
| `prompt.py` | Stage 1/2 のプロンプトテンプレート + ストック項目フォーマッタ |
| `generate.py` | 2段階パイプライン実装（transcribe → generate_feedback → analyze） |
| `record.py` | 録音補助CLI（Enter で開始/停止、再生/やり直し） |
| `run.py` | 全シナリオ実行 + JSON 出力 |
| `evaluate.py` | 自動メトリクス集計 + 目視確認用レポート |
| `audio/` | 録音ファイル格納先（.wav、gitignore対象） |
| `outputs/` | 結果JSON格納先 |

## 実行手順

### 1. 依存パッケージ（録音用）

```bash
uv pip install sounddevice soundfile numpy
```

### 2. モデル設定

`config.py` の `stage1_model` / `stage2_model` を設定する。

```python
stage1_model: str = "gemini/gemini-3.1-flash-lite-preview"
stage2_model: str = "gemini/gemini-3-flash-preview"
```

### 3. 録音

```bash
uv run python -m verification.v2_item_extraction.record
```

- 日本語プロンプトと指示が表示される
- Enter で録音開始 → Enter で停止
- `[r]` やり直し / `[p]` 再生 / Enter で次へ
- 12ファイル（6シナリオ x 2パターン）を `audio/` に保存

### 4. LLM 実行

```bash
uv run python -m verification.v2_item_extraction.run
```

- 全12ケースに対して Stage 1 → Stage 2 を順次実行
- 結果を `outputs/result_YYYYMMDD_HHMMSS.json` に保存

### 5. 評価レポート

```bash
uv run python -m verification.v2_item_extraction.evaluate
```

特定の結果ファイルを指定する場合:

```bash
uv run python -m verification.v2_item_extraction.evaluate --file result_20260407_115949.json
```

## 検証結果

`docs/verification/v2-item-extraction/result-2026-04-07.md` を参照。
