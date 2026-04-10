# UI実装タスクリスト

作成日: 2026-04-10

本ドキュメントは、Parla の PySide6 UI レイヤーを段階的に構築するためのタスクリストである。上から順番に実行すること。

---

## 前提・設計判断

### フレームワーク
- **PySide6** + **PySide6.QtAsyncio**（統合イベントループ）
- Qt のイベントループが Python の asyncio イベントループを兼ねる（`QtAsyncio.run()`）
- 別スレッド不要。async/await と Qt Signal が同一スレッド上で共存

### UIアーキテクチャ: ViewModel パターン
- 各画面に対応する **ViewModel**（`QObject` 継承）がドメインと UI の橋渡しを行う
- ViewModel は **EventBus の sync ハンドラ** として登録される
  - 理由: ViewModel の状態更新は軽量な代入だけなので sync で十分。UI更新の即時性が保証される
  - async ハンドラは外部APIコール用（サービス層が使う）
- ViewModel は `activate()` 時に **Query Service** で初期 state をロードし、その後の差分更新を EventBus イベントで受け取る
- ドメインイベント受信 → ViewModel 内部状態更新 → Qt Signal emit → View 描画
- ViewModel のライフサイクル:
  - `activate()`: 画面がアクティブになったとき、EventBus にハンドラ登録
  - `deactivate()`: 画面が非アクティブになったとき、EventBus からハンドラ解除

### サービス呼び出しパターン
- **状態変更** は ViewModel から command service を呼び出す
  - 非同期処理は `asyncio.create_task(service.method(...))` で起動する
  - 結果は EventBus 経由でイベントとして ViewModel に返る（直接 await しない）
  - 例: 録音完了 → `asyncio.create_task(feedback_service.judge_retry(...))` → `RetryJudged` イベント → ViewModel → UI
- **初期表示 / 一覧 / 履歴 / 集計 / 起動時判定** は Query Service を同期呼び出しする
  - 例: C2 表示開始 → `learning_item_query_service.list_items(filters)` → ViewModel state 初期化

### Read Model / Query Service
- 一覧・履歴・集計・起動時判定は **read model / query service** で取得する
- Query Service は **service層の読み取り専用コンポーネント** とする。副作用なし、EventBus emit なし、状態変更なし
- ローカル SQLite の読み取りが中心なので、Query Service は基本 sync でよい
- 複数 Repository をまたぐ集約や direct SQL は service層の Query Service に閉じ込め、ViewModel / View に書かない
- Query Service の戻り値は UI 向け DTO とし、集約済みの表示モデルを返す
- これは strict CQRS ではなく、既存の service 層の中で read-only な責務を明示分離するだけである

### プログレッシブ表示
- 全結果の完了を待たず、部分結果をドメインイベントとして逐次 UI に反映
- 例: フェーズB で8センテンスのフィードバックが個別に `FeedbackReady` として到着 → 1件ずつ表示

### テスト方針
- **全 UI コードを pytest-qt で TDD 開発する**
- テスト対象: ViewModel、ウィジェット、ナビゲーション、View、セッションコーディネーター
- サービス層はモック/フェイクを注入
- `qtbot` fixture を活用（Signal 待機、ウィジェット操作）
- 音声デバイス依存のテストはモックで代替

### 音声デバイス
- マイク/スピーカーは UI レイヤーの責務（Port として抽象化しない）
- `QAudioSource` で録音、`QMediaPlayer` + `QAudioOutput` で再生
- PCM 16bit mono 16kHz（Azure Speech 要件準拠）

### 画面一覧（参照）
- 画面設計の詳細: [09-ux-screens.md](../requirements/09-ux-screens.md)
- アーキテクチャ全体: [overview.md](overview.md) セクション 3.5
- セッション中はタブバー非表示（学習フロー没入）

### サービス層の API（参照）

UI が呼び出すサービス:
- `SessionService`: `compose_menu()`, `recompose_menu()`, `confirm_menu()`, `start_session()`, `advance_block()`, `interrupt_session()`, `resume_session()`, `check_menu_freshness()`, `get_active_sources()`
- `SourceService`: `register_source()`
- `FeedbackService`: `record_sentence()`, `judge_retry()`
- `ReviewService`: `request_variation()`, `judge_review()`, `judge_review_retry()`, `get_due_items()`
- `PracticeService`: `request_model_audio()`, `should_skip()`, `evaluate_overlapping()`, `detect_lag()`, `evaluate_live_delivery()`
- `SettingsService`: `get_settings()`, `update_settings()`

### UI が呼び出す Query Service（service層、参照）

- `AppStateQueryService`: `get_bootstrap_state()`
- `SourceQueryService`: `list_sources()`, `list_active_sources()`
- `LearningItemQueryService`: `list_items()`, `get_item_detail()`, `get_sentence_items()`
- `HistoryQueryService`: `get_history_overview()`, `get_daily_summary()`
- `SessionQueryService`: `get_today_dashboard()`, `get_menu_preview()`, `get_passage_summary()`, `get_session_summary()`

### UI が受信するドメインイベント（参照）
- ソース: `SourceRegistered`, `PassageGenerationStarted`, `PassageGenerationCompleted`, `PassageGenerationFailed`
- フィードバック: `SentenceRecorded`, `FeedbackReady`, `FeedbackFailed`, `LearningItemStocked`, `RetryJudged`
- レビュー: `VariationGenerationRequested`, `VariationReady`, `VariationGenerationFailed`, `ReviewAnswered`, `ReviewRetryJudged`, `SRSUpdated`
- 練習: `ModelAudioRequested`, `ModelAudioReady`, `ModelAudioFailed`, `OverlappingCompleted`, `OverlappingLagDetected`, `LiveDeliveryCompleted`, `PassageAchievementRecorded`
- セッション: `MenuComposed`, `MenuConfirmed`, `MenuRecomposed`, `BackgroundGenerationStarted`, `BackgroundGenerationCompleted`, `SessionStarted`, `SessionInterrupted`, `SessionResumed`, `SessionCompleted`
- 設定: `SettingsChanged`

---

## ディレクトリ構成

```
src/parla/services/
  __init__.py
  settings_service.py          # command service
  source_service.py            # command service
  feedback_service.py          # command service
  review_service.py            # command service
  practice_service.py          # command service
  session_service.py           # command service
  query_models.py              # UI向け read model / DTO
  app_state_query_service.py   # read-only。起動時判定、再開候補、今日メニュー
  source_query_service.py      # read-only。D2, F2 用のソース一覧・進捗集計
  learning_item_query_service.py   # read-only。C2, C3, E3, E4 用の学習項目読み取り
  history_query_service.py     # read-only。C4 用の履歴集計
  session_query_service.py     # read-only。C1, E9, F1, F2 用のサマリー集計

src/parla/ui/
    __init__.py
    app.py              # QApplication + QtAsyncio.run エントリーポイント
    container.py         # DI（全サービス・リポジトリのインスタンス生成と配線）
    theme.py             # カラー、フォント、スペーシング定数
    navigation.py        # タブ切替 + 画面スタック管理
    base_view_model.py   # ViewModel 基底クラス
    audio/
        __init__.py
        recorder.py      # QAudioSource 録音
        player.py        # QMediaPlayer 再生
    widgets/
        __init__.py
        waveform_widget.py    # リアルタイム波形描画
        level_meter_widget.py # レベルメーター
        timer_widget.py       # タイマー
        recording_controls.py # 録音UI複合ウィジェット
        wpm_chart.py          # WPM推移グラフ
        calendar_widget.py    # 学習カレンダー
        phonetic_label.py     # 発音記号付き英文表示
    screens/
        __init__.py
        setup/       # SCREEN-B（初回セットアップ）
        today/       # SCREEN-C1（今日の学習タブ）
        items/       # SCREEN-C2（学習項目一覧）, C3（学習項目詳細）
        history/     # SCREEN-C4（学習履歴タブ）
        settings/    # SCREEN-C5（設定タブ）
        sources/     # SCREEN-D1（ソース登録）, D2（ソース一覧）
        session/     # SCREEN-E1〜E9, F1, F2 + ヘッダー + コーディネーター

tests/services/
    __init__.py
    test_app_state_query_service.py
    test_source_query_service.py
    test_learning_item_query_service.py
    test_history_query_service.py
    test_session_query_service.py

tests/ui/
    __init__.py
    # 上記と対応する構成でテストを配置
```

---

## タスクリスト

### フェーズ -1: Read Model / Query Service（service層）

UI の一覧・履歴・集計・起動時判定は Qt 依存なしで先に固める。このフェーズは top-level の別レイヤーを追加するのではなく、既存の `src/parla/services/` 配下に read-only な Query Service を追加する。このフェーズは `pytest-qt` ではなく通常の `pytest` で TDD する。

- [x] **-1-1: service層内の Query Service 方針と read model DTO の定義**
  - ファイル: `src/parla/services/query_models.py`
  - Query Service の原則を明文化する
    - 読み取り専用
    - EventBus emit なし
    - ViewModel / View に SQL や集計ロジックを書かない
    - UI 向け DTO を返す
    - 既存の command service と同じ service 層に置く
  - 画面と Query Service の対応表を決める（C1/C2/C3/C4/D2/E9/F1/F2）

- [x] **-1-2: アプリ起動状態 Query**
  - ファイル: `src/parla/services/app_state_query_service.py`
  - テスト: `tests/services/test_app_state_query_service.py`
  - 返す内容:
    - 初回セットアップが必要か
    - 再開可能なセッションがあるか
    - 今日の confirmed menu があるか
    - メニュー鮮度チェック結果
  - テスト観点: 初回起動、再開候補あり、今日メニューあり、今日メニューなし

- [x] **-1-3: ソース一覧 / 進捗 Query**
  - ファイル: `src/parla/services/source_query_service.py`
  - テスト: `tests/services/test_source_query_service.py`
  - 対象画面: D2, F2
  - 返す内容:
    - ソース一覧（タイトル、CEFR、英語バリエーション、生成ステータス）
    - 学習進捗率、学習完了状態、次に学習するパッセージ候補
    - フィルタ用の read model
  - テスト観点: フィルタ、進捗率計算、active source 一覧

- [x] **-1-4: 学習項目一覧 Query**
  - ファイル: `src/parla/services/learning_item_query_service.py`
  - テスト: `tests/services/test_learning_item_query_service.py`
  - 対象画面: C2, E3, E4
  - 返す内容:
    - C2 用のフィルタ付き一覧
    - ソース名・カテゴリ・SRS 段階・習得状態を含む行 DTO
    - センテンス単位の関連学習項目一覧（ヒント表示や E4 の項目表示に利用）
  - テスト観点: フィルタ組み合わせ、関連学習項目取得、ソース情報 join

- [x] **-1-5: 学習項目詳細 Query**
  - ファイル: `src/parla/services/learning_item_query_service.py`
  - テスト: `tests/services/test_learning_item_query_service.py`
  - 対象画面: C3
  - 返す内容:
    - 初出時の発話
    - 各復習での発話・判定履歴
    - WPM 推移グラフ用系列
    - 元ソース・元センテンス情報
  - テスト観点: 成長ストーリー集約、履歴順序、WPM 系列生成
  - 備考: 必要データが不足する場合、このフェーズで不足永続化項目を確定してから UI に進む

- [x] **-1-6: 学習履歴 Query**
  - ファイル: `src/parla/services/history_query_service.py`
  - テスト: `tests/services/test_history_query_service.py`
  - 対象画面: C4
  - 返す内容:
    - カレンダーマーカー用日付一覧
    - 日別サマリー
    - 累計 WPM 推移
  - テスト観点: 日付集約、サマリー計算、WPM トレンド

- [x] **-1-7: 今日メニュー / パッセージ / セッション summary Query**
  - ファイル: `src/parla/services/session_query_service.py`
  - テスト: `tests/services/test_session_query_service.py`
  - 対象画面: C1, E9, F1, F2
  - 返す内容:
    - C1 用の今日メニュー表示 DTO
    - E9 用のパッセージ完了サマリー DTO
    - F1 用のセッション終了サマリー DTO
    - F2 用のメニュー preview DTO
  - テスト観点: メニュー表示、パッセージ結果集計、セッション成果集計

### フェーズ 0: 基盤整備

- [x] **0-1: 依存関係の追加**
  - `pyproject.toml` に `PySide6>=6.7` を dependencies に追加
  - `pyproject.toml` の dev dependencies に `pytest-qt` を追加
  - `uv sync` で導入確認

- [x] **0-2: ドキュメント修正（テスト方針の矛盾解消）**
  - `docs/architecture/implementation-plan.md` 38行目: 「UI | 頻繁に変わる | 手動確認」→ pytest-qt で TDD に変更
  - `docs/architecture/overview.md` 416行目: 「UIのテスト | UIは頻繁に変わる。手動確認で十分」→ pytest-qt で TDD に変更

- [x] **0-3: EventBus に unsubscribe 機能を追加**
  - `src/parla/event_bus.py` に `off_sync(event_type, handler)` / `off_async(event_type, handler)` メソッドを追加
  - ViewModel の `activate()` / `deactivate()` でハンドラの登録/解除に使用する
  - 既存テストが壊れないことを確認

- [x] **0-4: ViewModel 基底クラス**
  - ファイル: `src/parla/ui/base_view_model.py`
  - テスト: `tests/ui/test_base_view_model.py`
  - `QObject` 継承、`activate()` / `deactivate()` でEventBusハンドラの登録/解除
  - テスト観点: activate で登録されること、deactivate で解除されること、イベント受信で Signal が発火すること

- [x] **0-5: ナビゲーションコントローラー**
  - ファイル: `src/parla/ui/navigation.py`
  - テスト: `tests/ui/test_navigation.py`
  - `QTabBar` + `QStackedWidget` で4メインタブ（今日の学習 / 学習項目 / 学習履歴 / 設定）
  - セッション用の別 `QStackedWidget`（セッション中はタブ全体を隠す）
  - プッシュ/ポップ遷移（C2→C3、C5→D1/D2 等）
  - テスト観点: タブ切替、プッシュ/ポップ遷移、セッションモード切替（タブ非表示）

- [x] **0-6: DI コンテナ**
  - ファイル: `src/parla/ui/container.py`
  - EventBus、SQLite DB接続、各 Repository/Port アダプタ、既存の command service、service層の Query Service の生成・配線
  - サービス側の async ハンドラを EventBus に登録
  - ViewModel はコンテナから直接生成しない（各画面のファクトリが必要なサービスを受け取って生成）

- [x] **0-7: アプリエントリーポイント**
  - ファイル: `src/parla/ui/app.py`, `src/parla/__main__.py`
  - `QApplication` 生成 → コンテナ初期化 → `AppStateQueryService.get_bootstrap_state()` で起動先判定 → `QtAsyncio.run()`
  - `python -m parla` で起動可能にする

---

### フェーズ 1: 共通ウィジェット

- [x] **1-1: 波形表示ウィジェット**
  - ファイル: `src/parla/ui/widgets/waveform_widget.py`
  - テスト: `tests/ui/widgets/test_waveform_widget.py`
  - `QPainter` でリアルタイム波形描画、リングバッファ方式
  - `update_samples(samples: np.ndarray)` でデータ更新
  - E1, E2, E3, E6 で共用
  - テスト観点: サンプルデータ更新で再描画されること、バッファサイズ管理

- [x] **1-2: レベルメーターウィジェット**
  - ファイル: `src/parla/ui/widgets/level_meter_widget.py`
  - テスト: `tests/ui/widgets/test_level_meter_widget.py`
  - RMS レベルを縦バーで表示、低レベル時に警告色
  - `set_level(rms: float)` で更新
  - テスト観点: レベル設定、警告閾値判定

- [x] **1-3: タイマーウィジェット**
  - ファイル: `src/parla/ui/widgets/timer_widget.py`
  - テスト: `tests/ui/widgets/test_timer_widget.py`
  - カウントダウン / カウントアップ両対応、`QTimer` 100ms 更新
  - `timeout` Signal 発火、`start()`, `stop()`, `reset()`, `elapsed_ratio() -> float`
  - テスト観点: カウントダウンでtimeout Signal発火、elapsed_ratio計算、start/stop/reset動作

- [x] **1-4: 録音コントロールウィジェット**
  - ファイル: `src/parla/ui/widgets/recording_controls.py`
  - テスト: `tests/ui/widgets/test_recording_controls.py`
  - 波形 + レベルメーター + 録音ボタンの複合ウィジェット
  - `recording_finished(AudioData)` Signal
  - AudioRecorder はモック注入で差し替え
  - テスト観点: ボタン操作で録音開始/停止、完了 Signal 発火

- [x] **1-5: WPM推移グラフ**
  - ファイル: `src/parla/ui/widgets/wpm_chart.py`
  - テスト: `tests/ui/widgets/test_wpm_chart.py`
  - `QPainter` 折れ線グラフ、CEFR 目標レンジ帯表示
  - C3, C4, F1 で共用
  - テスト観点: データ設定、CEFR レンジ表示

- [x] **1-6: カレンダーウィジェット**
  - ファイル: `src/parla/ui/widgets/calendar_widget.py`
  - テスト: `tests/ui/widgets/test_calendar_widget.py`
  - 学習実施日にマーカー表示、日付クリックで `date_selected(date)` Signal
  - テスト観点: マーカー設定、日付選択 Signal 発火

- [x] **1-7: 発音記号付きラベル**
  - ファイル: `src/parla/ui/widgets/phonetic_label.py`
  - テスト: `tests/ui/widgets/test_phonetic_label.py`
  - 英文各単語下に発音記号、ON/OFF 切替、特定単語ハイライト機能
  - テスト観点: ON/OFF 切替、ハイライト設定

---

### フェーズ 2: 音声インフラ

- [x] **2-1: 音声録音マネージャー**
  - ファイル: `src/parla/ui/audio/recorder.py`
  - テスト: `tests/ui/audio/test_recorder.py`
  - `QAudioSource` + `QMediaDevices.audioInputs()` でマイク列挙・選択
  - PCM 16bit mono 16kHz
  - リアルタイムで波形データ・RMS を Signal 通知
  - 録音完了時に `AudioData`（`src/parla/domain/audio.py`）を生成
  - テスト観点: QAudioSource をモック、AudioData 生成の正しさ、Signal 発火

- [x] **2-2: 音声再生マネージャー**
  - ファイル: `src/parla/ui/audio/player.py`
  - テスト: `tests/ui/audio/test_player.py`
  - `QMediaPlayer` + `QAudioOutput` で再生
  - 速度調整（0.5x〜2.0x）
  - `playback_position_changed(seconds)` Signal（オーバーラッピング時のリアルタイムハイライト用）
  - テスト観点: QMediaPlayer をモック、速度設定、position Signal 発火

---

### フェーズ 3: 静的画面（ViewModel パターン検証）

各画面は View（QWidget）と ViewModel（QObject）のペアで構成する。

- [ ] **3-1: 設定画面 (SCREEN-C5)**
  - ファイル: `src/parla/ui/screens/settings/view.py`, `src/parla/ui/screens/settings/view_model.py`
  - テスト: `tests/ui/screens/settings/test_view_model.py`, `tests/ui/screens/settings/test_view.py`
  - 最もシンプルな CRUD 画面。ViewModel パターンの動作確認に最適
  - ViewModel: `SettingsService.get_settings()` / `update_settings()` 呼び出し、`SettingsChanged` イベントハンドル
  - View: CEFR レベル `QComboBox`、英語バリエーション `QComboBox`、発音記号 `QCheckBox`、ソース管理ボタン
  - テスト観点: 設定読み込み→表示、変更→サービス呼び出し、イベント受信→UI更新

- [ ] **3-2: 初回セットアップ画面 (SCREEN-B)**
  - ファイル: `src/parla/ui/screens/setup/view.py`, `src/parla/ui/screens/setup/view_model.py`
  - テスト: `tests/ui/screens/setup/test_view_model.py`, `tests/ui/screens/setup/test_view.py`
  - CEFR 選択（各レベルに日本語説明付き）+ 英語バリエーション選択
  - 確定後 C1 へ遷移
  - テスト観点: 選択操作、確定でサービス呼び出し、遷移 Signal

- [ ] **3-3: ソース登録画面 (SCREEN-D1)**
  - ファイル: `src/parla/ui/screens/sources/registration_view.py`, `src/parla/ui/screens/sources/registration_view_model.py`
  - テスト: `tests/ui/screens/sources/test_registration_view_model.py`, `tests/ui/screens/sources/test_registration_view.py`
  - テキスト入力（100〜50,000文字）、タイトル、CEFR レベル自動表示
  - `PassageGenerationStarted` / `Completed` / `Failed` イベントで生成進捗表示
  - テスト観点: バリデーション（文字数）、登録→サービス呼び出し、進捗イベント→表示更新

- [ ] **3-4: ソース一覧画面 (SCREEN-D2)**
  - ファイル: `src/parla/ui/screens/sources/list_view.py`, `src/parla/ui/screens/sources/list_view_model.py`
  - テスト: `tests/ui/screens/sources/test_list_view_model.py`, `tests/ui/screens/sources/test_list_view.py`
  - `SourceQueryService.list_sources()` で初期表示
  - フィルタ付きリスト、各ソースのプログレスバー、学習完了状態
  - `SourceRegistered` / `PassageGenerationCompleted` / `PassageGenerationFailed` イベントで差分更新
  - テスト観点: フィルタ適用、イベント受信→リスト更新

- [ ] **3-5: 今日の学習タブ (SCREEN-C1)**
  - ファイル: `src/parla/ui/screens/today/view.py`, `src/parla/ui/screens/today/view_model.py`
  - テスト: `tests/ui/screens/today/test_view_model.py`, `tests/ui/screens/today/test_view.py`
  - `SessionQueryService.get_today_dashboard()` で初期表示
  - セッションメニュー表示（ブロック一覧 + 推定時間）
  - 「学習開始」ボタン（メニューが無い/未確定の場合は無効）
  - テスト観点: メニュー有無による表示切替、学習開始ボタンの有効/無効制御

---

### フェーズ 4: 一覧・詳細画面

- [ ] **4-1: 学習項目一覧 (SCREEN-C2)**
  - ファイル: `src/parla/ui/screens/items/list_view.py`, `src/parla/ui/screens/items/list_view_model.py`
  - テスト: `tests/ui/screens/items/test_list_view_model.py`, `tests/ui/screens/items/test_list_view.py`
  - `LearningItemQueryService.list_items()` で初期表示・フィルタ反映
  - フィルタ付きリスト（SRS 段階、カテゴリ、ソース、習得状態）
  - クリックで C3 へプッシュ遷移
  - テスト観点: フィルタ操作、項目クリック→遷移 Signal

- [ ] **4-2: 学習項目詳細 (SCREEN-C3)**
  - ファイル: `src/parla/ui/screens/items/detail_view.py`, `src/parla/ui/screens/items/detail_view_model.py`
  - テスト: `tests/ui/screens/items/test_detail_view_model.py`, `tests/ui/screens/items/test_detail_view.py`
  - `LearningItemQueryService.get_item_detail()` で集約読み取り
  - 成長ストーリー（初出時発話 → 各復習での発話推移）
  - WPM推移グラフ（`WpmChartWidget` 使用）
  - テスト観点: データ取得→表示、グラフ表示

- [ ] **4-3: 学習履歴タブ (SCREEN-C4)**
  - ファイル: `src/parla/ui/screens/history/view.py`, `src/parla/ui/screens/history/view_model.py`
  - テスト: `tests/ui/screens/history/test_view_model.py`, `tests/ui/screens/history/test_view.py`
  - `HistoryQueryService.get_history_overview()` / `get_daily_summary()` で初期表示
  - カレンダー（学習日マーク）、WPM推移グラフ、日別サマリー
  - テスト観点: 日付選択→サマリー表示、カレンダーマーカー

---

### フェーズ 5: セッション系画面（コア学習フロー）

セッション中はタブバーを非表示にし、セッション専用のナビゲーションスタック上で動作する。

- [ ] **5-0: セッションヘッダーウィジェット**
  - ファイル: `src/parla/ui/screens/session/header.py`
  - テスト: `tests/ui/screens/session/test_header.py`
  - 全セッション画面上部に常時表示
  - 表示: ブロック名+進捗（例: 「ブロック1 復習 (8/20)」）、経過時間、累計ワード数、平均WPM
  - テスト観点: 進捗更新、経過時間カウント

- [ ] **5-1: マイクチェック画面 (SCREEN-E1)**
  - ファイル: `src/parla/ui/screens/session/mic_check_view.py`, `src/parla/ui/screens/session/mic_check_view_model.py`
  - テスト: `tests/ui/screens/session/test_mic_check_view_model.py`, `tests/ui/screens/session/test_mic_check_view.py`
  - マイクデバイス選択ドロップダウン
  - リアルタイム波形 + レベルメーター
  - 入力レベル低すぎる場合は警告表示
  - 「開始」ボタン（十分なレベル検知後に有効化）
  - AudioRecorder の初期化・動作確認を兼ねる。選択マイクはセッション全体で共有
  - テスト観点: マイク選択、レベル検知→ボタン有効化、警告表示

- [ ] **5-2: ブロック1/3 復習画面 (SCREEN-E2)**
  - ファイル: `src/parla/ui/screens/session/review_view.py`, `src/parla/ui/screens/session/review_view_model.py`
  - テスト: `tests/ui/screens/session/test_review_view_model.py`, `tests/ui/screens/session/test_review_view.py`
  - 学習項目名（SRS段階に応じた表示制御）、日本語お題
  - タイマー、録音UI、ヒント段階的開示（0→1→2）
  - フロー:
    1. `ReviewService.request_variation()` → `VariationReady` で問題表示
    2. 録音完了 → `asyncio.create_task(review_service.judge_review())` → `ReviewAnswered` で結果表示
    3. 正解: 簡易フィードバック → 1.5秒後自動遷移
    4. 不正解: 模範解答 → ヒント → リトライ（最大3回、`judge_review_retry()`）
    5. 全問完了 → `session_service.advance_block()`
  - テスト観点: ヒント段階開示、正解/不正解フロー、自動遷移タイミング、リトライ回数制限

- [ ] **5-3: フェーズA 発話画面 (SCREEN-E3)**
  - ファイル: `src/parla/ui/screens/session/phase_a_view.py`, `src/parla/ui/screens/session/phase_a_view_model.py`
  - テスト: `tests/ui/screens/session/test_phase_a_view_model.py`, `tests/ui/screens/session/test_phase_a_view.py`
  - パッセージの全センテンス一覧表示（日本語お題）
  - 現在センテンスのハイライト
  - タイマー、録音UI
  - `LearningItemQueryService.get_sentence_items()` でヒント有無を判定
  - ヒントボタン（関連学習項目がある場合のみ表示）
  - 録音完了で `FeedbackService.record_sentence()` → 自動で次センテンスへ
  - 全センテンス完了で E4（フェーズB）へ遷移
  - テスト観点: センテンス進行、録音→サービス呼び出し、ヒント表示判定

- [ ] **5-4: フェーズB フィードバック画面 (SCREEN-E4)** ← 最も複雑
  - ファイル: `src/parla/ui/screens/session/phase_b_view.py`, `src/parla/ui/screens/session/phase_b_view_model.py`
  - テスト: `tests/ui/screens/session/test_phase_b_view_model.py`, `tests/ui/screens/session/test_phase_b_view.py`
  - **プログレッシブ表示**: `FeedbackReady` イベントがセンテンスごとに個別到着 → 1件ずつ UI に追加
  - センテンスごとの表示:
    - ユーザー発話再現テキスト
    - 動的模範解答
    - 正誤ステータス
  - 学習項目リスト（`LearningItemStocked` イベントで更新。自動ストック済み / 要確認 / 再出フラグ）
  - 即時リトライ: 録音 → `FeedbackService.judge_retry()` → `RetryJudged` イベント（最大3回）
  - 「項目を編集」ボタン → E5 シートを開く
  - 「次へ」ボタン → `PracticeService.should_skip()` 判定 → E6 or E9 へ遷移
  - テスト観点: プログレッシブ表示（イベント到着順の表示追加）、リトライフロー、学習項目リスト更新

- [ ] **5-5: 学習項目編集シート (SCREEN-E5)**
  - ファイル: `src/parla/ui/screens/session/item_edit_view.py`, `src/parla/ui/screens/session/item_edit_view_model.py`
  - テスト: `tests/ui/screens/session/test_item_edit_view_model.py`, `tests/ui/screens/session/test_item_edit_view.py`
  - モーダルダイアログまたはスライドインシート
  - 学習項目の編集（パターン、説明）、除外、手動追加
  - テスト観点: 編集→保存、除外操作、手動追加

- [ ] **5-6: フェーズC 練習ワークスペース (SCREEN-E6)** ← 2番目に複雑
  - ファイル: `src/parla/ui/screens/session/phase_c_view.py`, `src/parla/ui/screens/session/phase_c_view_model.py`
  - テスト: `tests/ui/screens/session/test_phase_c_view_model.py`, `tests/ui/screens/session/test_phase_c_view.py`
  - 3モード切替: リスニング / オーバーラッピング / 本番発話
  - 表示:
    - 英文テキスト（学習項目部分ハイライト）
    - 発音記号（`PhoneticLabel` 使用、設定 ON/OFF）
    - 日本語お題（本番発話モード時は主表示）
    - TTS 再生コントロール + 速度スライダー（0.75x, 1.0x, 1.25x）
    - 録音UI + リアルタイム波形
    - オーバーラッピング時: 再生位置のリアルタイムハイライト
    - 結果表示（合格/不合格/差分要約）
  - サービス連携:
    - リスニング: `AudioPlayer.play()` でモデル音声再生
    - オーバーラッピング: モデル音声再生+同時録音 → `PracticeService.evaluate_overlapping()` + `detect_lag()`
    - 本番発話: 録音 → `PracticeService.evaluate_live_delivery()`
  - イベント: `ModelAudioReady/Failed`, `OverlappingCompleted`, `OverlappingLagDetected`, `LiveDeliveryCompleted`
  - 練習順序・回数はユーザー自由（推奨アクションは表示してよい）
  - テスト観点: モード切替、各モードのサービス連携、結果表示

- [ ] **5-7: パッセージ完了サマリー (SCREEN-E9)**
  - ファイル: `src/parla/ui/screens/session/passage_summary_view.py`, `src/parla/ui/screens/session/passage_summary_view_model.py`
  - テスト: `tests/ui/screens/session/test_passage_summary_view_model.py`, `tests/ui/screens/session/test_passage_summary_view.py`
  - `SessionQueryService.get_passage_summary()` で集約読み取り
  - パッセージ学習結果サマリー（完了 / 通し発話達成の有無）
  - ストック学習項目一覧
  - WPM結果
  - 「次のパッセージへ」/ 「ブロック完了」ボタン
  - テスト観点: 結果集計表示、遷移ボタン

- [ ] **5-8: セッション終了サマリー (SCREEN-F1)**
  - ファイル: `src/parla/ui/screens/session/session_summary_view.py`, `src/parla/ui/screens/session/session_summary_view_model.py`
  - テスト: `tests/ui/screens/session/test_session_summary_view_model.py`, `tests/ui/screens/session/test_session_summary_view.py`
  - `SessionQueryService.get_session_summary()` で集約読み取り
  - 今日の成果: パッセージ数、新規項目数、復習正答率、WPM推移等
  - WPM推移グラフ（`WpmChartWidget`）
  - 「次へ」ボタン → F2 へ
  - テスト観点: 成果集計表示

- [ ] **5-9: 明日のメニュー確定 (SCREEN-F2)**
  - ファイル: `src/parla/ui/screens/session/tomorrow_menu_view.py`, `src/parla/ui/screens/session/tomorrow_menu_view_model.py`
  - テスト: `tests/ui/screens/session/test_tomorrow_menu_view_model.py`, `tests/ui/screens/session/test_tomorrow_menu_view.py`
  - `SessionQueryService.get_menu_preview()` と `SourceQueryService.list_active_sources()` で初期表示
  - `SessionService.compose_menu()` で自動構成したメニュー表示
  - 各ブロックの内容と推定時間
  - 素材変更（`recompose_menu()`、進行中ソース一覧 + 新規追加ボタン）
  - 「このメニューで確定」ボタン → `confirm_menu()`
  - `BackgroundGenerationStarted` / `Completed` イベントで進捗表示
  - テスト観点: メニュー表示、素材変更、確定→サービス呼び出し、バックグラウンド進捗

---

### フェーズ 6: セッション遷移ロジック

- [ ] **6-1: セッションコーディネーター**
  - ファイル: `src/parla/ui/screens/session/coordinator.py`
  - テスト: `tests/ui/screens/session/test_coordinator.py`
  - 画面遷移を制御する上位コントローラー
  - AudioRecorder インスタンスを保持し、各画面の ViewModel に渡す
  - 遷移ルール:
    ```
    C1「学習開始」→ E1 マイクチェック
    E1 完了 → ブロック判定
      review ブロック → E2
      new_material ブロック → E3（パッセージ単位で繰り返し）
      consolidation ブロック → E2
    E2 全問完了 → advance_block → 次ブロック
    E3 全文完了 → E4
    E4 完了 → should_skip ? E9 : E6
    E6 完了 → E9
    E9 完了 → 次パッセージ or advance_block
    最終ブロック完了 → F1
    F1 → F2
    F2 確定 → メインタブ復帰
    ```
  - テスト観点: 各遷移パターン（全パスを網羅）

- [ ] **6-2: セッション中断/再開**
  - ファイル: 6-1 のコーディネーターに追加
  - テスト: 6-1 のテストに追加
  - ウィンドウ閉じ or 中断ボタン → `SessionService.interrupt_session()`
  - 次回起動時に中断セッションがあれば `resume_session()` で中断ブロックの先頭からやり直す
  - テスト観点: 中断→状態保存、再開→正しいブロックから復帰

---

### フェーズ 7: スタイリングと仕上げ

- [ ] **7-1: テーマ定数**
  - ファイル: `src/parla/ui/theme.py`
  - カラーパレット、フォント（日本語対応: Noto Sans JP 等）、スペーシング定数
  - 全ウィジェットに共通 QSS（Qt Style Sheet）を適用

- [ ] **7-2: ウィンドウサイズとレイアウト調整**
  - 初期ウィンドウサイズ、最小サイズ制約
  - レスポンシブレイアウト

- [ ] **7-3: エラーハンドリング UI**
  - サービス呼び出し失敗時のエラーダイアログ
  - `FeedbackFailed`, `ModelAudioFailed`, `VariationGenerationFailed`, `PassageGenerationFailed` 等のエラーイベント表示
  - ネットワークエラー時のリトライ UI

---

## 並行作業メモ

- フェーズ -1 はフェーズ 3〜6 の前提であり、原則として最初に完了させる
- フェーズ -1 は Qt 非依存なので単独で先行可能
- フェーズ 1 と フェーズ 2 は独立しており並行可能
- フェーズ 3 と フェーズ 4 は独立しており並行可能
- フェーズ 5 はフェーズ 1 + 2 の完了が前提
- フェーズ 6 はフェーズ 5 の完了が前提
- フェーズ 7 は最後に実施

## 推奨着手順

-1（Read Model / Query Service）→ 0（基盤）→ 1+2（並行）→ 3-1（設定画面で ViewModel パターン検証）→ 3-5（C1）→ 5-1（マイクチェックで音声結合確認）→ 5-2（復習）→ 5-3 → 5-4 → 5-6 → 残り
