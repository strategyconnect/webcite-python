from __future__ import annotations

import io

import httpx
import pytest

import webcite
from tests.conftest import Recorder, load


def test_verify_sends_documented_request_and_returns_saved_response(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    saved = load("claim-great-wall.json")
    recorder.queue(httpx.Response(201, json=saved))
    claim = "The Great Wall of China is visible from the Moon with the naked eye."
    result = client.verify(claim)
    req = recorder.requests[0]
    assert (req.method, req.url.path) == ("POST", "/api/v1/verify")
    assert str(req.url).startswith("https://api.webcite.co/")
    assert req.headers["x-api-key"] == "test-key"
    assert req.headers["x-webcite-surface"] == "sdk-python"
    assert req.headers["user-agent"].startswith(f"webcite-python/{webcite.__version__} ")
    assert req.headers["idempotency-key"]
    assert recorder.body() == {"claim": claim}
    group = result["claim_groups"][0]
    assert group["verdict"]["result"] == "contradicted"
    assert group["citations"][0]["url"] == "https://www.nasa.gov/image-article/great-wall/"
    assert result["usage"]["credits"] == 4


def test_verify_passes_options_without_inventing_defaults(
    client: webcite.Webcite, recorder: Recorder
) -> None:
    client.verify("x", include_stance=False, source_urls=["https://a.example"], thread_id="t1")
    assert recorder.body() == {
        "claim": "x",
        "include_stance": False,
        "source_urls": ["https://a.example"],
        "thread_id": "t1",
    }


def test_extract_returns_saved_document(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(httpx.Response(201, json=load("doc-bls-table.json")))
    doc = client.extract("asset-1", mode="standard")
    assert recorder.body() == {"asset_id": "asset-1", "mode": "standard"}
    assert recorder.requests[0].url.path == "/api/v1/extract"
    assert doc["state"] == "complete"
    assert "Summary table A" in doc["markdown"]
    assert doc["usage"]["page_charges"][0]["page_type"] == "form"


def test_extract_requires_an_asset(client: webcite.Webcite) -> None:
    with pytest.raises(ValueError, match="asset_id"):
        client.extract()


def test_upload_sends_multipart_file(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(httpx.Response(200, json={"successCode": 200, "data": {"asset_id": "a1"}}))
    out = client.upload(io.BytesIO(b"%PDF-1.4"), filename="report.pdf")
    req = recorder.requests[0]
    assert req.headers["content-type"].startswith("multipart/form-data")
    assert b'filename="report.pdf"' in req.content and b"%PDF-1.4" in req.content
    assert out["data"]["asset_id"] == "a1"


def test_upload_reads_a_path(
    client: webcite.Webcite, recorder: Recorder, tmp_path: pytest.TempPathFactory
) -> None:
    path = tmp_path / "w9.pdf"  # type: ignore[operator]
    path.write_bytes(b"bytes")
    client.upload(str(path))
    assert b'filename="w9.pdf"' in recorder.requests[0].content


def test_search_and_balance(client: webcite.Webcite, recorder: Recorder) -> None:
    recorder.queue(httpx.Response(200, json=load("claim-apple-fy2024.json")))
    recorder.queue(httpx.Response(200, json=load("balance.json")))
    found = client.search("Apple FY2024 net sales", limit=3)
    assert recorder.body(0) == {"query": "Apple FY2024 net sales", "limit": 3}
    assert found["claim_groups"][0]["citations"][0]["url"].startswith("https://www.sec.gov/")
    assert client.balance()["credits"]["remaining"] == 87.5
    assert recorder.requests[1].method == "GET"


def test_env_vars_and_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBCITE_API_KEY", "env-key")
    monkeypatch.setenv("WEBCITE_API_URL", "https://webcite.internal.example/")
    rec = Recorder()
    c = webcite.Webcite(http_client=httpx.Client(transport=httpx.MockTransport(rec)))
    c.accuracy()
    assert str(rec.requests[0].url) == "https://webcite.internal.example/api/v1/accuracy"
    assert rec.requests[0].headers["x-api-key"] == "env-key"


def test_missing_key_names_the_key_page() -> None:
    with pytest.raises(webcite.AuthenticationError) as info:
        webcite.Webcite()
    assert "https://webcite.co/api-keys" in str(info.value)
    assert info.value.code == "missing_api_key"


def test_path_ids_are_encoded(client: webcite.Webcite, recorder: Recorder) -> None:
    client.get_citation("a/b c")
    assert recorder.requests[0].url.raw_path == b"/api/v1/citations/a%2Fb%20c"
