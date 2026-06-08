"""
Domain exceptions — raised by service layer, translated to HTTP by handlers.
Services should NOT import from fastapi or know about HTTP.
"""


class DomainException(Exception):
    """Base exception for all domain exceptions."""
    pass


class NotFoundError(DomainException):
    """Resource not found."""
    pass


class ConflictError(DomainException):
    """Resource already exists or operation would create a conflict."""
    pass


class ValidationError(DomainException):
    """Invalid data or state."""
    pass


class PermissionDeniedError(DomainException):
    """User lacks required permissions."""
    pass


class InvalidStateError(DomainException):
    """Operation not allowed in current state."""
    pass
