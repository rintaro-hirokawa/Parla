# V7 実験設計の全体像

## 何を検証するのか

「同じ学習項目を10回練習しても、毎回違う文で練習できるか？」

ただし「違う」には2つの軸がある:

1. **内容の多様性** — 話題・語彙・状況が違う
2. **文法構造の多様性** — 文の組み立て方が違う

内容だけ変えても文法が同じだと、学習者は「主語を入れ替えただけ」のパターンに気づいてしまう。

---

## 文法構造の多次元モデル

英文の構造を**7つの独立した次元**で記述する。

```
"The environmental impact should have been taken into account."
  │                         │          │        │
  sentence_type: declarative │          │        │
  polarity: affirmative      │          │        │
  voice: ─────────────────── passive    │        │
  tense_aspect: ─────────────────────── past_perfect
  modality: ──────────────── obligation │        │
  clause_type: ──────────────────────── simple   │
  info_structure: ───────────────────────────── canonical
```

1つの英文は、この7次元の**組み合わせ**で表現される。

### 各次元の値

```mermaid
mindmap
  root((英文の構造))
    文タイプ
      平叙文
      疑問文
      命令文
    極性
      肯定
      否定
    態
      能動
      受動
    時制・相
      現在形
      過去形
      現在完了
      過去完了
      未来(will)
      未来(going to)
      現在進行
      過去進行
    法性
      なし
      義務(should/must)
      可能(can/might)
      仮定(would/could)
    複文構造
      単文
      重文(and/but)
      副詞節(if/when/because)
      関係詞節
      名詞節(that/whether)
      分詞構文
    情報構造
      標準語順
      副詞前置
      分裂文(It is...that)
      there構文
      主題化
```

### なぜ多次元か？

フラットなタグ（「受動態」「疑問文」「条件文」…）だと、**組み合わせを見落とす**。

```
❌ フラットタグ: "passive" → 1種類に見える

✅ 多次元:
   passive + present_simple + declarative  → "It is taken into account."
   passive + past_perfect + interrogative  → "Had it been taken into account?"
   passive + hypothetical + adverbial      → "If it were taken into account, ..."
   → 同じ「受動態」でも全く異なる文になる
```

---

## 5フェーズの実験フロー

```mermaid
flowchart TD
    subgraph "Phase A: ベースライン"
        A1[学習項目 × ソース5種]
        A2[制約なしで生成]
        A3["自然な分散度を測定"]
        A1 --> A2 --> A3
    end

    subgraph "Phase B: ストレステスト"
        B1[学習項目 × ソース1種固定]
        B2[制約なし × 5回]
        B3["ソース固定時の収束度を測定"]
        B1 --> B2 --> B3
    end

    subgraph "Phase C: 履歴方式"
        C1[学習項目 × ソース1種固定]
        C2["Phase Bの結果を履歴として渡す\n+「文法構造も変えよ」指示"]
        C3[追加5回生成]
        C4["履歴による改善度を測定"]
        C1 --> C2 --> C3 --> C4
    end

    subgraph "Phase D: 次元制約方式"
        D1[学習項目 × ソース1種固定]
        D2["特定の次元値を明示指定\n例: voice=passive, clause=relative"]
        D3[指定通りの文を生成]
        D4["品質を損なわず分散できるか"]
        D1 --> D2 --> D3 --> D4
    end

    subgraph "Phase E: CEFR比較"
        E1["take into account × S6"]
        E2["B1 × 3回, B2 × 3回"]
        E3["難易度が反映されるか"]
        E1 --> E2 --> E3
    end

    A3 -->|"比較: ソースの効果"| B3
    B3 -->|"比較: 履歴の効果"| C4
    B3 -->|"比較: 明示制約の効果"| D4
```

---

## 各Phaseが答える問い

```mermaid
flowchart LR
    Q1{"ソースを変えるだけで\n文法も変わる？"}
    Q2{"ソース固定だと\n文法が偏る？"}
    Q3{"履歴を渡せば\n偏りは解消する？"}
    Q4{"次元を指定すれば\n確実に分散する？"}
    Q5{"どっちが本番向き？"}

    Q1 -->|Phase A vs B| Q2
    Q2 -->|Phase B vs C| Q3
    Q2 -->|Phase B vs D| Q4
    Q3 --> Q5
    Q4 --> Q5

    style Q5 fill:#f9f,stroke:#333
```

| Phase比較 | 問い | 期待される発見 |
|-----------|------|--------------|
| A vs B | ソース多様性 → 文法多様性？ | ソースが違えば文法も自然に変わるか、それとも同じ構文に偏るか |
| B vs C | 履歴+汎用指示 → 改善？ | 「前回と違う構文で」という指示だけでどこまで効くか |
| B vs D | 明示的な次元制約 → 改善？ | 「受動態で書け」等の指定は品質（自然さ）を犠牲にするか |
| C vs D | 本番設計の選択 | 汎用指示で十分か、明示制約が必要か |

---

## 1回の生成で何が起きるか

```mermaid
sequenceDiagram
    participant R as run.py
    participant P as prompt.py
    participant G as generate.py
    participant L as LLM (LiteLLM)
    participant V as Pydantic

    R->>P: 学習項目 + ソース + 設定<br/>(+ 履歴 / 次元制約)
    P->>P: プロンプト組み立て<br/>(3パターンから選択)
    P-->>G: messages
    G->>L: litellm.completion()
    L-->>G: JSON応答
    G->>V: VariationResult.model_validate_json()
    V-->>G: 検証済みオブジェクト
    G-->>R: VariationResult

    Note over R: 結果に含まれる情報
    Note over R: ・ja: 日本語お題
    Note over R: ・en: 模範英文
    Note over R: ・grammar: 7次元プロファイル
```

---

## 評価のしくみ

```mermaid
flowchart TD
    subgraph "自動評価 (evaluate.py)"
        M1["学習項目の出現チェック\n正規表現 + 活用形対応"]
        M2["文法構造の分散度\n7次元 × エントロピー"]
        M3["語彙多様性 (TTR)\nユニーク語数 / 総語数"]
        M4["構文パターン類似度\n英文間のペアワイズ比較"]
        M5["Phase間差分レポート\nA vs B, B vs C, B vs D"]
    end

    subgraph "目視評価"
        H1["文脈の自然さ\nソースとの関連性"]
        H2["学習項目の正確な使用\n文法的・意味的に正しいか"]
        H3["日本語プロンプトの自然さ\n翻訳調でないか"]
        H4["CEFR適合\n難易度の印象"]
    end

    subgraph "合格基準"
        P1["重複 < 20%"]
        P2["正確な使用 ≥ 90%"]
        P3["自然さ ≥ 80%"]
        P4["5回生成で各次元2値以上"]
    end

    M1 --> P2
    M2 --> P4
    M4 --> P1
    H1 --> P3
    H2 --> P2
```

### 文法分散度の測定例

ある学習項目を5回生成した結果:

```
生成1: declarative / affirmative / active  / present_simple  / none       / simple   / canonical
生成2: declarative / affirmative / active  / present_simple  / obligation / simple   / canonical
生成3: declarative / affirmative / passive / present_perfect / none       / relative / canonical
生成4: interrogative/ affirmative/ active  / past_simple     / none       / adverbial/ canonical
生成5: declarative / negative   / active  / future_will     / possibility/ simple   / fronted_adverbial
```

次元別の分散:

| 次元 | 使用された値 | ユニーク数 | 偏り |
|------|------------|-----------|------|
| sentence_type | declarative×4, interrogative×1 | 2 | やや偏り |
| polarity | affirmative×4, negative×1 | 2 | やや偏り |
| voice | active×4, passive×1 | 2 | やや偏り |
| tense_aspect | present_simple×2, 他3種 | 4 | **良好** |
| modality | none×3, obligation×1, possibility×1 | 3 | まあまあ |
| clause_type | simple×3, relative×1, adverbial×1 | 3 | まあまあ |
| info_structure | canonical×4, fronted×1 | 2 | **偏り大** |

→ `info_structure` が最も偏りやすい次元と判明 → 本番設計でこの次元を制約対象にする

---

## 本番設計への示唆（実験後の意思決定）

```mermaid
flowchart TD
    R[実験結果]
    R --> Q1{Phase Cの履歴方式で\n全次元2値以上達成？}
    Q1 -->|Yes| D1["本番: 履歴方式を採用\n（シンプル）"]
    Q1 -->|No| Q2{Phase Dで品質を\n維持できた？}
    Q2 -->|Yes| D2["本番: 偏りやすい次元のみ\n明示制約を追加"]
    Q2 -->|No| D3["本番: プロンプト改善 or\nテンプレートバリエーション\n（フォールバック戦略）"]

    style D1 fill:#9f9
    style D2 fill:#ff9
    style D3 fill:#f99
```
