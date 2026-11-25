"""Python SDK for the Webcite API: parse documents, verify claims and bind citations to quotes."""

from ._async_client import AsyncWebcite
from ._client import Webcite
from ._errors import (
    APIError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    IncompleteStreamError,
    InsufficientCreditsError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    WebciteConnectionError,
    WebciteError,
    WebciteTimeoutError,
)
from ._version import __version__

__all__ = [
    "APIError",
    "AsyncWebcite",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "IncompleteStreamError",
    "InsufficientCreditsError",
    "NotFoundError",
    "PayloadTooLargeError",
    "PermissionDeniedError",
    "RateLimitError",
    "ServerError",
    "Webcite",
    "WebciteConnectionError",
    "WebciteError",
    "WebciteTimeoutError",
    "__version__",
]
