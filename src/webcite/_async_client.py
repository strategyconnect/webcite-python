"""Asynchronous client. Same methods as Webcite, awaited."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, List, Mapping, Optional, Sequence, cast

import httpx

from . import _requests as R
from ._base import (
    SSEDecoder,
    StreamTracker,
    TimeoutArg,
    default_headers,
    parse_json,
    request_kwargs,
    resolve_config,
    retry_delay,
    should_retry,
)
from ._errors import (
    IncompleteStreamError,
    WebciteConnectionError,
    WebciteTimeoutError,
    error_from_response,
)
from .types import (
    AskJob,
    Balance,
    CitationList,
    ExtractResponse,
    JSONObject,
    StreamEvent,
    UploadResponse,
    VerifyResponse,
)


class AsyncWebcite:
    """Async client for the Webcite API.

    ``api_key`` defaults to ``WEBCITE_API_KEY``; ``base_url`` defaults to ``WEBCITE_API_URL`` or
    https://api.webcite.co. GET requests and verifications (sent with an Idempotency-Key) are
    retried on 429 and 5xx; other calls are never repeated automatically.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutArg = None,
        max_retries: Optional[int] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = resolve_config(api_key, base_url, timeout, max_retries)
        self._http = http_client or httpx.AsyncClient()
        self._owns_http = http_client is None

    @property
    def base_url(self) -> str:
        return self._config.base_url

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncWebcite:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # -- transport ---------------------------------------------------------------------------

    def _build(self, spec: R.RequestSpec) -> httpx.Request:
        kwargs = request_kwargs(spec)
        headers = {**default_headers(self._config.api_key), **kwargs.pop("headers")}
        return self._http.build_request(
            spec.method,
            self._config.base_url + spec.path,
            headers=headers,
            timeout=self._config.timeout,
            **kwargs,
        )

    async def _send_raw(self, spec: R.RequestSpec, stream: bool = False) -> httpx.Response:
        attempt = 0
        while True:
            status: Optional[int] = None
            wait_hint: Optional[float] = None
            try:
                response = await self._http.send(self._build(spec), stream=stream)
                if response.status_code < 400:
                    return response
                if stream:
                    await response.aread()
                status = response.status_code
                error = error_from_response(status, response.headers, response.text)
                wait_hint = error.retry_after
                if not should_retry(spec, status, attempt, self._config.max_retries):
                    raise error
            except httpx.TimeoutException as exc:
                if not should_retry(spec, None, attempt, self._config.max_retries):
                    raise WebciteTimeoutError(_timeout_message(spec)) from exc
            except httpx.TransportError as exc:
                if not should_retry(spec, None, attempt, self._config.max_retries):
                    raise WebciteConnectionError(f"Could not reach {self.base_url}: {exc}") from exc
            await asyncio.sleep(retry_delay(attempt, wait_hint))
            attempt += 1

    async def _send(self, spec: R.RequestSpec) -> Any:
        return parse_json(await self._send_raw(spec))

    async def _stream(self, spec: R.RequestSpec) -> AsyncIterator[StreamEvent]:
        response = await self._send_raw(spec, stream=True)
        tracker, decoder = StreamTracker(), SSEDecoder()
        try:
            async for line in response.aiter_lines():
                event = decoder.feed(line)
                if event is None:
                    continue
                failure = tracker.add(event)
                yield cast(StreamEvent, event)
                if failure:
                    raise IncompleteStreamError(failure, tracker.events)
        except httpx.HTTPError as exc:
            raise IncompleteStreamError(
                f"Verification stream disconnected: {exc}", tracker.events
            ) from exc
        finally:
            await response.aclose()
        reason = tracker.final_failure()
        if reason:
            raise IncompleteStreamError(reason, tracker.events)

    # -- verification ------------------------------------------------------------------------

    async def verify(
        self,
        claim: str,
        *,
        source_urls: Optional[Sequence[str]] = None,
        filters: Optional[Mapping[str, Any]] = None,
        thread_id: Optional[str] = None,
        include_stance: Optional[bool] = None,
        include_verdict: Optional[bool] = None,
        decompose_claim: Optional[bool] = None,
        include_numeric_assess: Optional[bool] = None,
        include_source_reads: Optional[bool] = None,
        evidence_scope: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> VerifyResponse:
        """Verify one claim against web sources (POST /api/v1/verify). 4 credits by default."""
        return cast(
            VerifyResponse,
            await self._send(
                R.verify(
                    claim,
                    source_urls=source_urls,
                    filters=filters,
                    thread_id=thread_id,
                    include_stance=include_stance,
                    include_verdict=include_verdict,
                    decompose_claim=decompose_claim,
                    include_numeric_assess=include_numeric_assess,
                    include_source_reads=include_source_reads,
                    evidence_scope=evidence_scope,
                    idempotency_key=idempotency_key,
                )
            ),
        )

    def verify_stream(
        self,
        claim: str,
        *,
        source_urls: Optional[Sequence[str]] = None,
        filters: Optional[Mapping[str, Any]] = None,
        thread_id: Optional[str] = None,
        include_stance: Optional[bool] = None,
        include_verdict: Optional[bool] = None,
        decompose_claim: Optional[bool] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream verification events. Raises IncompleteStreamError without result and done."""
        return self._stream(
            R.verify(
                claim,
                source_urls=source_urls,
                filters=filters,
                thread_id=thread_id,
                include_stance=include_stance,
                include_verdict=include_verdict,
                decompose_claim=decompose_claim,
                stream=True,
            )
        )

    async def verify_batch(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        evidence_scope: Optional[Mapping[str, Any]] = None,
    ) -> List[JSONObject]:
        """Check quotes against their sources in one call (POST /api/v1/verify/batch)."""
        return cast(
            List[JSONObject], await self._send(R.verify_batch(items, evidence_scope=evidence_scope))
        )

    async def verify_feedback(
        self, token: str, verdict: str, note: Optional[str] = None
    ) -> JSONObject:
        """Record correct, incorrect or unsure on a verification result."""
        return cast(JSONObject, await self._send(R.verify_feedback(token, verdict, note)))

    async def verify_numeric(self, body: Mapping[str, Any]) -> JSONObject:
        """Check numeric arithmetic (POST /api/v2/verify/numeric)."""
        return cast(JSONObject, await self._send(R.verify_numeric(body)))

    async def search(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> VerifyResponse:
        """Search for sources (POST /api/v1/sources/search)."""
        return cast(VerifyResponse, await self._send(R.search(query, limit=limit, filters=filters)))

    # -- citations -----------------------------------------------------------------------

    async def list_citations(
        self,
        *,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        fields: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> CitationList:
        return cast(
            CitationList,
            await self._send(
                R.list_citations(page=page, limit=limit, fields=fields, thread_id=thread_id)
            ),
        )

    async def get_citation(self, citation_id: str) -> JSONObject:
        return cast(JSONObject, await self._send(R.get_citation(citation_id)))

    async def source_preview(
        self,
        *,
        url: Optional[str] = None,
        asset_id: Optional[str] = None,
        page: Optional[int] = None,
        quote: Optional[str] = None,
        **fields: Any,
    ) -> JSONObject:
        """Show the evidence passage at a URL or in an uploaded file."""
        return cast(
            JSONObject,
            await self._send(
                R.source_preview(
                    {"url": url, "asset_id": asset_id, "page": page, "quote": quote, **fields}
                )
            ),
        )

    # -- documents -----------------------------------------------------------------------

    async def upload(self, file: R.FileInput, *, filename: Optional[str] = None) -> UploadResponse:
        """Store a file (path, bytes or binary file object). Free. Keep data.asset_id."""
        return cast(UploadResponse, await self._send(R.upload(file, filename)))

    async def upload_url(self, url: str, *, filename: Optional[str] = None) -> UploadResponse:
        """Store the file at a public HTTPS URL."""
        return cast(UploadResponse, await self._send(R.upload_url(url, filename)))

    async def extract(
        self,
        asset_id: Optional[str] = None,
        *,
        asset_url: Optional[str] = None,
        mode: Optional[str] = None,
        refresh: Optional[bool] = None,
    ) -> ExtractResponse:
        """Read a document as Markdown with per-page units. Runs until every page is read."""
        return cast(
            ExtractResponse,
            await self._send(R.extract("", asset_id, asset_url, mode=mode, refresh=refresh)),
        )

    async def extract_visual_rendition(
        self,
        asset_id: Optional[str] = None,
        *,
        asset_url: Optional[str] = None,
        source_version_id: Optional[str] = None,
        refresh: Optional[bool] = None,
    ) -> JSONObject:
        return cast(
            JSONObject,
            await self._send(
                R.extract(
                    "/visual-rendition",
                    asset_id,
                    asset_url,
                    visual_rendition=True,
                    source_version_id=source_version_id,
                    refresh=refresh,
                )
            ),
        )

    async def extract_pages(
        self,
        asset_id: Optional[str] = None,
        *,
        asset_url: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> JSONObject:
        """Extract anchored chunks ready to index and cite."""
        return cast(
            JSONObject, await self._send(R.extract("/pages", asset_id, asset_url, mode=mode))
        )

    async def extract_figures(
        self, asset_id: Optional[str] = None, *, asset_url: Optional[str] = None
    ) -> JSONObject:
        """Extract every recognised number as a tagged, source-grounded figure."""
        return cast(JSONObject, await self._send(R.extract("/figures", asset_id, asset_url)))

    async def classify(
        self,
        asset_id: Optional[str] = None,
        *,
        asset_url: Optional[str] = None,
        taxonomy: Optional[str] = None,
    ) -> JSONObject:
        return cast(JSONObject, await self._send(R.classify(asset_id, asset_url, taxonomy)))

    async def gaps(
        self,
        category: str,
        docs: Sequence[Mapping[str, Any]],
        *,
        stage: Optional[str] = None,
        taxonomy: Optional[str] = None,
    ) -> JSONObject:
        return cast(
            JSONObject, await self._send(R.gaps(category, docs, stage=stage, taxonomy=taxonomy))
        )

    async def ask(
        self,
        question: str,
        document_text: str,
        *,
        document_name: Optional[str] = None,
        has_text_layer: Optional[bool] = None,
        top_k: Optional[int] = None,
    ) -> AskJob:
        """Queue a question over document text. Poll with get_ask() or wait_for_ask()."""
        return cast(
            AskJob,
            await self._send(
                R.ask(
                    question,
                    document_text,
                    document_name=document_name,
                    has_text_layer=has_text_layer,
                    top_k=top_k,
                )
            ),
        )

    async def get_ask(self, job_id: str) -> AskJob:
        return cast(AskJob, await self._send(R.get_ask(job_id)))

    async def wait_for_ask(
        self, job_id: str, *, poll_interval: float = 2.0, max_wait: Optional[float] = 600.0
    ) -> AskJob:
        """Poll until done or failed. After max_wait, returns the latest job view unchanged."""
        started = time.monotonic()
        while True:
            job = await self.get_ask(job_id)
            if job.get("status") in R.ASK_TERMINAL:
                return job
            if max_wait is not None and time.monotonic() - started >= max_wait:
                return job
            await asyncio.sleep(poll_interval)

    async def analyze_conflicts(
        self,
        figures: Sequence[Mapping[str, Any]],
        *,
        fx_rates: Optional[Sequence[Mapping[str, Any]]] = None,
        precedence_rules: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> JSONObject:
        return cast(
            JSONObject,
            await self._send(
                R.analyze_conflicts(figures, fx_rates=fx_rates, precedence_rules=precedence_rules)
            ),
        )

    async def analyze_document(self, asset_id: str) -> JSONObject:
        return cast(JSONObject, await self._send(R.analyze_document(asset_id)))

    async def accuracy(self) -> JSONObject:
        return cast(JSONObject, await self._send(R.accuracy()))

    async def balance(self) -> Balance:
        """Read remaining, used and total credits. Free."""
        return cast(Balance, await self._send(R.balance()))

    # -- retained sources (v2) -----------------------------------------------------------

    async def register_source(
        self, asset_id: str, file: R.FileInput, *, filename: Optional[str] = None
    ) -> JSONObject:
        return cast(JSONObject, await self._send(R.register_source(asset_id, file, filename)))

    async def publish_text_representation(self, version_id: str) -> JSONObject:
        return cast(JSONObject, await self._send(R.publish_text_representation(version_id)))

    async def latest_representation(self, version_id: str) -> JSONObject:
        return cast(JSONObject, await self._send(R.latest_representation(version_id)))

    async def source_unit(
        self, version_id: str, representation_id: str, unit_id: str
    ) -> JSONObject:
        return cast(
            JSONObject, await self._send(R.source_unit(version_id, representation_id, unit_id))
        )

    async def prepare_ocr_rescue(self, version_id: str, representation_id: str) -> JSONObject:
        return cast(
            JSONObject, await self._send(R.prepare_ocr_rescue(version_id, representation_id))
        )


def _timeout_message(spec: R.RequestSpec) -> str:
    return (
        f"{spec.method} {spec.path} did not answer within the client timeout. The server may "
        "still have completed the work; keep any operation IDs and check before repeating a "
        "paid call. Raise timeout= for long documents."
    )


__all__ = ["AsyncWebcite"]
