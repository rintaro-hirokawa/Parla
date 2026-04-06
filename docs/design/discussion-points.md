# 詳細設計に向けたディスカッション論点

最終更新日: 2026-04-06

要件定義・アーキテクチャ概要・技術検証結果を踏まえ、詳細設計に入る前に合意が必要な論点を整理する。各論点に対し推奨案を提示しているので、レビューの上で判断いただきたい。

---

## 1. MVP スコープと実装順序

### 1-1. 最初に動かすフロー

**推奨: ソース登録 → パッセージ生成 → Phase A → Phase B**

これがアプリのコア体験であり、最も不確実性が高い部分（LLM 統合、音声録音、フィードバックループ）を含む。ここを先に通すことで、後続の Block 1 / Block 3 / Phase C が自然に積み上がる。

Block 1 単体から始める案もあるが、Block 1 に使う学習項目は Phase B で生成されるため、シードデータへの依存が大きく、実体験として検証しにくい。

### 1-2. Phase C の実装タイミング

**推奨: Phase A→B の安定後に着手。Phase C 内ではリスニングモードを先行実装**

理由:
- Phase C は要件上「スキップ推奨」の条件がある（学習項目 0 件かつ WPM 目標内）。コア学習体験は Phase A→B で成立する
- オーバーラッピング（TTS 同時再生 + 録音 + 遅延検出）は技術検証 V9 が未完了
- リスニングモード（TTS 再生 + テキスト表示）は技術的に単純で、TTS 統合の検証にもなる
- 通し発話モードはリスニングの後に追加すれば自然

### 1-3. Block 1 / Block 3 の組み込みタイミング

**推奨: Block 2（Phase A→B）を一通り動かしてから追加**

理由:
- Block 1/3 の UI は Block 2 より単純（単文の日→英、正誤判定、ヒント表示）
- SRS のドメインロジック（間隔計算、信頼度乗数、スケジューリング）は UI なしでユニットテスト可能。ヘキサゴナルの恩恵をそのまま活かせる
- Block 2 で学習項目がストックされて初めて Block 1/3 が意味を持つ

### 1-4. マルチセッション体験のタイミング

**推奨: 単一セッション完走を先に完成させ、翌日メニュー確認フローは後から追加**

理由:
- 翌日メニュー確認は「セッション終了 → 翌日メニュー提示 → ユーザー確認 → バックグラウンド生成」というサイクルで、数日分のデータ蓄積が前提
- メニュー構成自体はルールベース（LLM 不要）で技術リスクが低い
- 単一セッションの通しが安定した後、シードデータで「N 日分の学習履歴」を作ってサイクル全体を検証するのが効率的

### まとめ: 実装マイルストーン案

```
M1: ソース登録 → パッセージ生成（LLM統合）→ 結果をUIで表示
M2: Phase A（録音 + タイマー + 波形）→ Phase B（フィードバック表示 + 学習項目ストック + リトライ）
M3: Block 1（SRSレビュー）+ Block 3（当日定着）→ 1セッション通し完走
M4: Phase C リスニングモード + 通し発話モード
M5: セッション終了サマリー + 翌日メニュー確認 + マルチデイサイクル
M6: Phase C オーバーラッピング（V9 検証完了後）
```

---

## 2. PySide6 UI アーキテクチャ

### 2-1. QML vs Widgets

**推奨: Widgets**

理由:
- **Python で完結する**。QML は独自 DSL + JavaScript が必要で、Python との境界でデバッグが困難になる
- **コーディングエージェントとの相性**。Widgets は Python コードなのでエージェントが読み書きしやすい。QML は情報量が少なく生成品質が落ちる
- **要件上のリッチ UI は限定的**。必要なのは波形表示・タイマー・テキストハイライト・自動遷移であり、いずれも QPainter + QTimer + カスタム Widget で実現可能。QML のアニメーション機能が活きるユースケースが少ない
- **プロトタイプの実用主義**（アーキテクチャ概要 2.3）。技術レイヤーを減らすほど反復速度が上がる

QML が優位になるのはモバイル UI やリッチアニメーションが必要な場合だが、将来のモバイル移行時は SwiftUI に書き直す方針（アーキテクチャ概要記載）であり、QML の移植性メリットは享受しない。

### 2-2. ViewModel パターンの具体化

**推奨: 画面単位の ViewModel + Qt Signal による伝搬**

具体的な設計:

```
ドメインイベント → EventBus → ViewModel（購読）→ Qt Signal emit → Screen Widget（slot で UI 更新）
ユーザー操作   → Screen Widget → ViewModel メソッド呼び出し → ドメインサービス呼び出し
```

- **粒度は画面単位**。PhaseAViewModel, PhaseBViewModel, ReviewViewModel 等。画面とドメインの状態マッピングが 1:1 で明快
- **ViewModel はドメインサービスを直接呼ぶ**。UseCase 層は挟まない。プロトタイプ期に UseCase を入れると「ドメインサービスの薄いラッパー」が量産されるだけで、保守コストに見合わない。ドメインサービスの API が UseCase 相当の粒度を持っていれば十分
- **ViewModel は QObject を継承**し、Qt Signal/Property を持つ。これにより Qt のスレッドセーフなシグナル機構をそのまま使え、asyncio スレッドからの結果通知も安全に UI スレッドへ渡せる

---

## 3. 非同期アーキテクチャ

### 3-1. Qt イベントループと asyncio の統合方式

**推奨: 専用スレッドで asyncio イベントループを回す（QThread + asyncio）**

理由:
- **分離が明確**。UI スレッド（Qt イベントループ）と非同期 I/O スレッド（asyncio ループ）が混ざらない。どちらの問題かすぐ切り分けられる
- **Orchestrator との親和性**。アーキテクチャ概要の DAG ベース並列制御は async/await で自然に書ける。QThread + concurrent.futures では複雑な依存グラフの記述が煩雑
- **qasync を回避**。qasync はメンテナンスが不安定で、PySide6 の新バージョンで動かなくなるリスクがある
- **スレッド間通信は Qt Signal**。asyncio スレッドの結果を ViewModel の Qt Signal 経由で UI スレッドに渡す。Qt Signal はスレッド間で安全に動作する

構造:

```
[UI スレッド: Qt イベントループ]
  ├── Screen Widgets（描画、ユーザー入力）
  ├── ViewModels（Qt Signal/Slot）
  └── QTimer（カウントダウン、自動遷移）

[asyncio スレッド: asyncio イベントループ]  ← QThread で起動
  ├── Orchestrator（LLMコールの並列/直列制御）
  ├── LLM Adapter（litellm 経由）
  └── TTS Adapter（ElevenLabs）

通信: ViewModel → asyncio スレッドにタスク投入（thread-safe queue or call_soon_threadsafe）
      asyncio スレッド → ViewModel の Qt Signal を emit（スレッド安全）
```

### 3-2. バックグラウンドタスクの管理

**推奨: Orchestrator 層が全バックグラウンドタスクを管理**

- Orchestrator は asyncio スレッド上で動き、asyncio.Task としてバックグラウンド処理を管理
- キャンセルは asyncio.Task.cancel() で統一
- エラーは Orchestrator が捕捉し、ドメインイベント（例: `GenerationFailed`）として通知
- ViewModel は Orchestrator の結果を購読するだけで、タスク管理の詳細を知らない

---

## 4. 音声技術スタック

### 4-1. 録音ライブラリ

**推奨: sounddevice**

理由:
- **コールバック API で numpy 配列が直接得られる**。リアルタイム波形表示に必要なデータが追加変換なしで手に入る
- **低レイテンシ**（PortAudio バックエンド）
- **デバイス列挙 API** がある（`sounddevice.query_devices()`）。マイク選択画面（SCREEN-E1）の要件を満たせる
- **アクティブにメンテナンスされている**
- QAudioSource も候補だが、numpy 配列への変換が追加で必要になり、波形表示パイプラインが冗長になる
- 将来のモバイル移行時はこの層は全面書き直し（アーキテクチャ概要記載済み）なので、Qt への統一性は利点にならない

### 4-2. 波形表示

**推奨: QPainter カスタム Widget**

理由:
- **依存ゼロ**。PySide6 だけで完結
- **描画内容を完全に制御可能**。波形 + レベルメーター + 現在位置マーカー等を一つの Widget 内で統合描画できる
- 30-60fps 更新は QPainter で十分に軽量
- pyqtgraph はグラフ描画ライブラリとしては優秀だが、このアプリの波形表示はシンプル（振幅の時系列表示 + レベルメーター）で、ライブラリを導入するほどの複雑さがない

### 4-3. 音声フォーマット変換

**推奨: プロトタイプ初期は WAV のまま保持。MP3 変換は後から追加**

理由:
- MP3 変換は保存容量の最適化であり、機能的なブロッカーではない
- pydub + ffmpeg は外部バイナリ依存が配布を複雑にする
- 1 セッション分の WAV（数十分）は数百 MB 程度で、ローカルアプリとしては許容範囲
- LLM への送信は WAV のまま行う（Gemini は WAV を受け付ける）
- アーキテクチャ概要の音声ファイル管理構造（`audio/recordings/`, `audio/converted/`）は維持し、変換処理だけ後から実装

---

## 5. 未完了技術検証との関係

**推奨: 実装フェーズに合わせて検証を並行実施。Port インターフェースは要件定義ベースで先行定義**

具体的な方針:

| 検証 | 方針 | 理由 |
|---|---|---|
| V2（学習項目抽出） | **M2 着手前に検証実施** | Phase B のコア。出力構造（reproduction, dynamic_answer, items）が Port インターフェースを直接規定する。要件定義で出力は定義済みだが、LLM が実際にこの構造を安定的に返せるか確認が必要 |
| V5（リトライ判定） | **モック Adapter で先行、M2 中に検証** | インターフェースが単純（音声入力 → 正誤 + コメント）。要件定義の出力構造が変わるリスクは低い |
| V9（オーバーラッピング） | **M6 前に検証** | Phase C オーバーラッピングは実装順序として最後。検証する時間的余裕がある |
| V11（通しパッセージ評価） | **M4 前に検証** | Phase C 通し発話の実装時に必要。リスニングモード先行中に検証可能 |

ヘキサゴナルアーキテクチャにより、Port インターフェースさえ定義すればモック Adapter で UI・ドメイン開発を進められる。要件定義で入出力は詳細に規定されているため、検証結果で Port インターフェースが根本的に変わるリスクは低い。変わるとすれば Adapter 内部のプロンプト設計や LLM コールの分割方法であり、それは Port の裏側に閉じる。

---

## 6. LLM クライアント設計

### 6-1. litellm の位置づけ

**推奨: litellm を Adapter 内部の実装詳細として使う**

```
Domain → LLMPort(Protocol) → GeminiLLMAdapter → litellm → Gemini API
```

理由:
- V1 検証で litellm 経由の動作は確認済み。構造化出力もサポート
- プロバイダ切り替え（Gemini → Claude 等）が litellm のパラメータ変更で済む
- ただし litellm 自体を Port とはしない。ドメインは litellm の型を知らない。Adapter が litellm のレスポンスをドメイン型に変換する
- リトライ戦略は Adapter 内で litellm のリトライ機構 or 独自実装のいずれかを選択可能

### 6-2. LLMPort の粒度

**推奨: 単一の LLMPort に機能別メソッドを持たせる**

理由:
- アーキテクチャ概要で `LLMPort` は単一 Port として記載されている
- 各メソッドはドメイン固有の入出力型を持つので型安全性は保たれる
- Port 数が増えすぎない（6-7 個の機能別 Port は管理コストが高い）
- 内部的に Adapter が LLM コールの分割・統合を自由に判断できる

```python
class LLMPort(Protocol):
    async def generate_passages(self, source: Source, cefr: CEFR, variety: Variety) -> PassageSet: ...
    async def generate_feedback(self, audio: AudioData, prompt: str, ...) -> FeedbackResult: ...
    async def judge_retry(self, audio: AudioData, model_answer: str, ...) -> RetryJudgment: ...
    async def generate_variation(self, item: LearningItem, context_source: Source, ...) -> PracticeItem: ...
    async def evaluate_full_passage(self, audio: AudioData, ...) -> PassageEvaluation: ...
    async def detect_overlapping_delay(self, user_audio: AudioData, model_audio: AudioData, ...) -> OverlappingResult: ...
```

補足: Port が肥大化した場合（10 メソッド超など）、その時点で機能グループ単位に分割すればよい。プロトタイプ初期は統一 Port のほうが見通しが良い。

---

## 7. DI・起動構成

**推奨: 手動 DI（main.py でのコンポジションルート）**

理由:
- 依存グラフが小さい。Adapter は 3-4 個（LLM, TTS, Repository, AudioStore）、ドメインサービスも限定的
- 全ての配線が 1 ファイルで見渡せる。新メンバー（エージェント含む）がアプリの構成を即座に把握可能
- DI コンテナはコンテナ自体の学習コスト + デバッグの不透明さが発生する。このプロジェクトの規模では割に合わない
- テスト時はモック Adapter を直接渡すだけ

```python
# main.py（イメージ）
def create_app() -> QApplication:
    # Adapters
    llm = GeminiLLMAdapter(config.gemini)
    tts = ElevenLabsTTSAdapter(config.elevenlabs)
    repo = SQLiteRepository(config.db_path)

    # Domain Services
    event_bus = EventBus()
    srs_scheduler = SRSScheduler(repo)
    item_stocker = ItemStocker(repo, llm)

    # Orchestrator (asyncio thread)
    orchestrator = Orchestrator(llm, tts)
    async_thread = AsyncThread(orchestrator)

    # ViewModels
    phase_a_vm = PhaseAViewModel(orchestrator, event_bus)
    ...
```

---

## 8. 開発中のデータ・モック戦略

### 8-1. LLM モックの範囲

**推奨: 3 層のモック戦略**

| 開発フェーズ | LLM | データ |
|---|---|---|
| UI 開発 | モック Adapter（固定 JSON を返す） | シードデータ |
| ドメインロジック開発 | 不要（ヘキサゴナルの恩恵） | ユニットテスト用 fixture |
| 統合テスト | 実 API（手動実行） | シードデータ + 実生成結果 |

モック Adapter は `MockLLMAdapter` として実装し、V1 検証結果のパッセージデータ等を返す。手動 DI なので `main.py` の 1 行を差し替えるだけでモック⇔本番を切り替え可能。

### 8-2. シードデータの初期設計

**推奨: V1 検証結果を核に、最小限のデータセットを構築**

| データ | 内容 | 元ネタ |
|---|---|---|
| ソース 1 件 | V1 検証で使った YouTube 要約テキスト | V1 検証結果 |
| パッセージ 6 件 | V1 結果の 6 パッセージ・47 文 | V1 検証結果 |
| 学習項目 15 件 | SRS ステージ 0-6 に分散配置 | 手動作成（V7 検証の 4 項目 + 追加） |
| セッション履歴 3 件 | WPM 推移を含む最小限の履歴 | 手動作成 |

シードデータは JSON or SQL ファイルとして `seeds/` に git 管理。`reset_db` コマンドで DB を再構築可能にする（アーキテクチャ概要 8.3 に記載の方針に従う）。

---

## 次のステップ

上記論点のレビュー完了後、以下の順で詳細設計に進む:

1. ドメインモデル詳細設計（エンティティ、値オブジェクト、ドメインサービスの具体的なインターフェース）
2. Port インターフェース定義
3. イベントカタログ（全イベントとハンドラの詳細定義）
4. UI 画面設計（コンポーネント構成 + 画面遷移）
5. SQLite スキーマ設計
6. 実装タスク分解（マイルストーン M1-M6 ベース）
