"""Source list and progress query service."""

from parla.domain.source import CEFRLevel, Source, SourceStatus
from parla.ports.practice_repository import PracticeRepository
from parla.ports.source_repository import SourceRepository
from parla.services.query_models import SourceSummary


class SourceQueryService:
    """Read-only service for source list and progress display."""

    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        practice_repo: PracticeRepository,
    ) -> None:
        self._source_repo = source_repo
        self._practice_repo = practice_repo

    def list_sources(
        self,
        *,
        status: SourceStatus | None = None,
        cefr_level: CEFRLevel | None = None,
    ) -> tuple[SourceSummary, ...]:
        """List all sources with progress info, optionally filtered."""
        sources = self._source_repo.get_all_sources()

        if status is not None:
            sources = [s for s in sources if s.status == status]
        if cefr_level is not None:
            sources = [s for s in sources if s.cefr_level == cefr_level]

        return tuple(self._to_summary(s) for s in sources)

    def list_active_sources(self) -> tuple[SourceSummary, ...]:
        """List sources with status not_started or in_progress."""
        sources = self._source_repo.get_active_sources()
        return tuple(self._to_summary(s) for s in sources)

    def _to_summary(self, source: Source) -> SourceSummary:
        passages = self._source_repo.get_passages_by_source(source.id)
        learned = sum(1 for p in passages if self._practice_repo.has_achievement(p.id))
        return SourceSummary(
            id=source.id,
            title=source.title,
            cefr_level=source.cefr_level,
            english_variant=source.english_variant,
            status=source.status,
            passage_count=len(passages),
            learned_passage_count=learned,
            created_at=source.created_at,
        )
