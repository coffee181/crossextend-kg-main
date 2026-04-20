#!/usr/bin/env python3
"""Embedding-assisted anchor retrieval for schema routing."""

from __future__ import annotations

from ..backends.embeddings import cosine_similarity
from ..models import RetrievedAnchor, SchemaCandidate

_ANCHOR_VECTOR_CACHE: dict[tuple[int, tuple[str, ...]], list[list[float]]] = {}


def empty_retrievals(candidates: list[SchemaCandidate]) -> dict[str, list[RetrievedAnchor]]:
    return {candidate.candidate_id: [] for candidate in candidates}


def _is_task_candidate(candidate: SchemaCandidate) -> bool:
    if candidate.routing_features.get("is_task_candidate"):
        return True
    task_step_id = candidate.routing_features.get("task_step_id")
    return isinstance(task_step_id, str) and task_step_id.startswith("T")


def retrieve_anchor_rankings(
    embedding_backend,
    backbone_descriptions: dict[str, str],
    candidates: list[SchemaCandidate],
    top_k: int,
) -> dict[str, list[RetrievedAnchor]]:
    if not candidates:
        return {}

    rankings = empty_retrievals(candidates)
    anchor_names = list(backbone_descriptions)
    anchor_texts = [f"{anchor}: {backbone_descriptions[anchor]}" for anchor in anchor_names]

    routable_candidates = [candidate for candidate in candidates if not _is_task_candidate(candidate)]
    if not routable_candidates:
        return rankings

    candidate_texts = [f"{candidate.label}: {candidate.description}".strip() for candidate in routable_candidates]
    cache_key = (id(embedding_backend), tuple(anchor_texts))
    anchor_vectors = _ANCHOR_VECTOR_CACHE.get(cache_key)
    if anchor_vectors is None:
        anchor_vectors = embedding_backend.embed_texts(anchor_texts)
        _ANCHOR_VECTOR_CACHE[cache_key] = anchor_vectors
    candidate_vectors = embedding_backend.embed_texts(candidate_texts)

    for candidate, candidate_vector in zip(routable_candidates, candidate_vectors, strict=False):
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
