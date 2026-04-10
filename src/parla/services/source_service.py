"""Source registration and passage generation orchestration."""

import structlog

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    PassageGenerationStarted,
    SourceRegistered,
)
from parla.domain.source import CEFRLevel, EnglishVariant, Source
from parla.event_bus import EventBus
from parla.ports.passage_generation import PassageGenerationPort
from parla.ports.source_repository import SourceRepository

logger = structlog.get_logger()


class SourceService:
    """Orchestrates source registration and passage generation."""

    def __init__(
        self,
        event_bus: EventBus,
        source_repo: SourceRepository,
        passage_generator: PassageGenerationPort,
    ) -> None:
        self._bus = event_bus
        self._repo = source_repo
        self._generator = passage_generator

    def register_source(
        self,
        text: str,
        cefr_level: CEFRLevel,
        english_variant: EnglishVariant,
        title: str = "",
    ) -> Source:
        """Register a new source and emit SourceRegistered."""
        source = Source(
            text=text,
            title=title,
            cefr_level=cefr_level,
            english_variant=english_variant,
        )
        self._repo.save_source(source)
        self._bus.emit(SourceRegistered(source_id=source.id))
        return source

    async def handle_source_registered(self, event: SourceRegistered) -> None:
        """Handle SourceRegistered: generate passages via LLM."""
        source = self._repo.get_source(event.source_id)
        if source is None:
            logger.error("source_not_found", source_id=str(event.source_id))
            return

        source = source.start_generating()
        self._repo.update_source(source)
        self._bus.emit(PassageGenerationStarted(source_id=source.id))

        try:
            passages = await self._generator.generate(
                source_id=source.id,
                source_text=source.text,
                cefr_level=source.cefr_level,
                english_variant=source.english_variant,
            )
            self._repo.save_passages(passages)

            source = source.complete_generation()
            self._repo.update_source(source)

            total_sentences = sum(len(p.sentences) for p in passages)
            self._bus.emit(
                PassageGenerationCompleted(
                    source_id=source.id,
                    passage_count=len(passages),
                    total_sentences=total_sentences,
                )
            )
        except Exception as exc:
            logger.exception("passage_generation_failed", source_id=str(source.id))
            source = source.fail_generation()
            self._repo.update_source(source)
            self._bus.emit(
                PassageGenerationFailed(
                    source_id=source.id,
                    error_message=str(exc),
                )
            )
