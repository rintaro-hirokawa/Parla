# Principal Engineer Code Review

レビュー日: 2026-04-11
対象: Parla コードベース全体（`src/parla/`, `tests/`）
レビュアー: Principal Engineer

---

## 総評

アーキテクチャ文書（`docs/architecture/overview.md`）に記述された設計方針は**非常に優れている**。ヘキサゴナルアーキテクチャ、イベント駆動、依存性逆転、MVVM — どれも正しい判断だ。そして実装も、**文書の方針を概ね忠実に反映している**。ジュニアエンジニアが書いたにしては相当レベルが高い。

ただし、設計方針を「理解はしているが体得はしていない」箇所がいくつかあり、それが積み重なるとアーキテクチャの根幹を侵食する。このレビューでは、表面的なコード品質ではなく**設計判断の根本**に踏み込んでフィードバックする。

---

## 1. [Critical] サービス層へのドメインロジック流出

### 問題

アーキテクチャ文書には「ドメインが最も重要であり、最も安定している」と書いてある。しかし実装では、**ビジネスルールの相当部分がサービス層に散逸している**。

#### 具体例 A: `PracticeService._map_words_to_sentences()`

`src/parla/services/practice_service.py:384-425`

この50行のstaticmethodは「評価済み単語列をセンテンスに割り当て、類似度を計算し、合否判定する」という**純粋なドメインロジック**だ。Azure APIやDBには一切触れていない。にもかかわらずサービス層にある。

```python
# practice_service.py:384 — これはドメインロジック
@staticmethod
def _map_words_to_sentences(
    sentence_texts: list[str],
    assessed_words: tuple[PronunciationWord, ...],
) -> list[SentenceStatus]:
    ...
    similarity = calculate_similarity(text, user_text)
    status = judge_sentence_status(similarity, omission_ratio)
```

このメソッドは `domain/similarity.py` や `domain/practice.py` にあるべきだ。実際、`calculate_similarity()` や `judge_sentence_status()` はドメインに定義されているのに、それを**呼び出すオーケストレーション自体がサービスに逃げている**。

#### 具体例 B: `SessionService._select_next_passages()`

`src/parla/services/session_service.py:171-183`

「次に学ぶべきパッセージの選択」は**セッションドメインの中核的な判断**だ。これがサービスにある理由は「リポジトリを呼ぶ必要があるから」だが、ロジック自体（「全センテンスにフィードバックがないパッセージを順に探す」）はドメイン関数として表現できる。サービスはデータ取得だけを担い、判定ロジックをドメインに移すべきだ。

#### 具体例 C: `FeedbackService._convert_learning_items()`

`src/parla/services/feedback_service.py:196-221`

LLM出力からドメインエンティティへの変換。これは **ドメインファクトリ関数** であり、`domain/learning_item.py` に `LearningItem.from_raw_feedback()` のようなクラスメソッドとして配置すべきだ。

### なぜ問題か

1. **テスタビリティの低下**: これらのメソッドはすべて `_` プレフィックスのprivateメソッドで、直接テストできない。ドメイン関数であれば、サービスやリポジトリのセットアップなしに純粋にテストできる
2. **ドメインの空洞化**: `domain/` に入っているのは型定義と小さなユーティリティ関数だけになり、ドメインモデルが「データ構造の置き場」に退化する
3. **ヘキサゴナルの本意からの乖離**: ドメインが薄くサービスが厚いのは、実質的にレイヤードアーキテクチャと同じ

### 推奨

「リポジトリへのアクセスが必要」という理由だけでドメインロジックをサービスに置かない。パターンとしては:
- サービスがリポジトリからデータを取得する
- 取得したデータをドメイン関数に渡す
- ドメイン関数が判断を返す
- サービスが結果を永続化/イベント発火する

---

## 2. [Critical] `Container` が God Object になっている

### 問題

`src/parla/ui/container.py` は DI コンテナを名乗っているが、実態は **222行のGod Object** だ。

```python
class Container:
    def __init__(self, *, db_path: str | Path = "") -> None:
        # 8つのリポジトリ
        self.session_repo = SQLiteSessionRepository(self.conn)
        self.source_repo = SQLiteSourceRepository(self.conn)
        # ... 6つ省略

        # 8つの外部アダプタ
        self.audio_storage = LocalAudioStorage(base_dir=audio_dir)
        self.passage_generator = GeminiPassageGenerationAdapter()
        # ... 6つ省略

        # 6つのコマンドサービス
        self.settings_service = SettingsService(...)
        self.source_service = SourceService(...)
        # ... 4つ省略

        # EventBusハンドラ登録（6行）
        self.event_bus.on_async(SourceRegistered)(self.source_service.handle_source_registered)
        # ...

        # 5つのクエリサービス
        self.app_state_query = AppStateQueryService(...)
        # ... 4つ省略
```

### なぜ問題か

1. **UIレイヤーに配置されている**: `src/parla/ui/container.py` — DIコンテナがUIパッケージ内にあるのは構造的に誤り。UIからドメイン/サービス/アダプタ全てをimportしている
2. **全てがpublicフィールド**: `SessionCoordinator` が `self._c.feedback_repo` や `self._c.item_repo` に直接アクセスしている。UIからリポジトリへの直接アクセスは、ヘキサゴナルの層境界を完全に無視している
3. **テストの困難さ**: Containerを差し替えるためのインターフェースがなく、テスト時に個別の依存を差し替えにくい

### 推奨

- Container を `src/parla/` のルート（`__init__.py` 相当の場所）に移す
- 少なくとも、UIが直接アクセスしてよいもの（サービス、クエリサービス）とそうでないもの（リポジトリ、アダプタ）を構造的に分離する
- `SessionCoordinator` がリポジトリに直接アクセスしている箇所は、サービスまたはクエリサービス経由に書き換える

---

## 3. [Critical] `SessionCoordinator` の責務過剰

### 問題

`src/parla/ui/screens/session/coordinator.py` は 502 行あり、以下の全てを担っている:

- セッション開始/中断/再開の制御
- ブロックのディスパッチ（review / new_material / consolidation）
- Phase A → B → C → PassageSummary のナビゲーション遷移
- 全ViewModelのインスタンス化と接続
- EventBusハンドラの動的な登録/解除
- パッセージ内のインデックス管理
- 翌日メニューの構成とUI表示
- ソース登録画面のpush
- ItemEdit モーダルの表示

### なぜ問題か

これは **「1つのことだけをうまくやる」の対極** にある。新しいフェーズの追加、フローの変更、テストの追加 — どれもこの巨大クラスに触れる必要がある。

さらに深刻なのは、Coordinatorが **Containerのリポジトリに直接アクセスしている** こと:

```python
# coordinator.py:69
self._menu = self._c.session_repo.get_menu(menu_id)

# coordinator.py:170-171
item = self._c.item_repo.get_item(item_id)
source = self._c.source_repo.get_source_by_sentence_id(item.source_sentence_id)
```

UIレイヤーからリポジトリ（アダプタ実装）への直接アクセスは、ヘキサゴナルの原則違反だ。

### 推奨

- `_resolve_review_items()` のようなデータ解決ロジックはサービス層に移す
- ViewModel のインスタンス化をファクトリに抽出する
- 最低限、Coordinatorがアクセスするのはサービスとクエリサービスだけにする

---

## 4. [Important] EventBusの型安全性の穴

### 問題

`BaseViewModel._register_sync()` は `Callable[..., None]` という型を受ける:

```python
# base_view_model.py:24
def _register_sync(self, event_type: type[Event], handler: Callable[..., None]) -> None:
    self._sync_registrations.append((event_type, handler))
```

`...` は全ての引数を受け入れるので、**間違ったイベント型のハンドラを登録しても型チェッカーが検出できない**。EventBus本体の `on_sync` はジェネリクスで正しく型付けされているのに、BaseViewModelで型安全性が失われている。

### 推奨

`Callable[[Event], None]` として最低限の型制約を入れるか、EventBusの `on_sync` デコレータを直接使うパターンに統一する。

---

## 5. [Important] `asyncio.ensure_future` の乱用

### 問題

ViewModel層で `asyncio.ensure_future()` が多用されている:

```python
# phase_b_view_model.py:162
asyncio.ensure_future(
    self._feedback_service.judge_retry(
        sentence_id=sentence_id,
        attempt=count + 1,
        audio=audio,
    )
)

# review_view_model.py:137
asyncio.ensure_future(
    self._review_service.judge_review(...)
)

# phase_c_view_model.py:207
asyncio.ensure_future(
    self._practice_service.evaluate_overlapping(self._passage_id, audio)
)
```

### なぜ問題か

1. **例外が握りつぶされる**: `ensure_future` から返されるTaskが保持されていないため、タスク内で発生した例外は `Task was destroyed but it is pending!` という警告のみで消える
2. **ライフサイクルの分離**: ViewModelが `deactivate()` された後もタスクが走り続ける可能性がある。結果がEventBus経由で返ってきても、ハンドラは既に解除されている

### 推奨

- タスク参照を保持し、`deactivate()` 時にキャンセルする
- エラーハンドリングを `ensure_future` のラッパーで統一する。例:

```python
def _run_async(self, coro: Coroutine) -> None:
    task = asyncio.ensure_future(coro)
    self._pending_tasks.append(task)
    task.add_done_callback(self._on_task_done)
```

---

## 6. [Important] PracticeService の巨大さと重複

### 問題

`src/parla/services/practice_service.py` は 426 行、15以上のメソッドを持ち、3つの独立したワークフローを1つのクラスに押し込んでいる:

1. **モデル音声生成** (TTS)
2. **オーバーラッピング評価** (Azure Pronunciation + Lag Detection)
3. **本番発話評価** (Live Delivery)

さらに、以下のコードがほぼ同一の形で3箇所に存在する:

```python
# lines 155-158, 200-203 (重複)
user_offsets = [w.offset_seconds for w in words if w.error_type != "Omission" and w.offset_seconds >= 0]
ref_offsets = [wt.start_seconds for wt in model_audio.word_timestamps]
n = min(len(user_offsets), len(ref_offsets))
deviations = calculate_timing_deviations(user_offsets[:n], ref_offsets[:n], baseline_correction=False)
```

そして `finalize_overlapping_stream()` と `evaluate_overlapping()` は、streaming版とbatch版で処理のほとんどが共通であるにもかかわらず、別メソッドとして丸ごとコピーされている。

### 推奨

- タイミング偏差計算はドメイン関数として `domain/timing.py` に抽出
- overlapping結果の組み立てをprivateメソッドに統合
- PracticeServiceの分割を検討（ただし、プロトタイプ期なので「分割して3ファイルにする」よりも「共通処理を括り出す」方が現実的）

---

## 7. [Important] SQLiteリポジトリのトランザクション管理の不在

### 問題

全てのSQLiteリポジトリで、各操作が個別にcommitされている:

```python
# sqlite_source_repository.py:87 — save_passages内
for passage in passages:
    self._conn.execute("INSERT INTO passages ...", (...))
    for sentence in passage.sentences:
        self._conn.execute("INSERT INTO sentences ...", (...))
self._conn.commit()  # 最後にまとめてcommitされているように見えるが...
```

しかし他のリポジトリでは:

```python
# sqlite_feedback_repository.py のsave_feedback — 1行ごとにcommit
self._conn.execute("INSERT INTO sentence_feedback ...", (...))
self._conn.commit()
```

### なぜ問題か

1. **原子性の欠如**: 複数のリポジトリにまたがる操作（例: フィードバック保存 + 学習項目保存）が途中で失敗すると、データが不整合になる
2. **パフォーマンス**: 各INSERT毎のcommitはSQLiteの最も遅い使い方。バッチでのcommitと比較して100倍以上遅い場合がある

### 推奨

- サービス層でUnit of Workパターンを導入するか、少なくとも `conn.execute()` のcommitをサービスレベルで管理する
- プロトタイプ期の現実的なアプローチとしては、`save_*` メソッドからcommitを外し、サービス側で `conn.commit()` を呼ぶ

---

## 8. [Important] ドメインイベントが `event_bus.py` に依存

### 問題

`src/parla/domain/events.py` の1行目:

```python
from parla.event_bus import Event
```

ドメインイベントの基底クラス `Event` が `event_bus.py`（インフラ）で定義されており、ドメインがインフラに依存している。これは **ヘキサゴナルアーキテクチャの依存方向に違反する**。

`event_bus.py` は `pydantic.BaseModel` を継承した `Event` クラスと、`EventBus` クラスの両方を含んでいる。

### 推奨

`Event` 基底クラスをドメイン層に移す。例えば `domain/events.py` の先頭で定義するか、`domain/base.py` のようなモジュールを作る。`EventBus` 本体は引き続きインフラに置く。

---

## 9. [Moderate] `datetime.now()` のデフォルト値

### 問題

多くのドメインモデルで `default_factory=datetime.now` が使われている:

```python
# feedback.py:17
created_at: datetime = Field(default_factory=datetime.now)

# session.py:47
created_at: datetime = Field(default_factory=datetime.now)

# learning_item.py:38
created_at: datetime = Field(default_factory=datetime.now)
```

同様に、サービス層でも `datetime.now()` や `date.today()` が直接呼ばれている:

```python
# session_service.py:299
updated = state.model_copy(update={"status": "interrupted", "interrupted_at": datetime.now()})
```

### なぜ問題か

1. **テスト時の時刻制御が困難**: テストで「3日後」をシミュレートするには `freezegun` 等のモンキーパッチが必要になる
2. **非決定性**: 同一テストの実行ごとに異なるタイムスタンプが生成される

`compose_menu()` のような一部のメソッドは `today: date` パラメータを受け取っており、正しいアプローチを理解している。しかし**徹底されていない**。

### 推奨

全体的なアプローチの統一として、サービスメソッドでは `now` / `today` を必ずパラメータで受け取り、ドメインモデルの `default_factory` は呼び出し側が明示的に渡す形に統一する。

---

## 10. [Moderate] Geminiアダプタのボイラープレート重複

### 問題

6つのGeminiアダプタ（feedback, passage, variation, retry_judgment, review_judgment, overlapping_lag）が**全く同じパターン**で実装されている:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
async def some_method(self, ...) -> ReturnType:
    logger.info("llm_call_start", model=self._model, ...)
    response = await asyncio.to_thread(litellm.completion, model=self._model, messages=messages, response_format=Schema)
    raw = response.choices[0].message.content
    result = Schema.model_validate_json(raw)
    logger.info("llm_call_complete", model=self._model, ...)
    return convert(result)
```

このパターンが6ファイル × 1-2メソッドで繰り返されている。

### 推奨

共通の `async def call_llm(model, messages, schema, **log_context)` ヘルパーを adapters 内の共有モジュールに抽出する。各アダプタはプロンプト組み立てと結果変換だけに集中できる。

---

## 11. [Moderate] エラー型の貧弱さ

### 問題

`domain/errors.py` には3つの例外しかない:

```python
class SourceTextTooShort(ValueError): ...
class SourceTextTooLong(ValueError): ...
class InvalidStatusTransition(ValueError): ...
```

一方、サービス層では全て `ValueError` で代用している:

```python
# session_service.py:155
msg = f"Menu not found: {menu_id}"
raise ValueError(msg)

# review_service.py:122
msg = f"Variation not found: {variation_id}"
raise ValueError(msg)
```

「メニューが見つからない」と「バリデーション失敗」は全く異なる性質のエラーだが、呼び出し側で区別できない。

### 推奨

少なくとも以下のドメインエラーを追加する:
- `EntityNotFound` — リポジトリから取得できなかった
- `InvalidStateError` — ビジネスルール上許可されない操作

---

## 12. [Moderate] テストの構造的な課題

### 良い点

- Fakeクラスを一貫して使用し、`unittest.mock` を使っていない点は非常に良い
- ドメインテストは行動仕様として優秀（SRSテストなど）
- pytest-asyncioの使い方が適切
- テスト構造がアーキテクチャ層に対応している

### 課題

1. **ViewModelのprivateロジックがテスト不能**: ドメインに抽出すべきロジックがサービスのprivateメソッドにあるため、それを経由せずにテストできない（上記 Issue 1 と関連）

2. **Coordinator のテストが脆い**: `test_coordinator.py` に15以上のFakeクラスが定義されており、Coordinatorの内部構造への依存度が高い。これは Coordinator 自体の責務が大きすぎることの症状

3. **統合テストが5スライスに限定**: スライス2の統合テストは存在するが、Phase C（オーバーラッピング、本番発話）の統合テストが見当たらない

---

## 13. [Moderate] `skip_to_phase` フラグのコードスメル

### 問題

```python
# container.py:100
self.skip_to_phase: str | None = None

# coordinator.py:210-212
if self._c.skip_to_phase == "c":
    self._c.practice_service.request_model_audio(passage.id)
    self._show_phase_c(passage.id)
    return
```

`Container` にデバッグ/シード用の `skip_to_phase` フラグがあり、Coordinatorが実行時にそれを参照している。これは**テスト・デバッグの仕組みがプロダクションコードに侵入している**例だ。

### 推奨

- Coordinatorに `start_at_phase` パラメータを渡す方式に変更する
- または、テスト用のseederで直接Coordinatorのメソッドを呼ぶ

---

## 14. [Minor] passages の `created_at` が空文字列

### 問題

```python
# sqlite_source_repository.py:70
self._conn.execute(
    """INSERT INTO passages (..., created_at) VALUES (?, ?, ?, ?, ?, ?)""",
    (str(passage.id), ..., ""),  # ← created_at が空文字列
)
```

`Passage` ドメインモデルには `created_at` フィールドがないため、SQLiteカラムに空文字列が入る。スキーマには `created_at TEXT NOT NULL` と定義されているが、値は常に空文字列。

### 推奨

- `Passage` に `created_at` を追加するか、スキーマから `created_at` を削除する
- 中途半端な状態は将来のデバッグを困難にする

---

## 15. [Minor] WPMターゲットに A1/C2 がない

### 問題

```python
# wpm.py:3-8
CEFR_WPM_TARGETS: dict[str, tuple[int, int]] = {
    "A2": (90, 100),
    "B1": (110, 130),
    "B2": (140, 170),
    "C1": (180, 200),
}
```

`CEFRLevel` enumにはA1, A2, B1, B2, C1, C2の6段階が定義されているが、WPMターゲットにはA1とC2がない。`calculate_time_limit()` でA1またはC2のソースを使うとKeyErrorが発生する。

---

## まとめ: 優先度順アクションリスト

| 優先度 | Issue | 推奨アクション |
|--------|-------|---------------|
| **P0** | 1. ドメインロジック流出 | `_map_words_to_sentences`, `_convert_learning_items`, `_select_next_passages` をドメイン関数に移動 |
| **P0** | 2. Container God Object | UIパッケージから移動、publicフィールドの整理 |
| **P0** | 8. ドメインイベントの依存方向 | `Event` 基底クラスをドメイン層に移す |
| **P1** | 3. Coordinator責務過剰 | リポジトリ直接アクセスの排除、データ解決をサービスに移す |
| **P1** | 5. ensure_future乱用 | タスク管理ヘルパーの導入 |
| **P1** | 7. トランザクション管理 | サービス層でのcommit管理に統一 |
| **P2** | 4. 型安全性 | BaseViewModel の handler 型制約を強化 |
| **P2** | 6. PracticeService | 重複コードの括り出し |
| **P2** | 9. datetime.now() | サービスでの時刻注入を徹底 |
| **P2** | 10. Geminiボイラープレート | LLM呼び出しヘルパーの抽出 |
| **P2** | 11. エラー型 | EntityNotFound, InvalidStateError の導入 |
| **P3** | 12. テスト構造 | ドメインロジック移動に伴うテスト追加 |
| **P3** | 13. skip_to_phase | デバッグ用フラグのプロダクションコードからの分離 |
| **P3** | 14. passages created_at | モデルとスキーマの整合 |
| **P3** | 15. WPMターゲット | A1/C2の追加またはバリデーション |

---

## 注記: 良くできている点

批判ばかりになったが、以下は明確に優れている:

- **ドメインの純粋関数群**: `srs.py`, `similarity.py`, `timing.py`, `lag_detection.py`, `wpm.py` — 全て外部依存ゼロで、テスタブルで、ドキュメントとして読める
- **イベント設計の一覧性**: `events.py` 1ファイルに全イベントを集約し、コメントでスライスごとに分類しているのは発見可能性が高い
- **MVVM + BaseViewModelのライフサイクル管理**: activate/deactivateパターンは、EventBusのリーク防止として効果的
- **Fakeベースのテスト戦略**: `unittest.mock` に頼らず、インターフェースに対するFake実装を使う方針はメンテナンス性が高い
- **SRSの完全な設定外部化**: `SRSConfig` で全パラメータを注入可能にしているのは、ドメインロジックを外部に公開する正しいやり方
- **構造化ロギング**: structlog の一貫した使用と、EventBusのemit時自動ロギング
- **ポートの適切な粒度**: 各ポートが「ドメインの要求単位」で切られており、アダプタの内部実装（2段階パイプライン等）がポートに漏れていない
- **テスト数と品質**: 87ファイル、7000行超のテストで、特にSRSテストは仕様書として読める品質
