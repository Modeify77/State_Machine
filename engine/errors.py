class StateMachineError(Exception):
    """Base exception for state machine errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An internal error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)


class UnauthorizedError(StateMachineError):
    """Missing or invalid authentication token."""

    code = "UNAUTHORIZED"
    status_code = 401
    message = "Missing or invalid authentication token"


class ForbiddenError(StateMachineError):
    """Valid token but not permitted for this action."""

    code = "FORBIDDEN"
    status_code = 403
    message = "Not permitted"


class NotFoundError(StateMachineError):
    """Resource not found."""

    code = "NOT_FOUND"
    status_code = 404
    message = "Resource not found"


class InvalidRequestError(StateMachineError):
    """Malformed request body."""

    code = "INVALID_REQUEST"
    status_code = 400
    message = "Invalid request"


class InvalidActionError(StateMachineError):
    """Action not legal in current state."""

    code = "INVALID_ACTION"
    status_code = 400
    message = "Invalid action"


class AlreadyActedError(StateMachineError):
    """Already submitted action this phase."""

    code = "ALREADY_ACTED"
    status_code = 400
    message = "Already submitted action this phase"


class ConflictError(StateMachineError):
    """Tick mismatch or other conflict."""

    code = "CONFLICT"
    status_code = 409
    message = "Conflict"
