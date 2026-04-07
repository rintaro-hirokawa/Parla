# V5: リトライ判定の速度と精度

フェーズBの即時リトライで、発話音声を「正解/不正解 + 一言コメント」として3秒以内に判定できるかを検証する。

検証レポート: [`docs/verification/v5-retry-judgment/result-2026-04-07.md`](../../docs/verification/v5-retry-judgment/result-2026-04-07.md)

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `config.py` | モデル名、reasoning_effort、実行回数などの設定 |
| `models.py` | LLM出力の Pydantic スキーマ (`correct`, `reason`) |
| `test_cases.py` | 5シナリオ × 4音声タイプ = 20テストケースの定義 |
| `prompt.py` | システム/ユーザープロンプトテンプレート |
| `judge.py` | 音声 base64 エンコード → LiteLLM multimodal 呼び出し → レイテンシ計測 |
| `run.py` | 全テストケースを実行し、正答率・レイテンシを集計して JSON 保存 |
| `record.py` | 録音補助 CLI。ガイドに従って20ファイルを順番に録音できる |
| `audio/` | 録音済み WAV ファイル (gitignore 対象) |
| `outputs/` | 実行結果 JSON (gitignore 対象) |

## 実行方法

### 1. 環境変数

```bash
export GEMINI_API_KEY="..."
```

### 2. 録音 (初回のみ)

```bash
uv pip install sounddevice soundfile numpy
uv run python -m verification.v5_retry_judgment.record
```

各テストケースで「話す内容」が表示される。Enter で録音開始 → Enter で停止。再生・やり直しも可能。`--overwrite` で既存ファイルを上書き。

### 3. 検証実行

```bash
uv run python -m verification.v5_retry_judgment.run
```

20ケース × `num_runs` 回 (デフォルト3) の API 呼び出しを行い、以下を出力する:

- 各ケースの判定結果・レイテンシ・reason のテーブル
- 集計メトリクス (正答率、レイテンシ中央値/最大値)
- 合否判定 (PASS/FAIL)
- `outputs/result_{timestamp}.json` に詳細を保存

### 4. 設定変更

`config.py` を編集する:

```python
model: str = "gemini/gemini-3-flash-preview"
reasoning_effort: str = "minimal"
num_runs: int = 3
```
