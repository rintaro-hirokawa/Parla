# 技術検証

本ディレクトリでは、AI-Driven-English の要件実現可能性を担保するための技術検証を管理する。

---

## 構造

```
docs/verification/
├── README.md                         ← このファイル
├── v1-passage-generation/
│   ├── definition.md                 ← 検証定義（問い・方法・基準）
│   └── result-YYYY-MM-DD.md          ← 検証結果（実施後に追加）
├── v2-item-extraction/
│   └── ...
...
```

- **definition.md**: 検証の定義（問い、背景、方法、合格基準、フォールバック）
- **result-YYYY-MM-DD.md**: 検証の実施結果。同じ検証を複数回実施した場合は日付で区別

---

## カテゴリ

| カテゴリ | 問い |
|---------|------|
| AI能力・品質 | Gemini にこの入出力ができるか? 出力品質は実用的か? |
| レイテンシ | UX を壊さない速度で返るか? |
| 外部サービス | TTS 等の品質・コスト・速度は許容範囲か? |

---

## 優先度

| 優先度 | 定義 | タイミング |
|-------|------|-----------|
| P1 | プロダクトの前提が成り立つか | 実装開始前に検証 |
| P2 | コア学習フローの品質が十分か | コアフロー実装と並行して検証 |
| P3 | 拡張機能が実現可能か | なくてもプロトタイプは動く |

---

## ステータス

| status | 意味 |
|--------|------|
| not_started | 未着手 |
| in_progress | 検証中 |
| passed | 合格基準を満たした |
| failed | 合格基準を満たさなかった（フォールバック適用） |
| deferred | 意図的に後回し |

---

## 検証項目一覧

### P1: プロダクト前提の検証

| ID | 項目 | カテゴリ | 関連LLMコール |
|----|------|---------|-------------|
| [V1](v1-passage-generation/definition.md) | パッセージ生成品質 | AI能力・品質 | #1 |
| [V2](v2-item-extraction/definition.md) | 学習項目抽出精度 | AI能力・品質 | #4 |
| [V3](v3-duplicate-detection/definition.md) | 意味的重複検出 | AI能力・品質 | #4 |

### P2: コアフロー品質の検証

| ID | 項目 | カテゴリ | 関連LLMコール |
|----|------|---------|-------------|
| [V5](v5-retry-judgment/definition.md) | リトライ判定の速度と精度 | レイテンシ + AI能力 | #5 |
| [V7](v7-variation-quality/definition.md) | 類題生成の品質と多様性 | AI能力・品質 | #3 |

### P3: 拡張機能の検証

| ID | 項目 | カテゴリ | 関連LLMコール |
|----|------|---------|-------------|
| [V8](v8-session-composition/definition.md) | ~~セッション構成のLLM判断品質~~ (resolved: 決定論的アプローチ採用) | — | — |
| [V9](v9-overlapping-detection/definition.md) | オーバーラッピング遅れ検知 | AI能力 | #7 |
| [V10](v10-tts/definition.md) | ~~TTS品質・コスト~~ (resolved: ElevenLabs品質確認済み) | — | — |
| [V11](v11-full-passage-evaluation/definition.md) | 本番発話の内容評価 | AI能力 + レイテンシ | #8 |
| [V12](v12-pronunciation/definition.md) | 発音評価 | AI能力 | — |

---

## 旧IDとの対応

`docs/requirements/14-technical-verification.md` からの移行マッピング:

| 旧ID | 新ID | 備考 |
|------|------|------|
| T10 | V1 | |
| T7 | V2 | |
| — | V3 | 新規追加 |
| T3 | V5 | |

| — | V7 | 新規追加 |
| — | V8 | 新規追加 |
| T1 | V9 | |
| T6 | V10 | |
| T2+T9 | V11 | 統合 |
| T4 | V12 | |

---

## 参考情報（検証不要）

以下はプロトタイプ段階では検証不要。スケール時に再検討する。

- **Gemini API レート制限・コスト**（旧T5）: 1セッション約170回の音声コールの現実性。プロトタイプは1ユーザーのため制約に達しない
- **並列バックグラウンド処理のレート制限**（旧T8）: 7センテンス分のフィードバック生成を並列実行する際のレート制限。順次実行でも機能は動作する

---

## 技術メモ

### 音声評価

- Gemini API に音声ファイルを直接入力する（STT 経由しない）
- 日英混在音声の精度が高いことを開発者の実験で確認済み
- Gemini API で YouTube 動画の内容解析も可能

### TTS

- ElevenLabs 等で模範音声を生成する
- 英語バリエーション（American / British 等）に対応した音声を選択する

### 遅れ検知の候補技術

- forced alignment（Montreal Forced Aligner 等）
- Gemini に音声ペアを入力して比較分析

### デスクトップアプリ

- Qt/PySide6 系を想定する
- Web はマイク周りの API 複雑さから避ける方針
