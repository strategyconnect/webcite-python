"""Response types. Responses are plain dicts; these TypedDicts describe the documented fields.

Fields can be missing or null. A null value means the server did not know it, not zero, so
keep nulls as they are when you store a response.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

JSONObject = Dict[str, Any]


class Usage(TypedDict, total=False):
    credits: Optional[float]
    pages: Optional[int]
    page_charges: List[JSONObject]


class CreditUsage(TypedDict, total=False):
    credits_used: Optional[float]
    credits_remaining: Optional[float]
    monthly_allocation: Optional[float]
    overage_enabled: Optional[bool]
    operation_id: Optional[str]


class StanceBreakdown(TypedDict, total=False):
    supports: int
    partially_supports: int
    contradicts: int
    neutral: int
    inconclusive: int
    irrelevant: int
    unknown: int


class Verdict(TypedDict, total=False):
    claim: str
    result: str
    confidence: Optional[float]
    summary: str
    stance_breakdown: StanceBreakdown
    origin_count: int
    document_count: int
    insufficient_evidence: bool
    key_findings: List[JSONObject]
    corrections: List[JSONObject]
    confidence_basis: str
    confidence_available: bool
    confidence_meaning: str


class Citation(TypedDict, total=False):
    id: str
    title: str
    url: str
    snippet: str
    status: str
    source_type: str
    stance: str
    stance_confidence: Optional[float]
    stance_explanation: str
    credibility_score: Optional[float]
    rank: int
    group_id: str
    is_group_primary: bool
    source_metadata: JSONObject


class DomainGroup(TypedDict, total=False):
    group_id: str
    domain: str
    domain_category: str
    group_stance: str
    citation_ids: List[str]
    primary_citation_id: str


class ClaimGroup(TypedDict, total=False):
    claim_id: str
    claim_index: int
    claim: str
    stance_summary: str
    citation_count: int
    citations: List[Citation]
    domain_groups: List[DomainGroup]
    verdict: Verdict


class VerifyResponse(TypedDict, total=False):
    """Returned by verify() and search()."""

    claim_groups: List[ClaimGroup]
    citations: List[Citation]
    domain_groups: List[DomainGroup]
    verdict: Verdict
    totalResults: int
    thread_id: str
    operation_id: str
    search_metadata: JSONObject
    usage: Usage
    credit_usage: CreditUsage


class ExtractUnit(TypedDict, total=False):
    kind: str
    index: int
    text: str
    provenance: JSONObject
    elements: List[JSONObject]
    geometry: JSONObject
    extraction_method: str
    reader: JSONObject


class ExtractResponse(TypedDict, total=False):
    format: str
    markdown: str
    units: List[ExtractUnit]
    state: str
    code: Optional[str]
    reason: Optional[str]
    complete: bool
    lost: List[JSONObject]
    extraction_method: str
    operation_id: str
    usage: Usage
    credit_usage: CreditUsage


class UploadedAsset(TypedDict, total=False):
    asset_id: str
    asset_url: str
    source_version_id: str
    filename: str
    size: int


class UploadResponse(TypedDict, total=False):
    successCode: int
    message: str
    data: UploadedAsset
    operation_id: str
    usage: Usage
    credit_usage: CreditUsage


class CitationList(TypedDict, total=False):
    statusCode: int
    message: str
    data: List[JSONObject]
    pagination: JSONObject


class AskJob(TypedDict, total=False):
    id: str
    status: str
    operation_id: str
    billing_status: str
    billing: JSONObject
    result: JSONObject
    usage: Usage


class BalanceCredits(TypedDict, total=False):
    used: float
    remaining: float
    total: float


class Balance(TypedDict, total=False):
    credits: BalanceCredits
    allow_overage: bool
    monthly_allocation: str
    billing_period_start: str
    billing_period_end: str


class StreamEvent(TypedDict):
    event: str
    data: Any
