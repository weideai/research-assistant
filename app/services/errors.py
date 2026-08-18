class ServiceError(Exception):
    code = "service_error"

    def __init__(self, message, *, field_errors=None):
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors or {}


class ValidationError(ServiceError):
    code = "validation_error"


class NotFoundError(ServiceError):
    code = "not_found"


class ConflictError(ServiceError):
    code = "row_version_conflict"
