"""State seeders for development and testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parla.ui.container import Container

_REGISTRY: dict[str, str] = {
    "day1": "parla.seeders.day1",
}


def apply_state(state: str, container: Container) -> None:
    """Reset DB and seed to the specified state."""
    if state not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise SystemExit(f"Unknown state: {state!r}. Available: {available}")

    import importlib

    module = importlib.import_module(_REGISTRY[state])
    module.seed(container)
