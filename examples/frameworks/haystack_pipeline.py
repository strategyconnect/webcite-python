"""Convert a PDF to Markdown, then check a claim from it, in one Haystack pipeline run.

Install: pip install webcite-haystack
Run:     WEBCITE_API_KEY=... python haystack_pipeline.py
"""

from haystack import Pipeline
from haystack_integrations.components.converters.webcite import WebciteDocumentConverter
from haystack_integrations.components.verifiers.webcite import WebciteClaimVerifier
from haystack_integrations.components.websearch.webcite import WebciteWebSearch

pipe = Pipeline()
pipe.add_component("convert", WebciteDocumentConverter(mode="lite"))
pipe.add_component("search", WebciteWebSearch(top_k=3))
pipe.add_component("verify", WebciteClaimVerifier(max_citations=2))

result = pipe.run(
    {
        "convert": {"sources": ["https://www.irs.gov/pub/irs-pdf/fw9.pdf"]},
        "search": {"query": "Apple total net sales fiscal 2024"},
        "verify": {"claims": ["The Great Wall of China is visible from the Moon."]},
    }
)
print(result["convert"]["documents"][0].meta)
print(result["search"]["links"])
print(result["verify"]["verdicts"][0]["result"])
