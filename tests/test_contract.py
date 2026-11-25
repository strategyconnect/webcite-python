"""Every request the SDK can send must match a path and method in the public OpenAPI.

The one exception is the credit balance route: it accepts an API key and backs the MCP
server's get_credit_balance tool, but it is not in the OpenAPI document.
"""

from __future__ import annotations

import re
from typing import Callable, List, Set, Tuple

import httpx

import webcite
from tests.conftest import Recorder, load

NOT_IN_OPENAPI = {("GET", "/api/v1/payment/credits/balance")}


def openapi_operations() -> Set[Tuple[str, str]]:
    spec = load("openapi.json")
    return {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops}


def template_regex(path: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", path) + "$")


def every_call(c: webcite.Webcite) -> List[Callable[[], object]]:
    return [
        lambda: c.verify("c"),
        lambda: list(c.verify_stream("c")),
        lambda: c.verify_batch([{"quote": "q", "url": "https://a.example"}]),
        lambda: c.verify_feedback("t", "correct"),
        lambda: c.verify_numeric({"claim": "2+2=4"}),
        lambda: c.search("q"),
        lambda: c.list_citations(page=1),
        lambda: c.get_citation("id1"),
        lambda: c.source_preview(url="https://a.example"),
        lambda: c.upload(b"x", filename="a.pdf"),
        lambda: c.upload_url("https://a.example/a.pdf"),
        lambda: c.extract("a"),
        lambda: c.extract_visual_rendition("a"),
        lambda: c.extract_pages("a"),
        lambda: c.extract_figures("a"),
        lambda: c.classify("a"),
        lambda: c.gaps("saas", [{"name": "deck"}]),
        lambda: c.ask("q", "text"),
        lambda: c.get_ask("j1"),
        lambda: c.analyze_conflicts([{"value": 1}]),
        lambda: c.analyze_document("a"),
        lambda: c.accuracy(),
        lambda: c.balance(),
        lambda: c.register_source("a", b"x", filename="a.pdf"),
        lambda: c.publish_text_representation("v1"),
        lambda: c.latest_representation("v1"),
        lambda: c.source_unit("v1", "r1", "u1"),
        lambda: c.prepare_ocr_rescue("v1", "r1"),
    ]


def sent_operations() -> List[Tuple[str, str]]:
    rec = Recorder()

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stream"):
            body = 'data: {"type":"result","data":{}}\n\ndata: {"type":"done"}\n\n'
            return httpx.Response(200, content=body)
        return httpx.Response(200, json={"status": "done"})

    rec.default = reply
    c = webcite.Webcite("k", http_client=httpx.Client(transport=httpx.MockTransport(rec)))
    for call in every_call(c):
        call()
    return [(r.method, r.url.path) for r in rec.requests]


def test_every_sdk_request_is_in_the_public_openapi() -> None:
    ops = openapi_operations()
    patterns = [(m, template_regex(p)) for m, p in ops]
    for method, path in sent_operations():
        if (method, path) in NOT_IN_OPENAPI:
            continue
        assert any(m == method and rx.match(path) for m, rx in patterns), (method, path)


def test_every_public_openapi_operation_has_an_sdk_method() -> None:
    sent = sent_operations()
    for method, template in openapi_operations():
        rx = template_regex(template)
        assert any(m == method and rx.match(p) for m, p in sent), (method, template)


def test_contract_check_detects_an_unknown_path() -> None:
    # Positive control: a path the API does not document must fail the match.
    patterns = [(m, template_regex(p)) for m, p in openapi_operations()]
    assert not any(m == "POST" and rx.match("/api/v1/review") for m, rx in patterns)
