# V9: オーバーラッピング遅れ検知

オーバーラッピング練習（模範音声と同時に発話する練習）で、学習者の発音・タイミングを自動評価するパイプライン。

詳細な検証経緯と結果は [docs/verification/v9-overlapping-detection/result-2026-04-07.md](../../docs/verification/v9-overlapping-detection/result-2026-04-07.md) を参照。

## クイックスタート

```bash
# 依存インストール
uv pip install elevenlabs pydub litellm pydantic matplotlib sounddevice scipy azure-cognitiveservices-speech

# 環境変数
export ELEVENLABS_API_KEY="..."
export GEMINI_API_KEY="..."
export AZURE_SPEECH_KEY="..."
export AZURE_SPEECH_REGION="japaneast"

# オーバーラッピング練習（録音 → 解析 → チャート表示）
uv run python practice.py

# 保存済み録音を Azure で再解析
uv run python pronunciation_assessment.py outputs/practice/XXXXXX_p1.wav p1
```

## ファイル一覧

### コア（プロダクション実装で使う想定のもの）

| ファイル | 役割 |
|---------|------|
| `pronunciation_assessment.py` | **Azure Pronunciation Assessment ラッパー**。連続認識モードで30秒超の音声に対応。生JSONから単語ごとのAccuracyScore, ErrorType, Offset, Durationを抽出。difflib による Omission/Insertion 後処理を含む |
| `visualize.py` | **チャート生成**。3種類のチャート関数を提供: `plot_delay_chart()`（FA偏差折れ線+loss）、`plot_pronunciation_chart()`（発音評価バー）、`plot_combined_chart()`（タイミング偏差+発音+ErrorTypeの3パネル統合） |
| `config.py` | 定数・閾値・APIキー取得関数。ElevenLabs / Gemini / Azure の環境変数を管理 |
| `models.py` | 全 Pydantic モデル。FA結果(`FAResult`)、遅れ検出(`DelayDetectionResult`)、Azure発音評価(`PronunciationResult`)、LLMフィードバック(`LLMFeedback`)、テストケース(`TestCase`)、実験結果(`ExperimentResult`) |

### ツール

| ファイル | 役割 |
|---------|------|
| `practice.py` | **CLI 検証アプリ**。模範音声をスピーカー再生 + マイク録音 → FA/Azure解析 → チャート表示。`--passage p1` でパッセージ選択、`--feedback` でLLMフィードバック生成 |

### ElevenLabs FA ベース（参考実装として残存）

| ファイル | 役割 |
|---------|------|
| `forced_alignment.py` | ElevenLabs Forced Alignment API ラッパー。音声ファイル+テキストから単語タイムスタンプを取得 |
| `delay_detection.py` | ベースライン補正累積偏差方式の遅れ検出ロジック。median ベースラインで自然なシャドーイング遅延を吸収し、局所的な遅れを検出。`compute_accuracy()` で ground truth との精度計算も可能 |
| `tts_generate.py` | ElevenLabs TTS 音声生成。`convert_with_timestamps` で模範音声+タイムスタンプを同時取得。pydub によるフレーズ別速度の音声結合にも対応 |

### LLM フィードバック

| ファイル | 役割 |
|---------|------|
| `prompt.py` | LLM 原因推定プロンプト。遅れの原因を4カテゴリ（pronunciation_difficulty / vocabulary_recall / syntactic_complexity / discourse_boundary）に分類する指示 |
| `llm_feedback.py` | LiteLLM 経由で Gemini を呼び出し、遅れ箇所データから構造化フィードバックを生成 |

### TTS 模擬検証用

| ファイル | 役割 |
|---------|------|
| `test_cases.py` | TTS 速度操作による模擬テストケース定義。V1出力パッセージから5パターン（sync, stumble, no_linking, gradual, different_voice）を自動生成 |
| `run.py` | TTS 模擬パイプラインの実行スクリプト。`--step tts/pipeline/all` で段階実行、`--runs N` でレイテンシ計測 |
| `evaluate.py` | 合格基準判定。Recall/FPR/FAレイテンシ/全体レイテンシをパターン別に集計 |

### データ

| ディレクトリ | 内容 |
|------------|------|
| `audio/reference/` | 模範 TTS 音声（mp3）+ タイムスタンプ（json） |
| `audio/simulated/` | TTS 模擬ユーザー音声 |
| `outputs/charts/` | TTS 模擬検証のチャート画像 |
| `outputs/practice/` | 実音声検証の録音（wav）、結果（json）、チャート（png） |
