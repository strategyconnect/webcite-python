from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import httpx
import pytest

import webcite
from tests.conftest import Recorder, load


def sse(*frames: Dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)


def test_stream_yields_events_and_completes(client: webcite.Webcite, recorder: Recorder) -> None:
    result = load("claim-great-wall.json")
    recorder.queue(
        sse(
            {"type": "progress"},
            {"type": "result", "data": result},
            {"type": "usage", "credits": 4},
            {"type": "done"},
        )
    )
    events = list(client.verify_stream("claim"))
    assert [e["data"]["type"] for e in events] == ["progress", "result", "usage", "done"]
    req = recorder.requests[0]
    assert req.url.path == "/api/v1/verify/stream"
    assert req.headers["accept"] == "text/event-stream"


def test_stream_without_done_raises_with_partial_events(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    recorder.queue(sse({"type": "progress"}, {"type": "result", "data": {}}))
    seen: List[Any] = []
    with pytest.raises(webcite.IncompleteStreamError) as info:
        for event in client.verify_stream("claim"):
            seen.append(event)
    assert len(seen) == 2 and len(info.value.events) == 2


def test_stream_error_event_raises(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(sse({"type": "error", "message": "Insufficient credits"}))
    with pytest.raises(webcite.IncompleteStreamError, match="Insufficient credits"):
        list(client.verify_stream("claim"))


def test_wait_for_ask_polls_until_done(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(
        httpx.Response(202, json={"id": "j1", "status": "queued"}),
        httpx.Response(200, json={"id": "j1", "status": "running"}),
        httpx.Response(200, json={"id": "j1", "status": "done", "result": {"answer": "12"}}),
    )
    job = client.ask("What was revenue?", "Revenue was $12 million.")
    assert recorder.body(0) == {
        "question": "What was revenue?",
        "documentText": "Revenue was $12 million.",
    }
    final = client.wait_for_ask(job["id"], poll_interval=0)
    assert final["status"] == "done"
    assert [r.url.path for r in recorder.requests[1:]] == ["/api/v1/ask/j1"] * 2


def test_wait_for_ask_returns_latest_view_after_max_wait(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    recorder.default = httpx.Response(200, json={"id": "j1", "status": "running"})
    assert client.wait_for_ask("j1", poll_interval=0, max_wait=0)["status"] == "running"


def test_async_client_matches_sync(aclient: webcite.AsyncWebcite, recorder: Recorder) -> None:
    recorder.queue(
        httpx.Response(201, json=load("claim-great-wall.json")),
        sse({"type": "result", "data": {}}, {"type": "done"}),
        httpx.Response(401, json={"message": "no", "statusCode": 401}),
    )

    async def run() -> None:
        out = await aclient.verify("claim")
        assert out["claim_groups"][0]["stance_summary"] == "contradicted"
        events = [e async for e in aclient.verify_stream("claim")]
        assert len(events) == 2
        with pytest.raises(webcite.AuthenticationError):
            await aclient.balance()
        await aclient.close()

    asyncio.run(run())
    assert recorder.requests[0].headers["x-webcite-surface"] == "sdk-python"
