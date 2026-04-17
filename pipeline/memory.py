#!/usr/bin/env python3
"""Temporal MemoryBank for retrieval-augmented KG construction.

The MemoryBank provides historical context retrieval for attachment decisions,
enabling cross-run knowledge persistence and evidence-aware scoring.

Architecture:
- MemoryEntry: Single memory unit (evidence, attachment, or snapshot)
- HistoricalContextHit: Retrieved context match for a candidate
- Scoring: Multi-factor weighted scoring (embedding, label, token, domain, time, anchor)

Memory Entry Types:
- evidence: EvidenceRecord-derived entries
- attachment: AttachmentDecision-derived entries
- snapshot: SnapshotManifest-derived entries

Scoring Formula:
    score = 0.40 * embed_score  (cosine similarity)
          + 0.25 * label_score  (exact label match)
          + 0.15 * token_score  (token overlap)
          + 0.10 * domain_score (domain affinity)
          + 0.05 * time_score   (temporal decay)
          + 0.05 * anchor_score (has parent anchor)

Threshold: score >= MEMORY_HIT_THRESHOLD (0.18) to be included.

Integration Points:
1. Schema routing: Prior anchor hints for embedding retrieval
2. Attachment judgment: LLM prompt includes HistoricalContextHits
3. Post-run update: New entries saved to persistent MemoryBank

Usage:
    # Load persistent memory
    entries = load_persistent_memory_bank(config)

    # Retrieve context for candidates
    context = retrieve_historical_context(
        config, embedding_backend, records_by_domain,
        candidates_by_domain, entries
    )

    # Build and save new entries
    new_entries = build_variant_memory_entries(...)
    save_temporal_memory_bank(path, entries + new_entries, max_entries)
"""

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


# Scoring weights - configurable via config in future versions
EMBEDDING_WEIGHT = 0.40
LABEL_MATCH_WEIGHT = 0.25
TOKEN_OVERLAP_WEIGHT = 0.15
DOMAIN_AFFINITY_WEIGHT = 0.10
TIME_DECAY_WEIGHT = 0.05
ANCHOR_SCORE_WEIGHT = 0.05

# Minimum score threshold for including a hit
MEMORY_HIT_THRESHOLD = 0.18

# Time decay half-life in days (entries older than this score lower)
TIME_DECAY_HALF_LIFE_DAYS = 180

# Cross-domain affinity score (used when entry comes from a different domain)
CROSS_DOMAIN_AFFINITY_SCORE = 0.6

# Minimum confidence threshold for attachment memory entries
ATTACHMENT_CONFIDENCE_THRESHOLD = 0.5


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse ISO-format timestamp string to datetime.

    Args:
        value: ISO-format timestamp string (with or without 'Z' suffix)

    Returns:
        timezone-aware datetime object or None if parsing fails

    Note:
        If parsing fails, logs a warning. Failed parsing means temporal
        filtering will not be applied, potentially allowing "future" knowledge.
    """
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        # Ensure timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        # Log warning for failed parsing - this affects temporal filtering
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to parse timestamp '{value}'. Temporal filtering will be skipped for this entry."
        )
        return None


def _tokenize(value: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric and CJK tokens.

    Args:
        value: Text to tokenize

    Returns:
        Set of lowercase tokens
    """
    return set(re.findall(r"[\w\u4e00-\u9fff]+", value.lower()))


def _truncate(value: str, limit: int = 240) -> str:
    """Truncate text to limit with ellipsis suffix.

    Args:
        value: Text to truncate
        limit: Maximum length (default: 240)

    Returns:
        Truncated text with '...' suffix if needed
    """
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _build_memory_path(config: PipelineConfig) -> Path:
    """Build the MemoryBank storage path from config.

    Args:
        config: Pipeline configuration

    Returns:
        Path to MemoryBank JSONL file
    """
    if config.runtime.temporal_memory_path:
        return Path(config.runtime.temporal_memory_path)
    return Path(config.runtime.artifact_root) / "temporal_memory_bank.jsonl"


def load_persistent_memory_bank(config: PipelineConfig) -> list[MemoryEntry]:
    """Load persistent MemoryBank entries from disk.

    Reads entries from the configured path, sorts by timestamp descending,
    and returns up to max_entries.

    Args:
        config: Pipeline configuration with runtime.temporal_memory_* settings

    Returns:
        List of MemoryEntry objects, sorted newest-first, up to max_entries

    Note:
        Returns empty list if MemoryBank is disabled or file doesn't exist.
    """
    if not config.runtime.enable_temporal_memory_bank:
        return []
    path = _build_memory_path(config)
    if not path.exists():
        return []
    items = [MemoryEntry.model_validate(item) for item in read_jsonl(path)]
    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[: config.runtime.temporal_memory_max_entries]


def save_temporal_memory_bank(
    path: str | Path,
    entries: list[MemoryEntry],
    max_entries: int,
) -> None:
    """Save MemoryBank entries to disk with deduplication and truncation.

    Deduplicates by memory_id, sorts by timestamp descending, and writes
    up to max_entries to JSONL format.

    Args:
        path: Output file path
        entries: List of MemoryEntry objects to save
        max_entries: Maximum number of entries to keep

    Note:
        Creates parent directories if needed. Overwrites existing file.
    """
    ensure_dir(Path(path).parent)
    deduped: dict[str, MemoryEntry] = {}
    for entry in entries:
        deduped[entry.memory_id] = entry
    ordered = sorted(deduped.values(), key=lambda item: item.timestamp, reverse=True)[:max_entries]
    write_jsonl(path, ordered)


def build_evidence_memory_entries(
    records_by_domain: dict[str, list[Any]],
) -> list[MemoryEntry]:
    """Build MemoryEntry objects from EvidenceRecords.

    Creates evidence-type memory entries for each record, capturing:
    - Domain context
    - Source type
    - Concept labels (node-worthy only)
    - Relation families
    - Raw text excerpt

    Args:
        records_by_domain: Dict mapping domain_id to list of EvidenceRecord

    Returns:
        List of MemoryEntry objects with entry_type='evidence'
    """
    entries: list[MemoryEntry] = []
    for domain_id, records in records_by_domain.items():
        for record in records:
            labels = [mention.label for mention in record.concept_mentions if mention.node_worthy]
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
    """Retrieve historical context hits for each schema candidate.

    For each candidate, retrieves MemoryBank entries that:
    1. Don't share evidence_ids with the candidate (avoid self-retrieval)
    2. Have timestamp <= candidate's evidence timestamp (no future knowledge)
    3. Score >= MEMORY_HIT_THRESHOLD after multi-factor scoring

    Scoring Factors:
    - embed_score: Cosine similarity between candidate and entry embeddings
    - label_score: 1.0 if exact label match, else 0.0
    - token_score: Token overlap ratio (Jaccard-like)
    - domain_score: Affinity based on domain relationship
    - time_score: Exponential decay from candidate timestamp
    - anchor_score: 1.0 if entry has parent_anchor, else 0.0

    Args:
        config: Pipeline configuration with runtime.temporal_memory_* settings
        embedding_backend: Embedding provider for computing similarity
        records_by_domain: Dict mapping domain_id to EvidenceRecord list
        candidates_by_domain: Dict mapping domain_id to SchemaCandidate list
        persistent_entries: Pre-loaded MemoryEntry list from disk

    Returns:
        Dict[domain_id, Dict[candidate_id, List[HistoricalContextHit]]]

    Note:
        Returns empty dict per domain if MemoryBank is disabled.
    """
    if not config.runtime.enable_temporal_memory_bank:
        return {domain_id: {} for domain_id in candidates_by_domain}

    current_entries = build_evidence_memory_entries(records_by_domain)
    all_entries = persistent_entries + current_entries
    if not all_entries:
        return {domain_id: {} for domain_id in candidates_by_domain}

    # Build evidence timestamp lookup for candidate time filtering
    evidence_times = {
        record.evidence_id: record.timestamp
        for records in records_by_domain.values()
        for record in records
    }

    # Pre-compute entry embeddings for all entries
    entry_texts = [entry.embedding_text or entry.summary for entry in all_entries]
    entry_vectors = embedding_backend.embed_texts(entry_texts)

    historical_context_by_domain: dict[str, dict[str, list[HistoricalContextHit]]] = {}
    for domain_id, candidates in candidates_by_domain.items():
        domain_hits: dict[str, list[HistoricalContextHit]] = {}
        if not candidates:
            historical_context_by_domain[domain_id] = domain_hits
            continue

        # Pre-compute candidate embeddings
        candidate_texts = [
            " ".join([candidate.label, candidate.description, " ".join(candidate.evidence_texts[:2])]).strip()
            or candidate.label
            for candidate in candidates
        ]
        candidate_vectors = embedding_backend.embed_texts(candidate_texts)

        for candidate, candidate_vec, candidate_text in zip(
            candidates, candidate_vectors, candidate_texts, strict=False
        ):
            candidate_tokens = _tokenize(candidate_text)
            # Get earliest evidence timestamp for candidate
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
                # Skip entries sharing evidence with candidate (avoid self-retrieval)
                if entry.evidence_ids and set(entry.evidence_ids) & set(candidate.evidence_ids):
                    continue

                # Skip entries newer than candidate (no future knowledge)
                entry_time = _parse_timestamp(entry.timestamp)
                if candidate_time and entry_time and entry_time > candidate_time:
                    continue

                # Compute multi-factor score
                embed_score = max(cosine_similarity(candidate_vec, entry_vec), 0.0)
                matched_labels = sorted(
                    {label for label in entry.label_refs if label.lower() == candidate.label.lower()}
                )
                label_score = 1.0 if matched_labels else 0.0
                overlap = len(candidate_tokens & set(entry.tags))
                token_score = overlap / max(len(candidate_tokens), 1)

                # Domain affinity: same domain > other domain, with no privileged domain.
                if entry.domain_id == candidate.domain_id:
                    domain_score = 1.0
                else:
                    domain_score = CROSS_DOMAIN_AFFINITY_SCORE

                # Temporal decay: newer entries score higher
                if candidate_time and entry_time:
                    days = abs((candidate_time - entry_time).total_seconds()) / 86400
                    time_score = math.exp(-days / TIME_DECAY_HALF_LIFE_DAYS)
                else:
                    time_score = 0.5

                # Anchor presence: entries with parent_anchor are more valuable
                anchor_score = 1.0 if entry.parent_anchor else 0.0

                # Weighted final score
                score = (
                    EMBEDDING_WEIGHT * embed_score
                    + LABEL_MATCH_WEIGHT * label_score
                    + TOKEN_OVERLAP_WEIGHT * token_score
                    + DOMAIN_AFFINITY_WEIGHT * domain_score
                    + TIME_DECAY_WEIGHT * time_score
                    + ANCHOR_SCORE_WEIGHT * anchor_score
                )

                # Threshold filter
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

            # Sort by score descending, return top-k
            hits.sort(key=lambda item: item.score, reverse=True)
            domain_hits[candidate.candidate_id] = hits[: config.runtime.temporal_memory_top_k]

        historical_context_by_domain[domain_id] = domain_hits

    return historical_context_by_domain


def top_historical_parent_anchor(
    hits: list[HistoricalContextHit] | None,
    backbone_concepts: set[str],
    min_score: float = 0.3,
) -> str | None:
    """Extract the most frequent parent_anchor from historical hits.

    Used to provide prior anchor hints when embedding retrieval
    is unavailable or weak. Only considers anchors that are
    valid backbone concepts and have sufficient score.

    Args:
        hits: List of HistoricalContextHit for a candidate
        backbone_concepts: Set of valid backbone concept labels
        min_score: Minimum hit score to consider (default: 0.3)

    Returns:
        Most common parent_anchor among qualifying hits, or None

    Example:
        >>> hits = [Hit(parent_anchor="Asset", score=0.5), Hit(parent_anchor="Asset", score=0.4)]
        >>> top_historical_parent_anchor(hits, {"Asset", "Component"})
        "Asset"
    """
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
    decisions_by_domain: dict[str, dict[str, AttachmentDecision]],
    historical_context_by_domain: dict[str, dict[str, list[HistoricalContextHit]]],
    domain_graphs: dict[str, DomainGraphArtifacts],
) -> list[MemoryEntry]:
    """Build complete MemoryEntry set for a variant run.

    Creates three types of memory entries:
    1. Evidence entries: From EvidenceRecords
    2. Attachment entries: From accepted AttachmentDecisions with confidence
    3. Snapshot entries: From SnapshotManifests with node/edge delta

    Args:
        variant_id: Variant identifier for memory_id prefix
        run_root: Run directory path for provenance
        records_by_domain: EvidenceRecord dict per domain
        decisions_by_domain: AttachmentDecision dict per domain
        historical_context_by_domain: Retrieved context hits per domain
        domain_graphs: DomainGraphArtifacts per domain

    Returns:
        Combined list of MemoryEntry objects for the run
    """
    entries = build_evidence_memory_entries(records_by_domain)
    run_token = Path(run_root).name if run_root else "run"

    # Build evidence timestamp lookup
    evidence_times = {
        record.evidence_id: record.timestamp
        for records in records_by_domain.values()
        for record in records
    }

    # Build attachment entries for accepted decisions
    for domain_id, decisions in decisions_by_domain.items():
        historical_hits = historical_context_by_domain.get(domain_id, {})
        for decision in decisions.values():
            if not decision.accept:
                continue
            # Only include decisions with sufficient confidence
            if decision.confidence < ATTACHMENT_CONFIDENCE_THRESHOLD:
                continue

            timestamp = min(
                (evidence_times.get(evidence_id) for evidence_id in decision.evidence_ids if evidence_times.get(evidence_id)),
                default="",
            )
            if not timestamp:
                continue

            # Reference top historical hits for provenance
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

    # Build snapshot entries for versioned graph states
    for domain_id, graph in domain_graphs.items():
        previous_nodes: set[str] = set()
        previous_edges: set[str] = set()
        state_by_snapshot = {state.snapshot_id: state for state in graph.snapshot_states}

        for manifest in graph.snapshots:
            state = state_by_snapshot.get(manifest.snapshot_id)
            if state is None:
                continue

            # Track delta from previous snapshot
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


# Additional utility functions for MemoryBank analysis

def count_memory_entries_by_type(entries: list[MemoryEntry]) -> dict[str, int]:
    """Count memory entries by entry_type.

    Args:
        entries: List of MemoryEntry objects

    Returns:
        Dict mapping entry_type to count
    """
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.entry_type] = counts.get(entry.entry_type, 0) + 1
    return counts


def filter_entries_by_domain(
    entries: list[MemoryEntry],
    domain_id: str,
) -> list[MemoryEntry]:
    """Filter memory entries by domain_id.

    Args:
        entries: List of MemoryEntry objects
        domain_id: Domain to filter for

    Returns:
        Filtered list of MemoryEntry objects
    """
    return [entry for entry in entries if entry.domain_id == domain_id]


def filter_entries_by_label(
    entries: list[MemoryEntry],
    label: str,
) -> list[MemoryEntry]:
    """Filter memory entries by label reference.

    Args:
        entries: List of MemoryEntry objects
        label: Label to search for (case-insensitive)

    Returns:
        Filtered list of MemoryEntry objects with matching label
    """
    lowered = label.lower()
    return [
        entry
        for entry in entries
        if any(ref.lower() == lowered for ref in entry.label_refs)
    ]


def get_unique_parent_anchors(entries: list[MemoryEntry]) -> set[str]:
    """Get all unique parent_anchor values from entries.

    Args:
        entries: List of MemoryEntry objects

    Returns:
        Set of unique parent_anchor strings (excluding None)
    """
    return {entry.parent_anchor for entry in entries if entry.parent_anchor}


def summarize_memory_bank(entries: list[MemoryEntry]) -> dict[str, Any]:
    """Generate summary statistics for a MemoryBank.

    Args:
        entries: List of MemoryEntry objects

    Returns:
        Dict with summary statistics including counts, domains, timestamps
    """
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
