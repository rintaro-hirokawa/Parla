# Parla

AI駆動の英語スピーキング学習デスクトップアプリ（日本語話者向け）。

## アーキテクチャ

ヘキサゴナルアーキテクチャ（Ports & Adapters）。ドメインは外部に依存しない（UI, LLM, DB を知らない）。

## コマンド

```bash
uv sync                          # 依存インストール
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run mypy                      # 型チェック
uv run pytest                    # テスト
```

## 要件定義

`docs/requirements/` に要件が定義済みだが、実態との乖離が大きくなってきたため、今では参照する必要はない。

## 技術検証

- 定義: `docs/verification/`
- コード・結果: `verification/`
- `verification/` にはテスト（pytest）、lint、型チェックは不要
