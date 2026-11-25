"""Typed errors. Each carries the server's message and the next step to take."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type

ERRORS_DOC = "https://webcite.co/api-docs/errors"
AUTH_DOC = "https://webcite.co/api-docs/authentication"
CREDITS_DOC = "https://webcite.co/api-docs/credits"
KEYS_PAGE = "https://webcite.co/api-keys"

_CREDITS_RE = re.compile(
    r"insufficient credits|credit.balance.exhausted|credit limit exceeded|INSUFFICIENT_CREDITS",
    re.IGNORECASE,
)


class WebciteError(Exception):
    """Base class for every error raised by this package."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        doc_url: Optional[str] = None,
        retry_after: Optional[float] = None,
        next_step: Optional[str] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message if not next_step else f"{message} Next step: {next_step}")
        self.message = message
        self.status = status
        self.code = code
        self.doc_url = doc_url
        self.retry_after = retry_after
        self.next_step = next_step
        self.body = body


class APIError(WebciteError):
    """The API answered with a non-2xx status."""


class BadRequestError(APIError):
    pass


class AuthenticationError(APIError):
    pass


class PermissionDeniedError(APIError):
    pass


class NotFoundError(APIError):
    pass


class ConflictError(APIError):
    pass


class PayloadTooLargeError(APIError):
    pass


class RateLimitError(APIError):
    pass


class InsufficientCreditsError(APIError):
    pass


class ServerError(APIError):
    pass


class WebciteConnectionError(WebciteError):
    """The request did not reach the API or the connection dropped."""


class WebciteTimeoutError(WebciteConnectionError):
    """The client timeout passed before the API answered."""


class IncompleteStreamError(WebciteError):
    """A verification stream ended without a result and a done event."""

    def __init__(self, message: str, events: List[Dict[str, Any]], **kw: Any) -> None:
        super().__init__(message, **kw)
        self.events = events


MISSING_KEY_STEP = (
    f"Pass api_key=... or set WEBCITE_API_KEY. Create a key at {KEYS_PAGE} (sign-in required)."
)

_STEPS: Dict[int, Tuple[Type[APIError], str, str, str]] = {
    401: (
        AuthenticationError,
        "unauthorized",
        AUTH_DOC,
        f"Check the API key. Create one at {KEYS_PAGE} (sign-in required). "
        "A key works only against the environment that issued it.",
    ),
    403: (
        PermissionDeniedError,
        "forbidden",
        AUTH_DOC,
        f"This key may not use this resource (app keys cannot upload or extract). "
        f"Use an account API key from {KEYS_PAGE}.",
    ),
    404: (
        NotFoundError,
        "not_found",
        ERRORS_DOC,
        "Confirm the ID exists and belongs to the account that owns this key.",
    ),
    409: (
        ConflictError,
        "conflict",
        ERRORS_DOC,
        "The Idempotency-Key was used with a different payload. "
        "Resend the original payload, or use a new key for a new request.",
    ),
    413: (
        PayloadTooLargeError,
        "payload_too_large",
        ERRORS_DOC,
        "Reduce the input. Files can be at most 100 MB.",
    ),
}


def _parse_body(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def _server_message(body: Any, status: int) -> str:
    if isinstance(body, dict):
        msg = body.get("message")
        if isinstance(msg, list):
            return "; ".join(str(m) for m in msg)
        if isinstance(msg, str) and msg:
            return msg
    if isinstance(body, str) and body.strip():
        return body.strip()[:500]
    return f"HTTP {status}"


def parse_retry_after(headers: Mapping[str, str], body: Any) -> Optional[float]:
    raw: Any = headers.get("retry-after")
    if raw is None and isinstance(body, dict):
        raw = body.get("retryAfter")
    try:
        return max(0.0, float(raw)) if raw is not None else None
    except (TypeError, ValueError):
        return None


def error_from_response(status: int, headers: Mapping[str, str], text: str) -> APIError:
    body = _parse_body(text)
    message = _server_message(body, status)
    server_code = body.get("error") if isinstance(body, dict) else None
    retry_after = parse_retry_after(headers, body)
    kw: Dict[str, Any] = {"status": status, "body": body, "retry_after": retry_after}
    if status in (400, 402, 429) and _CREDITS_RE.search(text):
        return InsufficientCreditsError(
            message,
            code="insufficient_credits",
            doc_url=CREDITS_DOC,
            next_step="Stop paid calls and keep completed results. Check the balance with "
            "balance(); an account owner can add credits or enable overage where the plan "
            "allows it.",
            **kw,
        )
    if status in _STEPS:
        cls, code, doc, step = _STEPS[status]
        return cls(message, code=code, doc_url=doc, next_step=step, **kw)
    if status == 429:
        wait = f"Wait {retry_after:g} seconds" if retry_after is not None else "Wait"
        return RateLimitError(
            message, code="rate_limited", doc_url=ERRORS_DOC, next_step=f"{wait} and retry.", **kw
        )
    if status >= 500:
        return ServerError(
            message,
            code=str(server_code or "server_error"),
            doc_url=ERRORS_DOC,
            next_step="Inspect saved operation IDs before repeating a paid "
            "call. A verify retry is safe with the same Idempotency-Key.",
            **kw,
        )
    return BadRequestError(
        message,
        code=str(server_code or "bad_request"),
        doc_url=ERRORS_DOC,
        next_step="Check the request fields against the endpoint reference.",
        **kw,
    )
