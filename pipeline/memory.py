#!/usr/bin/env python3
"""Temporal MemoryBank for retrieval-augmented KG construction."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..backends.embeddings import cosine_similarity
from ..config import PipelineConfig
from ..io import ensure_dir, read_jsonl, write_jsonl
from ..models import (
    AttachmentDecision,
    DomainGraphArtifacts,
    HistoricalContextHit,
    MemoryEntry,
    SchemaCandidate,
)


EMBEDDING_WEIGHT = 0.40
LABEL_MATCH_WEIGHT = 0.25
TOKEN_OVERLAP_WEIGHT = 0.15
DOMAIN_AFFINITY_WEIGHT = 0.10
TIME_DECAY_WEIGHT = 0.05
ANCHOR_SCORE_WEIGHT = 0.05
MEMORY_HIT_THRESHOLD = 0.18
TIME_DECAY_HALF_LIFE_DAYS = 180
CROSS_DOMAIN_AFFINITY_SCORE = 0.6
ATTACHMENT_CONFIDENCE_THRESHOLD = 0.5


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]+", value.lower()))


def _truncate(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _dedupe_memory_entries(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    deduped: dict[str, MemoryEntry] = {}
    for entry in entries:
        current = deduped.get(entry.memory_id)
        if current is None or entry.timestamp >= current.timestamp:
            deduped[entry.memory_id] = entry
    return sorted(deduped.values(), key=lambda item: item.timestamp, reverse=True)


def _build_memory_path(config: PipelineConfig) -> Path:
    if config.runtime.temporal_memory_path:
        return Path(config.runtime.temporal_memory_path)
    return Path(config.runtime.artifact_root) / "temporal_memory_bank.jsonl"


def _is_task_candidate(candidate: SchemaCandidate) -> bool:
    if candidate.routing_features.get("is_task_candidate"):
        return True
    task_step_id = candidate.routing_features.get("task_step_id")
    return isinstance(task_step_id, str) and task_step_id.startswith("T")


def load_persistent_memory_bank(config: PipelineConfig) -> list[MemoryEntry]:
    if not config.runtime.enable_temporal_memory_bank:
        return []
    path = _build_memory_path(config)
    if not path.exists():
        return []
    items = _dedupe_memory_entries([MemoryEntry.model_validate(item) for item in read_jsonl(path)])
    return items[: config.runtime.temporal_memory_max_entries]


def save_temporal_memory_bank(path: str | Path, entries: list[MemoryEntry], max_entries: int) -> None:
    ensure_dir(Path(path).parent)
    deduped: dict[str, MemoryEntry] = {}
    for entry in entries:
        deduped[entry.memory_id] = entry
    ordered = sorted(deduped.values(), key=lambda item: item.timestamp, reverse=True)[:max_entries]
    write_jsonl(path, ordered)


def build_evidence_memory_entries(records_by_domain: dict[str, list[Any]]) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for domain_id, records in records_by_domain.items():
        for record in records:
            labels = [
                mention.label
                for step_record in record.step_records
                for mention in step_record.concept_mentions
                if mention.node_worthy
            ]
            labels.extend(
                mention.label for mention in record.document_concept_mentions if mention.node_worthy
            )
            families = sorted({relation.family for relation in record.relation_mentions})
            tags = sorted(_tokenize(" ".join(labels + families)))
            summary_parts = [
                f"domain={domain_id}",
                f"source_type={record.source_type}",
                f"labels={', '.join(labels[:6])}" if labels else "labels=none",
                f"families={', '.join(families[:6])}" if families else "families=none",
                f"text={_truncate(record.raw_text, 160)}",
            ]
            summary = " | ".join(summary_parts)
            entries.append(
                MemoryEntry(
                    memory_id=f"evidence::{record.evidence_id}",
                    entry_type="evidence",
                    domain_id=domain_id,
                    timestamp=record.timestamp,
                    summary=summary,
                    label_refs=labels,
                    relation_families=families,
                    evidence_ids=[record.evidence_id],
                    tags=tags,
                    embedding_text=" ".join([record.raw_text, " ".join(labels), " ".join(families)]).strip(),
                )
            )
    return entries


def retrieve_historical_context(
    config: PipelineConfig,
    embedding_backend: Any,
    records_by_domain: dict[str, list[Any]],
    candidates_by_domain: dict[str, list[SchemaCandidate]],
    persistent_entries: list[MemoryEntry],
) -> dict[str, dict[str, list[HistoricalContextHit]]]:
    if not config.runtime.enable_temporal_memory_bank:
        return {domain_id: {} for domain_id in candidates_by_domain}

    current_entries = build_evidence_memory_entries(records_by_domain)
    all_entries = _dedupe_memory_entries(persistent_entries + current_entries)
    if not all_entries:
        return {domain_id: {} for domain_id in candidates_by_domain}

    evidence_times = {
        record.evidence_id: record.timestamp
        for records in records_by_domain.values()
        for record in records
    }

    entry_texts = [entry.embedding_text or entry.summary for entry in all_entries]
    entry_vectors = embedding_backend.embed_texts(entry_texts)

    historical_context_by_domain: dict[str, dict[str, list[HistoricalContextHit]]] = {}
    for domain_id, candidates in candidates_by_domain.items():
        domain_hits: dict[str, list[HistoricalContextHit]] = {
            candidate.candidate_id: [] for candidate in candidates
        }
        routable_candidates = [candidate for candidate in candidates if not _is_task_candidate(candidate)]
        if not routable_candidates:
            historical_context_by_domain[domain_id] = domain_hits
            continue

        candidate_texts = [
            " ".join([candidate.label, candidate.description, " ".join(candidate.evidence_texts[:2])]).strip()
            or candidate.label
            for candidate in routable_candidates
        ]
        candidate_vectors = embedding_backend.embed_texts(candidate_texts)

        for candidate, candidate_vec, candidate_text in zip(
            routable_candidates,
            candidate_vectors,
            candidate_texts,
            strict=False,
        ):
            candidate_tokens = _tokenize(candidate_text)
            candidate_time = min(
                (
                    _parse_timestamp(evidence_times.get(evidence_id))
                    for evidence_id in candidate.evidence_ids
                    if evidence_times.get(evidence_id)
                ),
                default=None,
            )

            hits: list[HistoricalContextHit] = []
            for entry, entry_vec in zip(all_entries, entry_vectors, strict=False):
                if entry.evidence_ids and set(entry.evidence_ids) & set(candidate.evidence_ids):
                    continue

                entry_time = _parse_timestamp(entry.timestamp)
                if candidate_time and entry_time and entry_time > candidate_time:
                    continue

                embed_score = max(cosine_similarity(candidate_vec, entry_vec), 0.0)
                matched_labels = sorted(
                    {label for label in entry.label_refs if label.lower() == candidate.label.lower()}
                )
                label_score = 1.0 if matched_labels else 0.0
                overlap = len(candidate_tokens & set(entry.tags))
                token_score = overlap / max(len(candidate_tokens), 1)
                domain_score = 1.0 if entry.domain_id == candidate.domain_id else CROSS_DOMAIN_AFFINITY_SCORE

                if candidate_time and entry_time:
                    days = abs((candidate_time - entry_time).total_seconds()) / 86400
                    time_score = math.exp(-days / TIME_DECAY_HALF_LIFE_DAYS)
                else:
                    time_score = 0.5

                anchor_score = 1.0 if entry.parent_anchor else 0.0
                score = (
                    EMBEDDING_WEIGHT * embed_score
                    + LABEL_MATCH_WEIGHT * label_score
                    + TOKEN_OVERLAP_WEIGHT * token_score
                    + DOMAIN_AFFINITY_WEIGHT * domain_score
                    + TIME_DECAY_WEIGHT * time_score
                    + ANCHOR_SCORE_WEIGHT * anchor_score
                )
                if score < MEMORY_HIT_THRESHOLD:
                    continue

                hits.append(
                    HistoricalContextHit(
                        memory_id=entry.memory_id,
                        entry_type=entry.entry_type,
                        domain_id=entry.domain_id,
                        timestamp=entry.timestamp,
                        score=round(score, 4),
                        summary=entry.summary,
                        parent_anchor=entry.parent_anchor,
                        snapshot_id=entry.snapshot_id,
                        variant_id=entry.variant_id,
                        matched_labels=matched_labels,
                        evidence_ids=list(entry.evidence_ids),
                    )
                )

            hits.sort(key=lambda item: item.score, reverse=True)
            domain_hits[candidate.candidate_id] = hits[: config.runtime.temporal_memory_top_k]

        historical_context_by_domain[domain_id] = domain_hits

    return historical_context_by_domain


def top_historical_parent_anchor(
    hits: list[HistoricalContextHit] | None,
    backbone_concepts: set[str],
    min_score: float = 0.3,
) -> str | None:
    if not hits:
        return None
    counts = Counter(
        hit.parent_anchor
        for hit in hits
        if hit.parent_anchor and hit.parent_anchor in backbone_concepts and hit.score >= min_score
    )
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def build_variant_memory_entries(
    variant_id: str,
    run_root: str | None,
    records_by_domain: dict[str, list[Any]],
    candidates_by_domain: dict[str, list[SchemaCandidate]],
    decisions_by_domain: dict[str, dict[str, AttachmentDecision]],
    historical_context_by_domain: dict[str, dict[str, list[HistoricalContextHit]]],
    domain_graphs: dict[str, DomainGraphArtifacts],
) -> list[MemoryEntry]:
    entries = build_evidence_memory_entries(records_by_domain)
    run_token = Path(run_root).name if run_root else "run"

    evidence_times = {
        record.evidence_id: record.timestamp
        for records in records_by_domain.values()
        for record in records
    }
    candidates_lookup = {
        candidate.candidate_id: candidate
        for candidates in candidates_by_domain.values()
        for candidate in candidates
    }

    for domain_id, decisions in decisions_by_domain.items():
        historical_hits = historical_context_by_domain.get(domain_id, {})
        for decision in decisions.values():
            candidate = candidates_lookup.get(decision.candidate_id)
            if candidate is not None and _is_task_candidate(candidate):
                continue
            if not decision.accept or decision.confidence < ATTACHMENT_CONFIDENCE_THRESHOLD:
                continue

            timestamp = min(
                (evidence_times.get(evidence_id) for evidence_id in decision.evidence_ids if evidence_times.get(evidence_id)),
                default="",
            )
            if not timestamp:
                continue

            hits = historical_hits.get(decision.candidate_id, [])
            related_memory_ids = [hit.memory_id for hit in hits[:3]]
            summary = (
                f"variant={variant_id} | candidate={decision.label} | route={decision.route} | "
                f"parent_anchor={decision.parent_anchor or 'none'} | history={', '.join(related_memory_ids) or 'none'}"
            )
            entries.append(
                MemoryEntry(
                    memory_id=f"{run_token}::{variant_id}::attachment::{decision.candidate_id}",
                    entry_type="attachment",
                    domain_id=domain_id,
                    timestamp=timestamp,
                    summary=summary,
                    label_refs=[decision.label],
                    evidence_ids=list(decision.evidence_ids),
                    parent_anchor=decision.parent_anchor,
                    variant_id=variant_id,
                    run_root=run_root,
                    tags=sorted(_tokenize(" ".join([decision.label, decision.route, decision.parent_anchor or ""]))),
                    embedding_text=summary,
                    confidence=decision.confidence,
                )
            )

    for domain_id, graph in domain_graphs.items():
        previous_nodes: set[str] = set()
        previous_edges: set[str] = set()
        state_by_snapshot = {state.snapshot_id: state for state in graph.snapshot_states}

        for manifest in graph.snapshots:
            state = state_by_snapshot.get(manifest.snapshot_id)
            if state is None:
                continue
            current_nodes = {node.node_id for node in state.nodes}
            current_edges = {edge.edge_id for edge in state.edges}
            new_nodes = sorted(current_nodes - previous_nodes)
            new_edges = sorted(current_edges - previous_edges)

            summary = (
                f"variant={variant_id} | snapshot={manifest.snapshot_id} | "
                f"new_nodes={len(new_nodes)} | new_edges={len(new_edges)} | "
                f"accepted_evidence={', '.join(manifest.accepted_evidence_ids[-3:])}"
            )
            entries.append(
                MemoryEntry(
                    memory_id=f"{run_token}::{variant_id}::snapshot::{manifest.snapshot_id}",
                    entry_type="snapshot",
                    domain_id=domain_id,
                    timestamp=manifest.created_at,
                    summary=summary,
                    label_refs=[item.split("::")[-1] for item in new_nodes[:6]],
                    evidence_ids=list(manifest.accepted_evidence_ids),
                    snapshot_id=manifest.snapshot_id,
                    variant_id=variant_id,
                    run_root=run_root,
                    tags=["snapshot", domain_id, variant_id],
                    embedding_text=summary,
                )
            )
            previous_nodes = current_nodes
            previous_edges = current_edges

    return entries


def count_memory_entries_by_type(entries: list[MemoryEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.entry_type] = counts.get(entry.entry_type, 0) + 1
    return counts


def filter_entries_by_domain(entries: list[MemoryEntry], domain_id: str) -> list[MemoryEntry]:
    return [entry for entry in entries if entry.domain_id == domain_id]


def filter_entries_by_label(entries: list[MemoryEntry], label: str) -> list[MemoryEntry]:
    lowered = label.lower()
    return [
        entry
        for entry in entries
        if any(ref.lower() == lowered for ref in entry.label_refs)
    ]


def get_unique_parent_anchors(entries: list[MemoryEntry]) -> set[str]:
    return {entry.parent_anchor for entry in entries if entry.parent_anchor}


def summarize_memory_bank(entries: list[MemoryEntry]) -> dict[str, Any]:
    if not entries:
        return {"total_count": 0}

    by_type = count_memory_entries_by_type(entries)
    domains = sorted(set(entry.domain_id for entry in entries))
    timestamps = sorted(entry.timestamp for entry in entries)
    anchors = get_unique_parent_anchors(entries)
    return {
        "total_count": len(entries),
        "by_type": by_type,
        "domains": domains,
        "earliest_timestamp": timestamps[0] if timestamps else None,
        "latest_timestamp": timestamps[-1] if timestamps else None,
        "unique_parent_anchors": len(anchors),
        "parent_anchors_sample": sorted(list(anchors))[:10],
    }
