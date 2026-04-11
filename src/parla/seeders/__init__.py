"""State seeders for development and testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parla.container import Container

_REGISTRY: dict[str, str] = {
    "day1": "parla.seeders.day1",
    "day1.short": "parla.seeders.day1_short",
    "day1.start_review": "parla.seeders.day1_start_review",
    "run_through": "parla.seeders.run_through",
}


def apply_state(state: str, container: Container) -> None:
    """Reset DB and seed to the specified state."""
    if state not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise SystemExit(f"Unknown state: {state!r}. Available: {available}")

    import importlib

    module = importlib.import_module(_REGISTRY[state])
    module.seed(container)
