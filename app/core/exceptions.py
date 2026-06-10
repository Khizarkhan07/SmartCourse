"""Domain exceptions raised by services and mapped to HTTP in API handlers."""


class DomainException(Exception):
    """Base exception for all domain exceptions."""


class NotFoundError(DomainException):
    """Resource not found."""


class ConflictError(DomainException):
    """Resource already exists or operation would create a conflict."""


class ValidationError(DomainException):
    """Invalid data or state."""


class PermissionDeniedError(DomainException):
    """User lacks required permissions."""


class InvalidStateError(DomainException):
    """Operation not allowed in current state."""
