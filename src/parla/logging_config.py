"""Structured logging configuration with JSONL file output.

Architecture overview 9章に準拠:
- JSONL（1行1イベント）で grep/jq フィルタ可能
- EventBus の emit/handler 実行、LLM コール、一般ログの3種
- コンソール（stderr）にも人間可読形式で出力（開発時用）
"""

import logging
import sys
from pathlib import Path

import structlog


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging(log_dir: Path = Path("data/logs")) -> None:
    """Configure structlog to output JSONL files and human-readable stderr."""
    _ensure_dir(log_dir)

    # --- stdlib logging handlers (structlog renders, stdlib routes) ---

    jsonl_formatter = logging.Formatter("%(message)s")

    # events.jsonl — イベントトレース
    events_handler = logging.FileHandler(log_dir / "events.jsonl", encoding="utf-8")
    events_handler.setFormatter(jsonl_formatter)

    events_logger = logging.getLogger("parla.events")
    events_logger.handlers.clear()
    events_logger.addHandler(events_handler)
    events_logger.setLevel(logging.DEBUG)
    events_logger.propagate = False

    # llm_calls.jsonl — LLM コールログ
    llm_handler = logging.FileHandler(log_dir / "llm_calls.jsonl", encoding="utf-8")
    llm_handler.setFormatter(jsonl_formatter)

    llm_logger = logging.getLogger("parla.llm")
    llm_logger.handlers.clear()
    llm_logger.addHandler(llm_handler)
    llm_logger.setLevel(logging.DEBUG)
    llm_logger.propagate = False

    # app.jsonl — 一般アプリケーションログ（+ stderr 出力）
    app_file_handler = logging.FileHandler(log_dir / "app.jsonl", encoding="utf-8")
    app_file_handler.setFormatter(jsonl_formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(message)s"))

    app_logger = logging.getLogger("parla")
    app_logger.handlers.clear()
    app_logger.addHandler(app_file_handler)
    app_logger.addHandler(stderr_handler)
    app_logger.setLevel(logging.DEBUG)
    app_logger.propagate = False

    # --- structlog configuration ---

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )
