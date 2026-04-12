"""Custom exception classes for the decision-time application."""


class DecisionTimeError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DecisionTimeError):
    """Entity not found. Maps to HTTP 404."""


class ValidationError(DecisionTimeError):
    """Invalid input or business rule violation. Maps to HTTP 422."""


class InvalidStateError(DecisionTimeError):
    """Wrong lifecycle state for the requested operation. Maps to HTTP 409."""


class ConflictError(DecisionTimeError):
    """Optimistic concurrency version mismatch. Maps to HTTP 409."""
