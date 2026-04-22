#!/usr/bin/env python3
"""Embedding-assisted anchor retrieval for schema routing."""

from __future__ import annotations

from backends.embeddings import cosine_similarity
try:
    from crossextend_kg.models import RetrievedAnchor, SchemaCandidate
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import RetrievedAnchor, SchemaCandidate

_ANCHOR_VECTOR_CACHE: dict[tuple[int, tuple[str, ...]], list[list[float]]] = {}


def empty_retrievals(candidates: list[SchemaCandidate]) -> dict[str, list[RetrievedAnchor]]:
    return {candidate.candidate_id: [] for candidate in candidates}


def retrieve_anchor_rankings(
    embedding_backend,
    backbone_descriptions: dict[str, str],
    candidates: list[SchemaCandidate],
    top_k: int,
    domain_id: str | None = None,
) -> dict[str, list[RetrievedAnchor]]:
    if not candidates:
        return {}

    rankings = empty_retrievals(candidates)
    anchor_names = list(backbone_descriptions)
    anchor_texts = [f"{anchor}: {backbone_descriptions[anchor]}" for anchor in anchor_names]
    candidate_texts = [f"{candidate.label}: {candidate.description}".strip() for candidate in candidates]
    cache_key = (id(embedding_backend), tuple(anchor_texts))
    anchor_vectors = _ANCHOR_VECTOR_CACHE.get(cache_key)
    if anchor_vectors is None:
        try:
            anchor_vectors = embedding_backend.embed_texts(anchor_texts, domain_id=domain_id)
        except TypeError:
            anchor_vectors = embedding_backend.embed_texts(anchor_texts)
        _ANCHOR_VECTOR_CACHE[cache_key] = anchor_vectors
    try:
        candidate_vectors = embedding_backend.embed_texts(candidate_texts, domain_id=domain_id)
    except TypeError:
        candidate_vectors = embedding_backend.embed_texts(candidate_texts)

    for candidate, candidate_vector in zip(candidates, candidate_vectors, strict=False):
        scored: list[RetrievedAnchor] = []
        for anchor_name, anchor_vector in zip(anchor_names, anchor_vectors, strict=False):
            scored.append(
                RetrievedAnchor(
                    anchor=anchor_name,
                    score=cosine_similarity(candidate_vector, anchor_vector),
                    rank=0,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        rankings[candidate.candidate_id] = [
            item.model_copy(update={"rank": rank})
            for rank, item in enumerate(scored[:top_k], start=1)
        ]
    return rankings
