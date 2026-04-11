"""Base class for domain events."""

from pydantic import BaseModel


class Event(BaseModel, frozen=True):
    """Base class for all domain events. Immutable value objects."""
