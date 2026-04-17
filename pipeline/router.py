#!/usr/bin/env python3
"""Embedding-assisted anchor retrieval for schema routing."""

from __future__ import annotations

from ..backends.embeddings import cosine_similarity
from ..models import RetrievedAnchor, SchemaCandidate


def empty_retrievals(candidates: list[SchemaCandidate]) -> dict[str, list[RetrievedAnchor]]:
    return {candidate.candidate_id: [] for candidate in candidates}


def retrieve_anchor_rankings(
    embedding_backend,
    backbone_descriptions: dict[str, str],
    candidates: list[SchemaCandidate],
    top_k: int,
) -> dict[str, list[RetrievedAnchor]]:
    if not candidates:
        return {}

    anchor_names = list(backbone_descriptions)
    anchor_texts = [f"{anchor}: {backbone_descriptions[anchor]}" for anchor in anchor_names]
    candidate_texts = [f"{candidate.label}: {candidate.description}" for candidate in candidates]
    anchor_vectors = embedding_backend.embed_texts(anchor_texts)
    candidate_vectors = embedding_backend.embed_texts(candidate_texts)

    rankings: dict[str, list[RetrievedAnchor]] = {}
    for candidate, candidate_vector in zip(candidates, candidate_vectors):
        scored: list[RetrievedAnchor] = []
        for anchor_name, anchor_vector in zip(anchor_names, anchor_vectors):
            scored.append(
                RetrievedAnchor(
                    anchor=anchor_name,
                    score=cosine_similarity(candidate_vector, anchor_vector),
                    rank=0,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        top_items: list[RetrievedAnchor] = []
        for rank, item in enumerate(scored[:top_k], start=1):
            top_items.append(item.model_copy(update={"rank": rank}))
        rankings[candidate.candidate_id] = top_items
    return rankings

