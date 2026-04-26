#!/usr/bin/env python3
"""Embedding-assisted anchor retrieval for schema routing."""

from __future__ import annotations

from backends.embeddings import cosine_similarity
try:
    from crossextend_kg.models import RetrievedAnchor, SchemaCandidate
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import RetrievedAnchor, SchemaCandidate

_ANCHOR_VECTOR_CACHE: dict[tuple[int, tuple[str, ...]], list[list[float]]] = {}

_BASE_ANCHORS = {"Asset", "Component", "Signal", "State", "Fault"}
_RELATION_COMPATIBILITY: dict[str, dict[str, float]] = {
    "structural": {"Asset": 0.15, "Component": 0.15, "Signal": -0.10, "Fault": -0.10},
    "communication": {"Signal": 0.10, "State": 0.10, "Fault": 0.10, "Asset": -0.15},
    "propagation": {"Fault": 0.10, "Signal": 0.10, "State": 0.10, "Component": 0.10},
    "lifecycle": {"State": 0.10, "Fault": 0.10, "Component": 0.10, "Asset": 0.10},
}


def empty_retrievals(candidates: list[SchemaCandidate]) -> dict[str, list[RetrievedAnchor]]:
    return {candidate.candidate_id: [] for candidate in candidates}


def _embed_texts(embedding_backend, texts: list[str], domain_id: str | None = None) -> list[list[float]]:
    try:
        return embedding_backend.embed_texts(texts, domain_id=domain_id)
    except TypeError:
        return embedding_backend.embed_texts(texts)


def _baseline_candidate_text(candidate: SchemaCandidate) -> str:
    return f"{candidate.label}: {candidate.description}".strip()


def _contextual_candidate_text(candidate: SchemaCandidate) -> str:
    features = candidate.routing_features or {}
    parts = [_baseline_candidate_text(candidate)]
    evidence_texts = [text for text in candidate.evidence_texts[:2] if text]
    if evidence_texts:
        parts.append("evidence: " + " ".join(evidence_texts))
    relation_families = features.get("relation_families") or []
    if relation_families:
        parts.append("relations: " + ", ".join(str(item) for item in relation_families))
    hint = features.get("semantic_type_hint")
    if hint:
        parts.append(f"semantic hint: {hint}")
    hint_candidates = features.get("semantic_type_hint_candidates") or []
    if hint_candidates:
        parts.append("semantic hint candidates: " + ", ".join(str(item) for item in hint_candidates))
    hypernym = features.get("shared_hypernym")
    if hypernym:
        parts.append(f"shared hypernym: {hypernym}")
    return " | ".join(parts)


def _anchor_prototypes(anchor: str, description: str) -> list[str]:
    return [
        f"{anchor}: {description}",
        f"{anchor} industrial ontology concept. Typical terms: {description}",
        f"Route candidates here when their function, relation context, and semantic evidence indicate {anchor}.",
    ]


def _relation_bonus(anchor: str, relation_families: list[str]) -> float:
    bonus = 0.0
    for family in relation_families:
        family_scores = _RELATION_COMPATIBILITY.get(str(family))
        if family_scores:
            bonus += family_scores.get(anchor, 0.0)
    return max(min(bonus, 0.20), -0.20)


def _rerank_adjustment(anchor: str, candidate: SchemaCandidate) -> float:
    features = candidate.routing_features or {}
    score = 0.0
    hint = features.get("semantic_type_hint")
    hint_candidates = set(features.get("semantic_type_hint_candidates") or [])
    shared_hypernym = features.get("shared_hypernym")
    relation_families = list(features.get("relation_families") or [])

    if hint == anchor:
        score += 0.20
    elif anchor in hint_candidates:
        score += 0.12
    elif hint in _BASE_ANCHORS and anchor in _BASE_ANCHORS:
        score -= 0.15

    if shared_hypernym == anchor:
        score += 0.25
    score += _relation_bonus(anchor, relation_families)
    return score


def retrieve_anchor_rankings(
    embedding_backend,
    backbone_descriptions: dict[str, str],
    candidates: list[SchemaCandidate],
    top_k: int,
    domain_id: str | None = None,
    mode: str = "baseline",
) -> dict[str, list[RetrievedAnchor]]:
    if not candidates:
        return {}

    rankings = empty_retrievals(candidates)
    anchor_names = list(backbone_descriptions)
    if mode == "baseline":
        anchor_texts = [f"{anchor}: {backbone_descriptions[anchor]}" for anchor in anchor_names]
        candidate_texts = [_baseline_candidate_text(candidate) for candidate in candidates]
        cache_key = (id(embedding_backend), tuple(anchor_texts))
        anchor_vectors = _ANCHOR_VECTOR_CACHE.get(cache_key)
        if anchor_vectors is None:
            anchor_vectors = _embed_texts(embedding_backend, anchor_texts, domain_id=domain_id)
            _ANCHOR_VECTOR_CACHE[cache_key] = anchor_vectors
        candidate_vectors = _embed_texts(embedding_backend, candidate_texts, domain_id=domain_id)

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

    if mode != "contextual_rerank":
        raise ValueError(f"unknown embedding routing mode: {mode}")

    anchor_prototype_texts: list[str] = []
    anchor_slices: dict[str, slice] = {}
    for anchor in anchor_names:
        start = len(anchor_prototype_texts)
        anchor_prototype_texts.extend(_anchor_prototypes(anchor, backbone_descriptions[anchor]))
        anchor_slices[anchor] = slice(start, len(anchor_prototype_texts))

    cache_key = (id(embedding_backend), tuple(anchor_prototype_texts))
    prototype_vectors = _ANCHOR_VECTOR_CACHE.get(cache_key)
    if prototype_vectors is None:
        prototype_vectors = _embed_texts(embedding_backend, anchor_prototype_texts, domain_id=domain_id)
        _ANCHOR_VECTOR_CACHE[cache_key] = prototype_vectors

    candidate_vectors = _embed_texts(
        embedding_backend,
        [_contextual_candidate_text(candidate) for candidate in candidates],
        domain_id=domain_id,
    )

    for candidate, candidate_vector in zip(candidates, candidate_vectors, strict=False):
        scored = []
        for anchor in anchor_names:
            vectors = prototype_vectors[anchor_slices[anchor]]
            similarities = [cosine_similarity(candidate_vector, vector) for vector in vectors]
            embedding_score = (max(similarities) * 0.75) + ((sum(similarities) / len(similarities)) * 0.25)
            final_score = embedding_score + _rerank_adjustment(anchor, candidate)
            scored.append(RetrievedAnchor(anchor=anchor, score=final_score, rank=0))
        scored.sort(key=lambda item: item.score, reverse=True)
        rankings[candidate.candidate_id] = [
            item.model_copy(update={"rank": rank})
            for rank, item in enumerate(scored[:top_k], start=1)
        ]
    return rankings
