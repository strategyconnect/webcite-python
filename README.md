# Webcite Python SDK

Webcite is an API for document parsing and claim verification. It reads PDFs, scans,
spreadsheets and office files into Markdown with per-page provenance, checks claims against
web sources or your own documents, and returns citations bound to the quotes that support or
contradict them. On ParseBench 2, Webcite extraction scored 91.74 overall (ranking pending
approval by LlamaIndex). This package is the official Python client for the
[Webcite API](https://webcite.co/api-docs).

<!-- Switch back to "pip install webcite" once it is published on PyPI. -->
```bash
pip install "git+https://github.com/strategyconnect/webcite-python.git@v0.1.0"
```

Python 3.9 or newer. The only dependency is `httpx`.

## First call

```python
from webcite import Webcite

client = Webcite()  # reads WEBCITE_API_KEY
result = client.verify("The Great Wall of China is visible from the Moon with the naked eye.")
group = result["claim_groups"][0]
print(group["verdict"]["result"], result["usage"]["credits"])
for citation in group["citations"][:1]:
    print(citation["stance"], citation["url"])
```

Recorded output (from the saved response at
[webcite.co/samples/claim-great-wall.json](https://webcite.co/samples/claim-great-wall.json),
recorded from the API on 24 November 2026):

```text
contradicted 4
contradicts https://www.nasa.gov/image-article/great-wall/
```

A verification costs 4 credits with the default stance and verdict. The Free plan includes
100 credits.

## Parse a document

```python
from webcite import Webcite

client = Webcite()
asset = client.upload("irs-form-w9-page-1.pdf")["data"]
doc = client.extract(asset["asset_id"])
print(doc["state"], doc["usage"]["credits"])
print(doc["markdown"].splitlines()[0])
```

Recorded output (saved response at
[webcite.co/samples/doc-irs-w9.json](https://webcite.co/samples/doc-irs-w9.json)):

```text
complete 0.4966
Form **W-9**
```

Uploading is free. Extraction is charged per page at cost. Check `state` before using
`markdown`: `complete: false` and `lost` name parts that were not recovered. The request stays
open until every page is read; there is no job to poll. `extract_pages()` returns anchored
chunks for indexing and `extract_figures()` returns every recognised number with its source.

## Check quotes against sources

```python
sec = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"
results = client.verify_batch([
    {"id": "q1", "quote": "Total net sales 391,035", "url": sec},
    {"id": "q2", "quote": "Revenue was $12 million.", "asset_id": asset["asset_id"], "page": 1},
])
for item in results:
    print(item)
```

## Search sources and preview evidence

```python
found = client.search("Apple total net sales fiscal 2024", limit=5)
preview = client.source_preview(url=found["citations"][0]["url"], quote="Total net sales")
```

## Stream a verification

```python
for event in client.verify_stream("The Eiffel Tower is 330 meters tall"):
    print(event["data"].get("type"))
```

The iterator raises `IncompleteStreamError` (with the events received so far) if the stream
ends without a `result` and a later `done` event, or reports `error`.

## Ask a question over a document

```python
job = client.ask("What was revenue in FY2025?", doc["markdown"])
answer = client.wait_for_ask(job["id"])  # polls GET /api/v1/ask/{id}
print(answer["status"])
```

`wait_for_ask` stops on `done` or `failed`. After `max_wait` seconds (600 by default) it returns
the latest job view instead of raising, so you can keep polling.

## Credits

```python
print(client.balance()["credits"]["remaining"])  # free
```

## Async

```python
import asyncio
from webcite import AsyncWebcite

async def main() -> None:
    async with AsyncWebcite() as client:
        result = await client.verify("The Eiffel Tower is 330 meters tall")
        print(result["claim_groups"][0]["verdict"]["result"])

asyncio.run(main())
```

Every method on `Webcite` exists on `AsyncWebcite`.

## Authentication

Create a key on the [API Keys page](https://webcite.co/api-keys) (sign-in required) and set it
as `WEBCITE_API_KEY`, or pass `Webcite(api_key=...)`. The key is sent in the `x-api-key`
header. Keep it on your server; never put it in frontend code, a public repository or a chat
with an AI agent. The `webcite` command line tool in the
[TypeScript package](https://github.com/strategyconnect/webcite-js) can store a key with
`webcite login`.

## Self-hosted deployments

Set `WEBCITE_API_URL` or pass `base_url`:

```python
client = Webcite(base_url="https://webcite.internal.example.com")
```

The default is `https://api.webcite.co`. A key works only against the environment that issued it.

## Errors

Every error is a `webcite.WebciteError` with `status`, `code`, `message` (the server's text),
`next_step`, `doc_url` and `retry_after`.

| Error | When |
| --- | --- |
| `AuthenticationError` | 401, or no key. `next_step` points to the API keys page. |
| `PermissionDeniedError` | 403. App keys cannot upload or extract. |
| `NotFoundError` | 404. The ID does not belong to this account. |
| `ConflictError` | 409. An Idempotency-Key was reused with a different payload. |
| `InsufficientCreditsError` | The balance is below the cost. Nothing was charged. |
| `RateLimitError` | 429. `retry_after` is in seconds. |
| `ServerError` | 5xx. |
| `WebciteTimeoutError`, `WebciteConnectionError` | The request did not complete. |
| `IncompleteStreamError` | A stream ended without a result and `done`. |

```python
import webcite

try:
    client.verify("...")
except webcite.InsufficientCreditsError as err:
    print(err.message, err.next_step)
```

## Retries and timeouts

GET requests and `verify()` are retried up to twice on 429 and 5xx, with backoff that honours
`Retry-After`. `verify()` sends an `Idempotency-Key`, so a retry is not charged twice. Other
paid calls (extraction, batch, upload) are never repeated automatically; a timeout does not
prove the server did no work. The default timeout is 15 minutes, matching the extraction docs;
pass `timeout=` (seconds or an `httpx.Timeout`) and `max_retries=` to change them.

The SDK sends no telemetry. Each request carries `x-webcite-surface: sdk-python` and a
`webcite-python/<version>` user agent, which Webcite stores as labels only.

## Use with agent frameworks

Short runnable examples are in [`examples/frameworks/`](examples/frameworks):

| Framework | File | How it connects |
|---|---|---|
| LangChain | `langchain_agent.py` | [`langchain-webcite`](https://github.com/strategyconnect/langchain-webcite) tools and retriever |
| Haystack | `haystack_pipeline.py` | [`webcite-haystack`](https://github.com/strategyconnect/webcite-haystack) components |
| CrewAI | `crewai_mcp.py` | Hosted MCP server |
| Google ADK | `google_adk_mcp.py` | Hosted MCP server through `McpToolset` |
| OpenAI Agents SDK | `openai_agents_mcp.py` | Hosted MCP server through `MCPServerStreamableHttp` |
| Pydantic AI | `pydantic_ai_mcp.py` | Hosted MCP server through `MCPToolset` |

The MCP examples list the Webcite tools without calling a model when run with no arguments.

## Links

- API documentation: https://webcite.co/api-docs (each page has a Markdown copy)
- OpenAPI: https://api.webcite.co/api/v1/openapi.json
- Errors and rate limits: https://webcite.co/api-docs/errors
- MCP server for AI agents: https://webcite.co/api-docs/mcp
- TypeScript SDK and CLI: https://github.com/strategyconnect/webcite-js

## Development

```bash
make install
make check   # ruff, mypy --strict, pytest; no network calls
```

MIT licensed.
