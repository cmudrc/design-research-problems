"""Package-specific exceptions."""

from __future__ import annotations


class MissingOptionalDependencyError(ImportError):
    """Raised when a caller uses an optional integration that is not installed."""


class ProblemEvaluationError(RuntimeError):
    """Raised when a problem definition is internally inconsistent."""
