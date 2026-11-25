"""Configuration, headers, retry policy and response handling shared by both clients."""

from __future__ import annotations

import json
import os
import platform
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Union

import httpx

from ._errors import MISSING_KEY_STEP, AuthenticationError, error_from_response
from ._requests import RequestSpec
from ._version import __version__

DEFAULT_BASE_URL = "https://api.webcite.co"
# Extraction keeps the request open while every page is read; the docs use 15 minutes.
DEFAULT_TIMEOUT = httpx.Timeout(900.0, connect=15.0)
DEFAULT_MAX_RETRIES = 2
SURFACE = "sdk-python"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_DELAY = 30.0

TimeoutArg = Union[float, httpx.Timeout, None]


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    timeout: httpx.Timeout
    max_retries: int


def resolve_config(
    api_key: Optional[str], base_url: Optional[str], timeout: TimeoutArg, max_retries: Optional[int]
) -> Config:
    key = api_key or os.environ.get("WEBCITE_API_KEY", "")
    if not key.strip():
        raise AuthenticationError(
            "No Webcite API key was provided.",
            code="missing_api_key",
            doc_url="https://webcite.co/api-docs/authentication",
            next_step=MISSING_KEY_STEP,
        )
    url = (base_url or os.environ.get("WEBCITE_API_URL") or DEFAULT_BASE_URL).rstrip("/")
    resolved_timeout = (
        timeout
        if isinstance(timeout, httpx.Timeout)
        else (DEFAULT_TIMEOUT if timeout is None else httpx.Timeout(timeout))
    )
    retries = DEFAULT_MAX_RETRIES if max_retries is None else max(0, max_retries)
    return Config(key.strip(), url, resolved_timeout, retries)


def default_headers(api_key: str) -> Dict[str, str]:
    return {
        "x-api-key": api_key,
        "x-webcite-surface": SURFACE,
        "User-Agent": f"webcite-python/{__version__} python/{platform.python_version()}",
        "Accept": "application/json",
    }


def request_kwargs(spec: RequestSpec) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if spec.idempotency_key:
        headers["Idempotency-Key"] = spec.idempotency_key
    if spec.stream:
        headers["Accept"] = "text/event-stream"
    kwargs: Dict[str, Any] = {"headers": headers}
    for name in ("json", "params", "files", "data"):
        value = getattr(spec, name)
        if value is not None:
            kwargs[name] = value
    return kwargs


def retry_delay(attempt: int, retry_after: Optional[float]) -> float:
    if retry_after is not None:
        return min(retry_after, MAX_RETRY_DELAY)
    base: float = min(0.5 * float(2**attempt), 8.0)
    return base * (0.75 + random.random() / 2)


def should_retry(spec: RequestSpec, status: Optional[int], attempt: int, max_retries: int) -> bool:
    if attempt >= max_retries or not spec.retryable:
        return False
    return status is None or status in RETRY_STATUSES


def parse_json(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        raise error_from_response(response.status_code, response.headers, response.text)
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise error_from_response(
            502, response.headers, "API response did not contain valid JSON"
        ) from exc


class SSEDecoder:
    """Turns text/event-stream lines into {"event", "data"} dicts."""

    def __init__(self) -> None:
        self._event = "message"
        self._data: List[str] = []

    def feed(self, raw_line: str) -> Optional[Dict[str, Any]]:
        line = raw_line.rstrip("\r")
        if line.startswith("event:"):
            self._event = line[6:].strip()
        elif line.startswith("data:"):
            self._data.append(line[5:][1:] if line[5:6] == " " else line[5:])
        elif line == "" and self._data:
            raw = "\n".join(self._data)
            try:
                data: Any = json.loads(raw)
            except ValueError:
                data = raw
            event = {"event": self._event, "data": data}
            self._event, self._data = "message", []
            return event
        return None


def event_kind(event: Mapping[str, Any]) -> str:
    data = event.get("data")
    if event.get("event") == "message" and isinstance(data, dict):
        return str(data.get("type", "message"))
    return str(event.get("event"))


class StreamTracker:
    """Applies the stream contract: a result and a later done event mean success."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self.has_result = False
        self.done = False

    def add(self, event: Dict[str, Any]) -> Optional[str]:
        """Record an event. Returns a failure reason when the stream reports one."""
        self.events.append(event)
        kind = event_kind(event)
        if kind in ("error", "accounting_error"):
            data = event.get("data")
            detail = data.get("message") if isinstance(data, dict) else None
            return f"Verification stream reported {kind}" + (f": {detail}" if detail else "")
        if kind in ("result", "complete"):
            self.has_result = True
        if kind == "done":
            if not self.has_result:
                return "Stream completion arrived before its result"
            self.done = True
        return None

    def final_failure(self) -> Optional[str]:
        if self.has_result and self.done:
            return None
        return "Verification stream ended without a result and a done event"
