# 正解判定基準

本ドキュメントでは、各場面における発話の正解/不正解の判定基準を定義する。

---

## 判定の原則

「対象の学習項目が適切に使われている」かどうかが最重要基準である。それ以外の要素は柔軟に許容する。

---

## 場面別の判定基準

| 場面 | 何を見るか | 許容 | 不合格 |
|------|-----------|------|--------|
| フェーズB即時リトライ | 模範解答の内容がおおむね再現されているか | 語彙の言い換え、語順の軽微な違い、冠詞の間違い | 学習項目の表現の欠落、意味が通じない |
| フェーズC本番発話 | Azure Pronunciation Assessment のword-level ErrorType でエラー率を判定 | 軽微な発音ミス（エラー率 < 15%） | エラー率 >= 15%（Mispronunciation + Omission の割合） |
| ブロック1復習 | 対象の学習項目が使われているか | 学習項目以外の部分の言い換え | 対象学習項目の不使用、意味が大きく異なる |
| ブロック3定着 | ブロック1と同じ | 同上 | 同上 |

---

## 具体例

学習項目: "A is more X than B"

### 正解

- "This course is more difficult than Nurburgring."（言い換え許容）

### 正解だが反応速度で評価低下

- "This... facility is... more challenging than... Nurburgring."（たどたどしい）

### 不正解

- "This facility is very challenging, unlike Nurburgring."（構文未使用）
- "This facility is challenging."（比較欠落）

---

## 判定指示テンプレート

### フェーズB即時リトライ / ブロック1・3（LLM判定）

```
判定基準:
1. 対象の学習項目「{pattern}」が適切に使われているか → 最重要
2. 模範解答の意味内容がおおむねカバーされているか
3. 英語として意味が通じるか

出力:
- correct: bool
- reason: 20語以内
- item_used: bool
```

### フェーズC本番発話（Azure ErrorType ベース判定）

LLMコールは使用しない。Azure Pronunciation Assessment のword-level ErrorType でエラー率を判定する。
Overlapping・Live Delivery とも同じアルゴリズムを使用。

```
判定ロジック:
1. Azure reference_text = 動的模範解答全文
2. 全単語から Insertion を除外した ref-aligned 単語を母数とする
3. Mispronunciation + Omission の単語数 / ref-aligned 単語数 = error_rate
4. error_rate < ERROR_RATE_THRESHOLD (0.15) なら合格
```

表示:
- pronunciation_score（Overlapping・Live Delivery 共通）
- 単語ごとの色分け（None=緑、Mispronunciation=赤太字、Omission=グレー取り消し線）
- Live Delivery のみ追加で合格/不合格を表示

---

## 無音/発話なしのハンドリング

- 音声が一定の閾値（1秒以上の発話区間なし）を下回った場合、「発話が検出されませんでした」と表示する
- そのセンテンスは「未回答」扱いとする
- フィードバックでは模範解答のみを表示し、即時リトライに進む
- WPM計測からは除外する
