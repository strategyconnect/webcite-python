from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Union

import httpx
import pytest

import webcite

FIXTURES = Path(__file__).parent / "fixtures"

Handler = Callable[[httpx.Request], httpx.Response]
Reply = Union[httpx.Response, Handler]


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class Recorder:
    """A mock transport that records requests and answers from a queue or a function."""

    def __init__(self) -> None:
        self.requests: List[httpx.Request] = []
        self.replies: List[Reply] = []
        self.default: Reply = httpx.Response(200, json={})

    def queue(self, *replies: Reply) -> None:
        self.replies.extend(replies)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        reply = self.replies.pop(0) if self.replies else self.default
        return reply(request) if callable(reply) else reply

    def body(self, index: int = -1) -> Dict[str, Any]:
        return json.loads(self.requests[index].content)  # type: ignore[no-any-return]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("webcite._client.time.sleep", lambda _s: None)

    async def _fast(_s: float) -> None:
        return None

    monkeypatch.setattr("webcite._async_client.asyncio.sleep", _fast)
    monkeypatch.delenv("WEBCITE_API_KEY", raising=False)
    monkeypatch.delenv("WEBCITE_API_URL", raising=False)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def client(recorder: Recorder) -> webcite.Webcite:
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    return webcite.Webcite("test-key", http_client=http)


@pytest.fixture
def aclient(recorder: Recorder) -> webcite.AsyncWebcite:
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    return webcite.AsyncWebcite("test-key", http_client=http)
