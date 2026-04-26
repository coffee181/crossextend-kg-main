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
    from crossextend_kg.models import EvidenceRecord, EvidenceUnit, SchemaCandidate, SemanticTypeHint, SharedHypernym
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import EvidenceRecord, EvidenceUnit, SchemaCandidate, SemanticTypeHint, SharedHypernym
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
_SHARED_HYPONYM_MAP: dict[str, SharedHypernym] = {
    "seal": "Seal",
    "connector": "Connector",
    "sensor": "Sensor",
    "controller": "Controller",
    "coolant": "Coolant",
    "actuator": "Actuator",
    "power": "Power",
    "housing": "Housing",
    "fastener": "Fastener",
    "media": "Media",
}


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


def _concept_candidate_key(domain_id: str, label: str) -> tuple[str, str, str]:
    return ("concept", domain_id, label)


def _endpoint_candidate_key(domain_id: str, evidence_id: str, label: str) -> tuple[str, ...]:
    return _concept_candidate_key(domain_id, label)


_IRREGULAR_PLURALS = {
    "indices": "index",
    "axes": "axis",
    "vertices": "vertex",
    "analyses": "analysis",
    "diagnoses": "diagnosis",
}

# Words that look plural but are actually singular in O&M context
_KEEP_AS_IS = frozenset({
    "busbar edges", "busbar edge",  # compound — don't strip 'edge'
})


def _to_singular(label: str) -> str:
    """Convert a label to singular form for canonical matching.

    Rules follow the attachment_gold_annotation_spec.md:
    - strip trailing 's' (but not 'ss' or 'us')
    - strip trailing 'es'
    - convert trailing 'ies' to 'y'
    - irregular plurals
    - named entities with IDs (e.g. HC-S1) are preserved
    - step IDs (e.g. T1) are preserved
    """
    if not label:
        return label
    # Preserve step IDs and named entity IDs
    if _extract_step_id(label):
        return label
    lower = label.lower()
    # Named entities with alphanumeric IDs: keep as-is
    if re.search(r"[A-Z]+-\d+", label):
        return label
    # Compound terms that should stay as-is
    if lower in _KEEP_AS_IS:
        return label
    # Check irregular
    words = lower.split()
    last = words[-1] if words else ""
    if last in _IRREGULAR_PLURALS:
        words[-1] = _IRREGULAR_PLURALS[last]
        return " ".join(words)
    # Regular plurals — only apply to the last word
    if len(last) > 2:
        if last.endswith("ies") and len(last) > 4:
            words[-1] = last[:-3] + "y"
            return " ".join(words)
        if last.endswith("es") and not last.endswith("ss") and not last.endswith("se"):
            words[-1] = last[:-2]
            return " ".join(words)
        if last.endswith("s") and not last.endswith("ss") and not last.endswith("us") and not last.endswith("is"):
            words[-1] = last[:-1]
            return " ".join(words)
    return label


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
            return _to_singular(base)
    return _to_singular(compact)


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
        # Normalize v2 fields
        for action in step_record.step_actions:
            action.target_label = _canonicalize_runtime_label(action.target_label)
        for s_edge in step_record.structural_edges:
            s_edge.head = _canonicalize_runtime_label(s_edge.head)
            s_edge.tail = _canonicalize_runtime_label(s_edge.tail)
        for d_edge in step_record.diagnostic_edges:
            d_edge.evidence_label = _canonicalize_runtime_label(d_edge.evidence_label)
            d_edge.indicated_label = _canonicalize_runtime_label(d_edge.indicated_label)
        for st in step_record.state_transitions:
            st.from_state = _canonicalize_runtime_label(st.from_state)
            st.to_state = _canonicalize_runtime_label(st.to_state)
            if st.evidence_label:
                st.evidence_label = _canonicalize_runtime_label(st.evidence_label)
    # Normalize cross_step_relations
    for csr in record.cross_step_relations:
        csr.head = _canonicalize_runtime_label(csr.head)
        csr.tail = _canonicalize_runtime_label(csr.tail)
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


def _dominant_hypernym(counts: Counter[str]) -> str | None:
    if not counts:
        return None
    top_count = max(counts.values())
    top_items = sorted([item for item, count in counts.items() if count == top_count])
    return top_items[0] if len(top_items) == 1 else None


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
    hypernym_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)

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
                    if mention.shared_hypernym:
                        hypernym_counts[concept_key][mention.shared_hypernym] += 1

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
                if mention.shared_hypernym:
                    hypernym_counts[key][mention.shared_hypernym] += 1

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
            "shared_hypernym": _dominant_hypernym(hypernym_counts[key]),
        }
        item["routing_features"] = routing_features
        results[item["domain_id"]].append(SchemaCandidate.model_validate(item))

    for domain_id in results:
        results[domain_id].sort(key=lambda candidate: candidate.label)
    return results
