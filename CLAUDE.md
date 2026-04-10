# Parla

AI駆動の英語スピーキング学習デスクトップアプリ（日本語話者向け）。

## アーキテクチャ

ヘキサゴナルアーキテクチャ（Ports & Adapters）。ドメインは外部に依存しない（UI, LLM, DB を知らない）。

- `docs/architecture/overview.md` — アーキテクチャ方針（設計原則、層構造、イベント駆動、データストレージ等）
- `docs/architecture/implementation-plan.md` — 実装方針（垂直スライス順序、テスト方針、コードが設計になるアプローチ）
- `docs/architecture/error-handling-and-logging.md` — エラーハンドリング・ロギング方針（tenacity、structlog）
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
