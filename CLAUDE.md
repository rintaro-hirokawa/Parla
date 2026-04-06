# Parla

AI駆動の英語スピーキング学習デスクトップアプリ（日本語話者向け）。

## アーキテクチャ

ヘキサゴナルアーキテクチャ（Ports & Adapters）+ DDD。詳細は `docs/architecture/overview.md` を参照。

```
src/parla/
├── knowledge/       BC1: 素材・学習項目・SRS
├── session/         BC2: セッション進行・フェーズ管理
├── ports/           Port インターフェース（LLM, TTS, Repository）
├── adapters/        Adapter 実装（Gemini, ElevenLabs, SQLite）
└── orchestrator/    LLMコール並列/直列制御
```

- ドメインは外部に依存しない（UI, LLM, DB を知らない）
- `verification/` は技術検証用。`src/parla/` とは独立（import しない）

## コマンド

```bash
uv sync                          # 依存インストール
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run mypy                      # 型チェック
uv run pytest                    # テスト
```

## 要件定義

`docs/requirements/` に全要件が定義済み。実装前に必ず参照すること。

## 技術検証

- 定義: `docs/verification/`
- コード・結果: `verification/`
- `verification/` にはテスト（pytest）、lint、型チェックは不要
