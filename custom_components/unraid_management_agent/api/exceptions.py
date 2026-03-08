"""Exceptions for the Uma API client."""


class UnraidAPIError(Exception):
    """Base exception for all Unraid API errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class UnraidConnectionError(UnraidAPIError):
    """Exception raised when unable to connect to the Unraid API."""


class UnraidNotFoundError(UnraidAPIError):
    """Exception raised when a resource is not found (404)."""


class UnraidConflictError(UnraidAPIError):
    """Exception raised when there's a resource conflict (409)."""


class UnraidValidationError(UnraidAPIError):
    """Exception raised when request validation fails (400)."""
