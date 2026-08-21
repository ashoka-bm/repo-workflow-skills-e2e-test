import logging


LOGGER = logging.getLogger(__name__)

ERROR_STATUSES = {
    "validation": 400,
    "missing": 404,
    "conflict": 409,
    "authorization": 403,
    "internal": 500,
}


class ApiError(Exception):
    def __init__(self, category: str, message: str) -> None:
        if category not in ERROR_STATUSES:
            raise ValueError(f"unknown API error category: {category}")
        super().__init__(message)
        self.category = category
        self.public_message = message


def error_response(
    error: Exception, correlation_id: str
) -> tuple[int, dict[str, object]]:
    if isinstance(error, ApiError):
        category = error.category
        message = error.public_message
    else:
        category = "internal"
        message = "Internal server error"
        LOGGER.error(
            "Unhandled API error correlation_id=%s",
            correlation_id,
            exc_info=(type(error), error, error.__traceback__),
        )
    return (
        ERROR_STATUSES[category],
        {
            "error": {
                "correlation_id": correlation_id,
                "message": message,
                "type": category,
            }
        },
    )
