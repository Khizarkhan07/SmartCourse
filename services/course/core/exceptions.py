class DomainException(Exception):
    pass

class NotFoundError(DomainException):
    pass

class PermissionDeniedError(DomainException):
    pass

class ValidationError(DomainException):
    pass
