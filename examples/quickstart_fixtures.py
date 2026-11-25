"""Runs the README quickstarts against the saved responses, with no network access.

Usage: python examples/quickstart_fixtures.py tests/fixtures
"""

import json
import sys
from pathlib import Path

import httpx

from webcite import Webcite

FIXTURES = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures")
ROUTES = {
    "/api/v1/verify": "claim-great-wall.json",
    "/api/v1/upload": None,
    "/api/v1/extract": "doc-irs-w9.json",
}


def answer(request: httpx.Request) -> httpx.Response:
    name = ROUTES[request.url.path]
    if name is None:
        return httpx.Response(200, json={"successCode": 200, "data": {"asset_id": "a1"}})
    return httpx.Response(201, json=json.loads((FIXTURES / name).read_text()))


client = Webcite("fixture-key", http_client=httpx.Client(transport=httpx.MockTransport(answer)))

result = client.verify("The Great Wall of China is visible from the Moon with the naked eye.")
group = result["claim_groups"][0]
print(group["verdict"]["result"], result["usage"]["credits"])
for citation in group["citations"][:1]:
    print(citation["stance"], citation["url"])

asset = client.upload(b"%PDF", filename="irs-form-w9-page-1.pdf")["data"]
doc = client.extract(asset["asset_id"])
print(doc["state"], doc["usage"]["credits"])
print(doc["markdown"].splitlines()[0])
