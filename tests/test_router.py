from __future__ import annotations

from crossextend_kg.models import SchemaCandidate
from crossextend_kg.pipeline.router import retrieve_anchor_rankings


class _FakeEmbeddingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(tuple(texts))
        return [
            [float(len(text)), float(sum(ord(char) for char in text) % 97)]
            for text in texts
        ]


def test_retrieve_anchor_rankings_caches_backbone_vectors_per_backend() -> None:
    backend = _FakeEmbeddingBackend()
    backbone_descriptions = {
        "Component": "physical component",
        "Signal": "observable signal",
    }
    candidates = [
        SchemaCandidate(
            candidate_id="battery::coolant level",
            domain_id="battery",
            label="coolant level",
            description="measured coolant level",
            evidence_ids=["BATOM_002"],
        )
    ]

    first = retrieve_anchor_rankings(
        embedding_backend=backend,
        backbone_descriptions=backbone_descriptions,
        candidates=candidates,
        top_k=1,
    )
    second = retrieve_anchor_rankings(
        embedding_backend=backend,
        backbone_descriptions=backbone_descriptions,
        candidates=candidates,
        top_k=1,
    )

    assert first["battery::coolant level"]
    assert second["battery::coolant level"]
    assert backend.calls.count(
        (
            "Component: physical component",
            "Signal: observable signal",
        )
    ) == 1
    assert len(backend.calls) == 3
