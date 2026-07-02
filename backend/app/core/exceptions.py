class AppError(Exception):
    """Base for domain errors mapped to a structured JSON response by main.py's exception handler."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
