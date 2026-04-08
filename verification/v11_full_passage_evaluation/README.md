# V11: 本番発話の内容評価

Phase C パフォーマンススピーチの評価（LLM Call #8）を検証する。

## 概要

Azure Pronunciation Assessment をストリーミングモードで使用し、発話中にリアルタイムで音声を送信・処理する。発話終了後 ~1.2s で結果を返す。

```
マイク入力 → PushAudioInputStream（リアルタイム送信）
          → Azure Pronunciation Assessment（ストリーミング）
          → difflib で Omission/Insertion 検出 + 文ごと similarity 判定
          → 合否判定 + 差分情報
```

## 環境変数

```bash
export AZURE_SPEECH_KEY="..."
export AZURE_SPEECH_REGION="japaneast"
```

## 使い方

```bash
# 1. 音声録音（4パターン）
uv run python -m verification.v11_full_passage_evaluation.record

# 2. 検証実行
uv run python -m verification.v11_full_passage_evaluation.run

# 3. 結果の詳細表示
uv run python -m verification.v11_full_passage_evaluation.evaluate
```

## テストケース

| パターン | 説明 | 期待判定 |
|---------|------|---------|
| pass_fluent | 模範通りに全文発話 | PASS |
| pass_paraphrase | 文4/7/8を英語で言い換え | PASS |
| fail_omission | 文6を沈黙でスキップ | FAIL |
| fail_semantic | 文8の意味を変更 | FAIL |

## 検証結果

**PASSED（条件付き）** — 詳細は `docs/verification/v11-full-passage-evaluation/result-2026-04-08.md`

| 指標 | 結果 | 目標 |
|------|------|------|
| 合否判定精度 | 100% (4/4) | >= 85% |
| 体感レイテンシ | ~1.2s | <= 5s |
| 判定安定性 | 3回実行全て同一結果 | — |
