"""Request builders shared by the sync and async clients.

Each builder returns a RequestSpec. The clients only send specs, so both clients call the same
paths with the same bodies. ``tests/test_contract.py`` checks every path and method here
against the public OpenAPI document.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import IO, Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import quote

FileInput = Union[str, "os.PathLike[str]", bytes, IO[bytes]]


@dataclass(frozen=True)
class RequestSpec:
    method: str
    path: str
    json: Optional[Mapping[str, Any]] = None
    params: Optional[Mapping[str, Any]] = None
    files: Optional[Mapping[str, Tuple[str, Any]]] = None
    data: Optional[Mapping[str, str]] = None
    idempotency_key: Optional[str] = None
    stream: bool = False

    @property
    def retryable(self) -> bool:
        """GET requests and keyed verifications are safe to repeat."""
        return self.method == "GET" or self.idempotency_key is not None


def _seg(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Path identifiers must be non-empty strings.")
    return quote(value, safe="")


def _compact(**fields: Any) -> Dict[str, Any]:
    """Drop arguments the caller did not pass, so server defaults apply."""
    return {k: v for k, v in fields.items() if v is not None}


def _asset(asset_id: Optional[str], asset_url: Optional[str]) -> Dict[str, Any]:
    if not asset_id and not asset_url:
        raise ValueError("Pass asset_id (from upload) or asset_url.")
    return _compact(asset_id=asset_id, asset_url=asset_url)


def read_file(file: FileInput, filename: Optional[str]) -> Tuple[str, bytes]:
    if isinstance(file, bytes):
        if not filename:
            raise ValueError("Pass filename= with bytes; its extension decides how it is read.")
        return filename, file
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        with open(path, "rb") as handle:
            return filename or os.path.basename(path), handle.read()
    name = filename or os.path.basename(str(getattr(file, "name", "")))
    if not name:
        raise ValueError("Pass filename= for a file object without a name.")
    return name, file.read()


def verify(
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
    stream: bool = False,
) -> RequestSpec:
    body = _compact(
        claim=claim,
        source_urls=list(source_urls) if source_urls else None,
        filters=filters,
        thread_id=thread_id,
        include_stance=include_stance,
        include_verdict=include_verdict,
        decompose_claim=decompose_claim,
        include_numeric_assess=include_numeric_assess,
        include_source_reads=include_source_reads,
        evidence_scope=evidence_scope,
    )
    if stream:
        return RequestSpec("POST", "/api/v1/verify/stream", json=body, stream=True)
    return RequestSpec(
        "POST", "/api/v1/verify", json=body, idempotency_key=idempotency_key or str(uuid.uuid4())
    )


def verify_batch(
    items: Sequence[Mapping[str, Any]], *, evidence_scope: Optional[Mapping[str, Any]] = None
) -> RequestSpec:
    body = _compact(items=[dict(i) for i in items], evidence_scope=evidence_scope)
    return RequestSpec("POST", "/api/v1/verify/batch", json=body)


def verify_feedback(token: str, verdict: str, note: Optional[str] = None) -> RequestSpec:
    return RequestSpec(
        "POST", "/api/v1/verify/feedback", json=_compact(token=token, verdict=verdict, note=note)
    )


def verify_numeric(body: Mapping[str, Any]) -> RequestSpec:
    return RequestSpec("POST", "/api/v2/verify/numeric", json=dict(body))


def search(
    query: str, *, limit: Optional[int] = None, filters: Optional[Mapping[str, Any]] = None
) -> RequestSpec:
    return RequestSpec(
        "POST", "/api/v1/sources/search", json=_compact(query=query, limit=limit, filters=filters)
    )


def list_citations(
    *,
    page: Optional[int] = None,
    limit: Optional[int] = None,
    fields: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> RequestSpec:
    return RequestSpec(
        "GET",
        "/api/v1/citations",
        params=_compact(page=page, limit=limit, fields=fields, thread_id=thread_id),
    )


def get_citation(citation_id: str) -> RequestSpec:
    return RequestSpec("GET", f"/api/v1/citations/{_seg(citation_id)}")


def source_preview(fields: Mapping[str, Any]) -> RequestSpec:
    body = _compact(**fields)
    if not body:
        raise ValueError("Pass url, or asset_id with page, quote or source_unit_id.")
    return RequestSpec("POST", "/api/v1/citations/source-preview", json=body)


def upload(file: FileInput, filename: Optional[str] = None) -> RequestSpec:
    name, content = read_file(file, filename)
    return RequestSpec("POST", "/api/v1/upload", files={"file": (name, content)})


def upload_url(url: str, filename: Optional[str] = None) -> RequestSpec:
    return RequestSpec("POST", "/api/v1/upload/url", json=_compact(url=url, filename=filename))


def extract(
    path: str, asset_id: Optional[str], asset_url: Optional[str], **options: Any
) -> RequestSpec:
    return RequestSpec(
        "POST",
        f"/api/v1/extract{path}",
        json={**_asset(asset_id, asset_url), **_compact(**options)},
    )


def classify(
    asset_id: Optional[str], asset_url: Optional[str], taxonomy: Optional[str]
) -> RequestSpec:
    return RequestSpec(
        "POST",
        "/api/v1/classify",
        json={**_asset(asset_id, asset_url), **_compact(taxonomy=taxonomy)},
    )


def gaps(
    category: str,
    docs: Sequence[Mapping[str, Any]],
    *,
    stage: Optional[str] = None,
    taxonomy: Optional[str] = None,
) -> RequestSpec:
    return RequestSpec(
        "POST",
        "/api/v1/gaps",
        json=_compact(
            category=category, docs=[dict(d) for d in docs], stage=stage, taxonomy=taxonomy
        ),
    )


def ask(
    question: str,
    document_text: str,
    *,
    document_name: Optional[str] = None,
    has_text_layer: Optional[bool] = None,
    top_k: Optional[int] = None,
) -> RequestSpec:
    return RequestSpec(
        "POST",
        "/api/v1/ask",
        json=_compact(
            question=question,
            documentText=document_text,
            documentName=document_name,
            hasTextLayer=has_text_layer,
            topK=top_k,
        ),
    )


def get_ask(job_id: str) -> RequestSpec:
    return RequestSpec("GET", f"/api/v1/ask/{_seg(job_id)}")


def analyze_conflicts(
    figures: Sequence[Mapping[str, Any]],
    *,
    fx_rates: Optional[Sequence[Mapping[str, Any]]] = None,
    precedence_rules: Optional[Sequence[Mapping[str, Any]]] = None,
) -> RequestSpec:
    return RequestSpec(
        "POST",
        "/api/v1/analyze/conflicts",
        json=_compact(
            figures=[dict(f) for f in figures],
            fxRates=[dict(r) for r in fx_rates] if fx_rates is not None else None,
            precedenceRules=[dict(r) for r in precedence_rules]
            if precedence_rules is not None
            else None,
        ),
    )


def analyze_document(asset_id: str) -> RequestSpec:
    return RequestSpec("POST", "/api/v1/analyze/document", json={"asset_id": asset_id})


def accuracy() -> RequestSpec:
    return RequestSpec("GET", "/api/v1/accuracy")


def balance() -> RequestSpec:
    # Account route used by the Webcite MCP server's get_credit_balance tool. It accepts an API
    # key but is not in the public OpenAPI document; the contract test lists it as the one
    # exception.
    return RequestSpec("GET", "/api/v1/payment/credits/balance")


def register_source(asset_id: str, file: FileInput, filename: Optional[str] = None) -> RequestSpec:
    name, content = read_file(file, filename)
    return RequestSpec(
        "POST", "/api/v2/sources", files={"file": (name, content)}, data={"assetId": asset_id}
    )


def _rep(version_id: str, rest: str = "") -> str:
    return f"/api/v2/sources/{_seg(version_id)}/representations{rest}"


def publish_text_representation(version_id: str) -> RequestSpec:
    return RequestSpec("POST", _rep(version_id, "/text"))


def latest_representation(version_id: str) -> RequestSpec:
    return RequestSpec("GET", _rep(version_id, "/latest"))


def source_unit(version_id: str, representation_id: str, unit_id: str) -> RequestSpec:
    return RequestSpec("GET", _rep(version_id, f"/{_seg(representation_id)}/units/{_seg(unit_id)}"))


def prepare_ocr_rescue(version_id: str, representation_id: str) -> RequestSpec:
    return RequestSpec("POST", _rep(version_id, f"/{_seg(representation_id)}/prepare-ocr-rescue"))


ASK_TERMINAL: List[str] = ["done", "failed"]
