#!/usr/bin/env python3
"""Evidence normalization and schema-candidate extraction."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    from crossextend_kg.config import PipelineConfig
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import PipelineConfig
try:
    from crossextend_kg.file_io import load_evidence_records
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import load_evidence_records
try:
    from crossextend_kg.models import EvidenceRecord, EvidenceUnit, SchemaCandidate, SemanticTypeHint
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import EvidenceRecord, EvidenceUnit, SchemaCandidate, SemanticTypeHint
from pipeline.utils import normalize_text


_STEP_ID_PATTERN = re.compile(r"^(T\d+)\b", re.IGNORECASE)
_ASSET_PATTERN = re.compile(r"\b(pack|vehicle|machine|line|cabinet|station|platform|equipment|asset)\b", re.IGNORECASE)
_COMPONENT_PATTERN = re.compile(
    r"\b(module|connector|hose|bracket|clip|plate|bead|window|land|branch|section|interface|end|neck|seat|shell|coupler|component|sensor|pack)\b",
    re.IGNORECASE,
)
_SIGNAL_PATTERN = re.compile(
    r"\b(level|color|wetness|wetting|path|result|height|depth|twist|load|seepage|reading|signal|telemetry)\b",
    re.IGNORECASE,
)
_STATE_PATTERN = re.compile(r"\b(state|condition|boundary|dry|wet)\b", re.IGNORECASE)
_FAULT_PATTERN = re.compile(r"\b(fault|failure|crack|distortion|leak|leakage|anomaly|defect)\b", re.IGNORECASE)
_TRAILING_STABLE_PATTERN = re.compile(r"^(?P<base>.+?)\s+stable$", re.IGNORECASE)
_HANDLE_PROUD_PATTERN = re.compile(r"^(?:orange\s+)?handle\s+sits\s+proud$", re.IGNORECASE)
_HANDLE_FLUSH_PATTERN = re.compile(r"^handle\s+flush(?:ness)?(?:\s+with\b.*)?$", re.IGNORECASE)
_SEMANTIC_TYPE_HINTS: frozenset[str] = frozenset({"Asset", "Component", "Signal", "State", "Fault"})


def load_records_by_domain(config: PipelineConfig) -> dict[str, list[EvidenceRecord]]:
    cache: dict[str, list[EvidenceRecord]] = {}
    records_by_domain: dict[str, list[EvidenceRecord]] = {}
    for domain in config.domains:
        if domain.data_path not in cache:
            cache[domain.data_path] = load_evidence_records(domain.data_path)
        for record in cache[domain.data_path]:
            if record.domain_id == domain.domain_id and record.role != domain.role:
                raise ValueError(
                    f"record role mismatch for domain {domain.domain_id}: "
                    f"expected {domain.role}, got {record.role}"
                )
        records = [
            record
            for record in cache[domain.data_path]
            if record.domain_id == domain.domain_id and record.source_type in domain.source_types
        ]
        records.sort(key=lambda item: item.timestamp)
        records_by_domain[domain.domain_id] = records
    return records_by_domain


def normalize_records_by_domain(records_by_domain: dict[str, list[EvidenceRecord]]) -> dict[str, list[EvidenceRecord]]:
    normalized: dict[str, list[EvidenceRecord]] = {}
    for domain_id, records in records_by_domain.items():
        normalized[domain_id] = [_normalize_record_labels(record) for record in records]
    return normalized


def build_evidence_units(config: PipelineConfig, records_by_domain: dict[str, list[EvidenceRecord]]) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for domain in config.domains:
        for index, record in enumerate(records_by_domain[domain.domain_id]):
            units.append(
                EvidenceUnit(
                    evidence_id=record.evidence_id,
                    domain_id=record.domain_id,
                    role=record.role,
                    source_id=Path(domain.data_path).name,
                    source_type=record.source_type,
                    locator=f"{domain.domain_id}/{record.source_type}/{index}",
                    raw_text=record.raw_text,
                    normalized_text=normalize_text(record.raw_text, config.data.normalize_whitespace),
                    metadata={"timestamp": record.timestamp},
                )
            )
    return units


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _extract_step_id(value: str) -> str | None:
    match = _STEP_ID_PATTERN.match(value.strip())
    if not match:
        return None
    return match.group(1).upper()


def _task_candidate_label(evidence_id: str, step_id: str) -> str:
    return f"{evidence_id}:{step_id}"


def _task_candidate_key(domain_id: str, evidence_id: str, step_id: str) -> tuple[str, str, str, str]:
    return ("task", domain_id, evidence_id, step_id)


def _concept_candidate_key(domain_id: str, label: str) -> tuple[str, str, str]:
    return ("concept", domain_id, label)


def _endpoint_candidate_key(domain_id: str, evidence_id: str, label: str) -> tuple[str, ...]:
    step_id = _extract_step_id(label)
    if step_id:
        return _task_candidate_key(domain_id, evidence_id, step_id)
    return _concept_candidate_key(domain_id, label)


def _canonicalize_runtime_label(label: str) -> str:
    compact = " ".join(str(label).split())
    if not compact or _extract_step_id(compact):
        return compact

    lower = compact.lower()
    if lower == "service-disconnect":
        return "service disconnect"
    if _HANDLE_PROUD_PATTERN.match(compact):
        return "handle proud"
    if _HANDLE_FLUSH_PATTERN.match(compact):
        return "handle flushness"

    stable_match = _TRAILING_STABLE_PATTERN.match(compact)
    if stable_match:
        base = stable_match.group("base").strip()
        if any(keyword in base.lower() for keyword in ("status", "path", "permissive")):
            return base
    return compact


def _normalize_record_labels(record: EvidenceRecord) -> EvidenceRecord:
    for mention in record.document_concept_mentions:
        mention.label = _canonicalize_runtime_label(mention.label)
    for relation in record.document_relation_mentions:
        relation.head = _canonicalize_runtime_label(relation.head)
        relation.tail = _canonicalize_runtime_label(relation.tail)

    for step_record in record.step_records:
        step_record.task.label = _canonicalize_runtime_label(step_record.task.label)
        for mention in step_record.concept_mentions:
            mention.label = _canonicalize_runtime_label(mention.label)
        for relation in step_record.relation_mentions:
            relation.head = _canonicalize_runtime_label(relation.head)
            relation.tail = _canonicalize_runtime_label(relation.tail)
    return record


def _normalize_semantic_type_hint(value: str | None) -> SemanticTypeHint | None:
    if not isinstance(value, str):
        return None
    compact = value.strip()
    if compact in _SEMANTIC_TYPE_HINTS:
        return compact  # type: ignore[return-value]
    mapping: dict[str, SemanticTypeHint] = {
        "asset": "Asset",
        "component": "Component",
        "signal": "Signal",
        "state": "State",
        "fault": "Fault",
    }
    return mapping.get(compact.lower())


def _fallback_semantic_type_hint_candidates(label: str, description: str) -> list[str]:
    text = f"{label} {description}"
    hints: list[str] = []
    if _FAULT_PATTERN.search(text):
        hints.append("Fault")
    if _SIGNAL_PATTERN.search(text):
        hints.append("Signal")
    if _STATE_PATTERN.search(text):
        hints.append("State")
    if _COMPONENT_PATTERN.search(text):
        hints.append("Component")
    if _ASSET_PATTERN.search(text):
        hints.append("Asset")
    return hints


def aggregate_schema_candidates(
    records_by_domain: dict[str, list[EvidenceRecord]],
    *,
    assume_normalized: bool = False,
) -> dict[str, list[SchemaCandidate]]:
    grouped: dict[tuple[str, ...], dict] = {}
    descriptions: dict[tuple[str, ...], list[str]] = defaultdict(list)
    relation_participation: Counter[tuple[str, ...]] = Counter()
    relation_head_participation: Counter[tuple[str, ...]] = Counter()
    relation_tail_participation: Counter[tuple[str, ...]] = Counter()
    relation_families: dict[tuple[str, ...], set[str]] = defaultdict(set)
    step_ids_by_candidate: dict[tuple[str, ...], set[str]] = defaultdict(set)
    semantic_hint_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)

    for domain_id, records in records_by_domain.items():
        for record in records:
            if not assume_normalized:
                record = _normalize_record_labels(record)
            for relation in record.relation_mentions:
                head_key = _endpoint_candidate_key(domain_id, record.evidence_id, relation.head)
                tail_key = _endpoint_candidate_key(domain_id, record.evidence_id, relation.tail)
                relation_participation[head_key] += 1
                relation_participation[tail_key] += 1
                relation_head_participation[head_key] += 1
                relation_tail_participation[tail_key] += 1
                relation_families[head_key].add(relation.family)
                relation_families[tail_key].add(relation.family)

            for step_record in record.step_records:
                key = _task_candidate_key(domain_id, record.evidence_id, step_record.step_id)
                scoped_label = _task_candidate_label(record.evidence_id, step_record.step_id)
                grouped.setdefault(
                    key,
                    {
                        "candidate_id": f"{domain_id}::{scoped_label}",
                        "domain_id": domain_id,
                        "role": record.role,
                        "label": scoped_label,
                        "description": "",
                        "evidence_ids": [],
                        "evidence_texts": [],
                        "routing_features": {},
                        "_is_task_candidate": True,
                        "_task_step_id": step_record.step_id,
                        "_task_evidence_id": record.evidence_id,
                        "_task_surface_form": step_record.task.surface_form,
                    },
                )
                _append_unique(grouped[key]["evidence_ids"], record.evidence_id)
                _append_unique(grouped[key]["evidence_texts"], step_record.task.surface_form)

                for mention in step_record.concept_mentions:
                    if not mention.node_worthy:
                        continue
                    concept_key = _concept_candidate_key(domain_id, mention.label)
                    grouped.setdefault(
                        concept_key,
                        {
                            "candidate_id": f"{domain_id}::{mention.label}",
                            "domain_id": domain_id,
                            "role": record.role,
                            "label": mention.label,
                            "description": mention.description,
                            "evidence_ids": [],
                            "evidence_texts": [],
                            "routing_features": {},
                            "_is_task_candidate": False,
                        },
                    )
                    _append_unique(grouped[concept_key]["evidence_ids"], record.evidence_id)
                    _append_unique(grouped[concept_key]["evidence_texts"], mention.surface_form or mention.label)
                    if mention.description:
                        descriptions[concept_key].append(mention.description)
                    step_ids_by_candidate[concept_key].add(step_record.step_id)
                    explicit_hint = _normalize_semantic_type_hint(mention.semantic_type_hint)
                    if explicit_hint is not None:
                        semantic_hint_counts[concept_key][explicit_hint] += 1
                    else:
                        for hint in _fallback_semantic_type_hint_candidates(mention.label, mention.description):
                            semantic_hint_counts[concept_key][hint] += 1

            for mention in record.document_concept_mentions:
                if not mention.node_worthy:
                    continue
                key = _concept_candidate_key(domain_id, mention.label)
                grouped.setdefault(
                    key,
                    {
                        "candidate_id": f"{domain_id}::{mention.label}",
                        "domain_id": domain_id,
                        "role": record.role,
                        "label": mention.label,
                        "description": mention.description,
                        "evidence_ids": [],
                        "evidence_texts": [],
                        "routing_features": {},
                        "_is_task_candidate": False,
                    },
                )
                _append_unique(grouped[key]["evidence_ids"], record.evidence_id)
                _append_unique(grouped[key]["evidence_texts"], mention.surface_form or mention.label)
                if mention.description:
                    descriptions[key].append(mention.description)
                explicit_hint = _normalize_semantic_type_hint(mention.semantic_type_hint)
                if explicit_hint is not None:
                    semantic_hint_counts[key][explicit_hint] += 1
                else:
                    for hint in _fallback_semantic_type_hint_candidates(mention.label, mention.description):
                        semantic_hint_counts[key][hint] += 1

    results: dict[str, list[SchemaCandidate]] = {domain_id: [] for domain_id in records_by_domain}
    for key, item in grouped.items():
        description = Counter(descriptions[key]).most_common(1)[0][0] if descriptions[key] else item["description"]
        item["description"] = description
        hint_counts = semantic_hint_counts[key]
        dominant_hint = None
        hint_candidates: list[str] = []
        if hint_counts:
            top_count = max(hint_counts.values())
            hint_candidates = sorted([hint for hint, count in hint_counts.items() if count == top_count])
            if len(hint_candidates) == 1:
                dominant_hint = hint_candidates[0]

        routing_features = {
            "evidence_count": len(item["evidence_ids"]),
            "relation_participation_count": relation_participation[key],
            "relation_head_count": relation_head_participation[key],
            "relation_tail_count": relation_tail_participation[key],
            "relation_families": sorted(relation_families[key]),
            "step_ids": sorted(step_ids_by_candidate[key]),
            "semantic_type_hint": dominant_hint,
            "semantic_type_hint_candidates": hint_candidates,
            "support_count": len(item["evidence_ids"]),
            "is_task_candidate": bool(item.pop("_is_task_candidate", False)),
        }
        task_step_id = item.pop("_task_step_id", "")
        task_evidence_id = item.pop("_task_evidence_id", "")
        task_surface_form = item.pop("_task_surface_form", "")
        if task_step_id:
            routing_features["task_step_id"] = task_step_id
            routing_features["task_evidence_id"] = task_evidence_id
            routing_features["task_surface_form"] = task_surface_form
        item["routing_features"] = routing_features
        results[item["domain_id"]].append(SchemaCandidate.model_validate(item))

    for domain_id in results:
        results[domain_id].sort(key=lambda candidate: candidate.label)
    return results
