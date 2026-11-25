from __future__ import annotations

import httpx
import pytest

import webcite
from tests.conftest import Recorder

UNAUTH = {
    "message": "Authentication required. Please provide a valid Bearer token, API key, or bot key.",
    "error": "Unauthorized",
    "statusCode": 401,
}


def test_401_carries_server_message_and_key_page(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    recorder.queue(httpx.Response(401, json=UNAUTH))
    with pytest.raises(webcite.AuthenticationError) as info:
        client.list_citations()
    err = info.value
    assert err.status == 401 and err.message == UNAUTH["message"]
    assert err.next_step and "https://webcite.co/api-keys" in err.next_step
    assert err.doc_url == "https://webcite.co/api-docs/authentication"
    assert len(recorder.requests) == 1


def test_insufficient_credits_is_typed(client: webcite.Webcite, recorder: Recorder) -> None:
    msg = "Insufficient credits. Required: 3, Available: 1"
    recorder.queue(httpx.Response(400, json={"message": msg, "statusCode": 400}))
    with pytest.raises(webcite.InsufficientCreditsError) as info:
        client.extract("a1")
    assert info.value.message == msg and info.value.code == "insufficient_credits"


def test_get_is_retried_on_503_then_succeeds(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(
        httpx.Response(503, json={"message": "busy"}), httpx.Response(200, json={"a": 1})
    )
    assert client.accuracy() == {"a": 1}
    assert len(recorder.requests) == 2


def test_verify_retry_reuses_its_idempotency_key(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    recorder.queue(
        httpx.Response(429, headers={"Retry-After": "1"}, json={"message": "slow down"}),
        httpx.Response(200, json={"claim_groups": []}),
    )
    client.verify("x")
    keys = {r.headers["idempotency-key"] for r in recorder.requests}
    assert len(recorder.requests) == 2 and len(keys) == 1


def test_paid_post_without_key_is_never_repeated(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    recorder.queue(httpx.Response(502, json={"message": "storage failed"}))
    with pytest.raises(webcite.ServerError) as info:
        client.extract("a1")
    assert len(recorder.requests) == 1
    assert info.value.message == "storage failed"


def test_retries_stop_at_the_budget(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.default = httpx.Response(429, headers={"Retry-After": "2"}, json={"retryAfter": 2})
    with pytest.raises(webcite.RateLimitError) as info:
        client.accuracy()
    assert len(recorder.requests) == 3
    assert info.value.retry_after == 2.0 and "Wait 2 seconds" in str(info.value)


def test_timeout_on_extract_is_not_retried_and_explains(recorder: Recorder) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    recorder.default = boom
    c = webcite.Webcite("k", http_client=httpx.Client(transport=httpx.MockTransport(recorder)))
    with pytest.raises(webcite.WebciteTimeoutError, match="may still have completed"):
        c.extract("a1")
    assert len(recorder.requests) == 1


def test_default_timeout_allows_long_extractions() -> None:
    c = webcite.Webcite("k")
    assert c._config.timeout.read == 900.0
