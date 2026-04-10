"""Domain-specific exceptions."""


class SourceTextTooShort(ValueError):
    """Source text is shorter than the minimum required length."""


class SourceTextTooLong(ValueError):
    """Source text exceeds the maximum allowed length."""


class InvalidStatusTransition(ValueError):
    """Attempted an invalid status transition."""
