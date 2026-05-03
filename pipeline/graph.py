#!/usr/bin/env python3
"""Schema materialization, graph assembly, and snapshot creation."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass

try:
    from crossextend_kg.config import PipelineConfig, VariantConfig
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import PipelineConfig, VariantConfig
try:
    from crossextend_kg.models import (
        AdapterConcept,
        CandidateTriple,
        DomainGraphArtifacts,
        DomainSchema,
        GraphEdge,
        GraphNode,
        LifecycleEvent,
        SchemaCandidate,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import (
        AdapterConcept,
        CandidateTriple,
        DomainGraphArtifacts,
        DomainSchema,
        GraphEdge,
        GraphNode,
        LifecycleEvent,
        SchemaCandidate,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )
from pipeline.relation_validation import load_relation_constraints, validate_edge
from rules.relation_filtering import filter_relation_mention

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphRelationInput:
    label: str
    family: str
    head: str
    tail: str
    source_field: str | None = None
    head_step: str | None = None
    tail_step: str | None = None
    mechanism: str | None = None
    evidence_label: str | None = None

_STRUCTURAL_CONTEXTUAL_HEAD_PATTERN = re.compile(
    r"\b(branch|path|condition|state|section|geometry|position|circuit|loop|face|surface|interface|cavity|pocket|edge)\b",
    re.IGNORECASE,
)
_STEP_SUMMARY_PREFIX_PATTERN = re.compile(r"^(?:for|on|at)\s+[^,]+,\s*", re.IGNORECASE)
_STEP_SUMMARY_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-./]*")
_STEP_SUMMARY_SPLITTERS = (
    ".",
    ";",
    ",",
    " while ",
    " because ",
    " so ",
    " then ",
    " before ",
    " after ",
)
_WORKFLOW_DISPLAY_ACTIONS = ("record", "inspect", "measure", "expose", "compare", "repair", "verify", "remove")
_WORKFLOW_ACTION_LOOKUP = {
    "record": "record",
    "records": "record",
    "capture": "record",
    "captures": "record",
    "document": "record",
    "documents": "record",
    "note": "record",
    "notes": "record",
    "log": "record",
    "logs": "record",
    "inspect": "inspect",
    "inspects": "inspect",
    "inspection": "inspect",
    "observe": "inspect",
    "observes": "inspect",
    "check": "inspect",
    "checks": "inspect",
    "review": "inspect",
    "reviews": "inspect",
    "watch": "inspect",
    "watches": "inspect",
    "examine": "inspect",
    "examines": "inspect",
    "identify": "inspect",
    "identifies": "inspect",
    "trace": "inspect",
    "traces": "inspect",
    "measure": "measure",
    "measures": "measure",
    "measurement": "measure",
    "gauge": "measure",
    "gauges": "measure",
    "quantify": "measure",
    "quantifies": "measure",
    "expose": "expose",
    "exposes": "expose",
    "exposure": "expose",
    "open": "expose",
    "opens": "expose",
    "access": "expose",
    "accesses": "expose",
    "uncover": "expose",
    "uncovers": "expose",
    "isolate": "expose",
    "isolates": "expose",
    "safe": "expose",
    "lift": "expose",
    "compare": "compare",
    "compares": "compare",
    "comparison": "compare",
    "compares with": "compare",
    "compares_with": "compare",
    "align": "compare",
    "aligns": "compare",
    "match": "compare",
    "matches": "compare",
    "repair": "repair",
    "repairs": "repair",
    "replacement": "repair",
    "replace": "repair",
    "replaces": "repair",
    "reseat": "repair",
    "reseats": "repair",
    "reset": "repair",
    "resets": "repair",
    "correct": "repair",
    "corrects": "repair",
    "refit": "repair",
    "refits": "repair",
    "install": "repair",
    "installs": "repair",
    "installs on": "repair",
    "installs_on": "repair",
    "renew": "repair",
    "renews": "repair",
    "restore": "repair",
    "restores": "repair",
    "torque": "repair",
    "torques": "repair",
    "tighten": "repair",
    "tightens": "repair",
    "lubricate": "repair",
    "lubricates": "repair",
    "verify": "verify",
    "verifies": "verify",
    "verification": "verify",
    "validation": "verify",
    "confirm": "verify",
    "confirms": "verify",
    "validate": "verify",
    "validates": "verify",
    "prove": "verify",
    "proves": "verify",
    "test": "verify",
    "tests": "verify",
    "pressure-test": "verify",
    "pressure-tests": "verify",
    "circulate": "verify",
    "circulates": "verify",
    "monitor": "verify",
    "monitors": "verify",
    "release": "verify",
    "remove": "remove",
    "removes": "remove",
    "removal": "remove",
    "detach": "remove",
    "detaches": "remove",
}
_WEAK_WORKFLOW_RELATION_LABELS = {
    "allows",
    "allow",
    "holds",
    "hold",
    "keeps",
    "keep",
    "leaves",
    "leave",
    "names",
    "name",
    "marks",
    "mark",
    "performed on",
    "performed_on",
    "pays attention to",
    "pays_attention_to",
    "requires",
    "require",
    "runs",
    "run",
    "targets",
    "target",
}
_WORKFLOW_GENERIC_CONTEXT_PATTERN = re.compile(r"\b(branch|path|history|context|process|cycle)\b", re.IGNORECASE)
_WORKFLOW_LABEL_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.IGNORECASE)


def _task_candidate_label(evidence_id: str, step_id: str) -> str:
    return f"{evidence_id}:{step_id}"


def _extract_step_id(value: str) -> str | None:
    value = value.strip()
    if not value.startswith("T"):
        return None
    digits = value[1:].split(None, 1)[0]
    if digits.isdigit():
        return f"T{digits}"
    return None


def _candidate_id_from_endpoint(domain_id: str, evidence_id: str, endpoint: str) -> str:
    step_id = _extract_step_id(endpoint)
    if step_id:
        return f"{domain_id}::{_task_candidate_label(evidence_id, step_id)}"
    return f"{domain_id}::{endpoint}"


def _resolve_record_task_label(record_evidence_id: str, endpoint: str) -> str:
    step_id = _extract_step_id(endpoint)
    if not step_id:
        return endpoint
    return _task_candidate_label(record_evidence_id, step_id)


def _normalize_space(value: str) -> str:
    return " ".join(str(value).split())


def _truncate_step_summary(summary: str, *, max_words: int = 10, max_chars: int = 72) -> str:
    words = _STEP_SUMMARY_WORD_PATTERN.findall(summary)
    if not words:
        return ""
    truncated_words: list[str] = []
    for word in words:
        candidate = " ".join(truncated_words + [word])
        if truncated_words and (len(truncated_words) >= max_words or len(candidate) > max_chars):
            break
        truncated_words.append(word)
        if len(" ".join(truncated_words)) >= max_chars:
            break
    return " ".join(truncated_words)


def _step_order_index(step_id: str, fallback_index: int) -> int:
    extracted = _extract_step_id(step_id)
    if extracted is None:
        return fallback_index
    return int(extracted[1:])


def _step_sequence_edges(step_record) -> list[tuple[str, str]]:
    """Return sequence edges from the authoritative v2 ``sequence_next`` field."""
    step_id = step_record.step_id
    if step_record.sequence_next:
        return [(step_id, step_record.sequence_next)]
    return []


def _step_action_edges(step_record) -> list[tuple[str, str, str]]:
    """Return action-object edges from the authoritative v2 ``step_actions`` field."""
    return [(sa.action_type, sa.target_label, sa.action_type) for sa in step_record.step_actions]


def _step_structural_edges(step_record) -> list[tuple[str, str, str]]:
    """Return (label, head, tail) tuples for structural edges.

    Prefers v2 ``structural_edges`` when populated; falls back to
    ``structural`` relations in ``relation_mentions``.
    """
    if step_record.structural_edges:
        return [(se.label, se.head, se.tail) for se in step_record.structural_edges]
    edges: list[tuple[str, str, str]] = []
    for relation in step_record.relation_mentions:
        if relation.family == "structural":
            edges.append((relation.label, relation.head, relation.tail))
    return edges


def _step_summary_source(step_record) -> str:
    # v2: prefer independent surface_form or step_summary
    v2_surface = _normalize_space(getattr(step_record, "surface_form", ""))
    if v2_surface and v2_surface.lower() != step_record.step_id.lower():
        return v2_surface
    v2_summary = _normalize_space(getattr(step_record, "step_summary", ""))
    if v2_summary and v2_summary.lower() != step_record.step_id.lower():
        return v2_summary
    description = _normalize_space(step_record.task.description)
    if description and description.lower() != step_record.step_id.lower():
        return description
    surface_form = _normalize_space(step_record.task.surface_form)
    if surface_form:
        return surface_form
    return _normalize_space(step_record.task.label)


def _normalize_relation_phrase(value: str) -> str:
    return _normalize_space(str(value).replace("_", " ").replace("/", " ")).lower()


def _canonical_action_from_phrase(value: str) -> str | None:
    normalized = _normalize_relation_phrase(value)
    if not normalized:
        return None
    if normalized in _WEAK_WORKFLOW_RELATION_LABELS:
        return None
    if normalized in _WORKFLOW_ACTION_LOOKUP:
        return _WORKFLOW_ACTION_LOOKUP[normalized]
    for token in _WORKFLOW_LABEL_TOKEN_PATTERN.findall(normalized):
        canonical = _WORKFLOW_ACTION_LOOKUP.get(token)
        if canonical:
            return canonical
    return None


def _sentence_case(value: str) -> str:
    compact = value.strip()
    if not compact:
        return ""
    return compact[:1].upper() + compact[1:]


def _step_summary_text(step_record) -> str:
    source = _step_summary_source(step_record)
    if not source:
        return ""

    summary = _STEP_SUMMARY_PREFIX_PATTERN.sub("", source, count=1).strip()
    lowered = summary.lower()
    split_points = [lowered.find(splitter) for splitter in _STEP_SUMMARY_SPLITTERS if lowered.find(splitter) > 0]
    if split_points:
        summary = summary[: min(split_points)].strip()
    return summary


def _canonical_step_action(step_record) -> str | None:
    # v2: if step_phase is set, derive action from it
    step_phase = getattr(step_record, "step_phase", None)
    if step_phase == "observe":
        summary = _normalize_relation_phrase(_step_summary_text(step_record))
        if summary:
            action = _canonical_action_from_phrase(summary)
            if action in ("record", "inspect", "measure", "expose", "compare"):
                return action
        return "inspect"
    if step_phase == "diagnose":
        summary = _normalize_relation_phrase(_step_summary_text(step_record))
        if summary:
            action = _canonical_action_from_phrase(summary)
            if action:
                return action
        return "compare"
    if step_phase == "repair":
        summary = _normalize_relation_phrase(_step_summary_text(step_record))
        if summary:
            action = _canonical_action_from_phrase(summary)
            if action in ("repair", "remove", "expose"):
                return action
        return "repair"
    if step_phase == "verify":
        return "verify"

    summary = _normalize_relation_phrase(_step_summary_text(step_record))
    if not summary:
        return None
    if "pressure hold" in summary or "proof cycle" in summary:
        return "verify"
    if "time to first" in summary:
        return "measure"
    return _canonical_action_from_phrase(summary)


def _step_tail_anchor_map(step_record) -> dict[str, str | None]:
    return {
        mention.label: mention.semantic_type_hint
        for mention in step_record.concept_mentions
    }


def _workflow_display_action(
    *,
    raw_label: str,
    step_action: str | None,
    tail_anchor: str | None,
) -> str | None:
    raw_action = _canonical_action_from_phrase(raw_label)
    if raw_action == "inspect" and step_action in {"record", "verify"} and tail_anchor in {"Signal", "State", "Fault"}:
        return step_action
    if raw_action == "record" and step_action == "verify" and tail_anchor in {"Signal", "State", "Fault"}:
        return "verify"
    if raw_action in _WORKFLOW_DISPLAY_ACTIONS:
        return raw_action
    if step_action in _WORKFLOW_DISPLAY_ACTIONS:
        return step_action
    return None


def _workflow_edge_display_policy(
    *,
    raw_label: str,
    display_action: str | None,
    tail_label: str,
    tail_anchor: str | None,
) -> tuple[str, bool, str | None]:
    if not display_action:
        return ("low", False, "unsupported_workflow_action")

    normalized_raw = _normalize_relation_phrase(raw_label)
    normalized_tail = _normalize_relation_phrase(tail_label)
    is_weak_raw = normalized_raw in _WEAK_WORKFLOW_RELATION_LABELS

    if tail_anchor == "Asset":
        return ("low", False, "workflow_asset_context")

    if is_weak_raw:
        if (
            display_action in {"expose", "remove", "repair"}
            and tail_anchor == "Component"
            and not _WORKFLOW_GENERIC_CONTEXT_PATTERN.search(normalized_tail)
        ):
            return ("medium", True, None)
        if display_action == "verify" and tail_anchor in {"State", "Fault"}:
            return ("medium", True, None)
        return ("low", False, "weak_workflow_relation")

    if display_action == "record":
        if tail_anchor in {"Signal", "State", "Fault"}:
            return ("high", True, None)
        return ("low", False, "record_requires_signal_like_target")

    if display_action == "inspect":
        if tail_anchor in {"Signal", "Component", "State", "Fault"}:
            return ("high", True, None)
        return ("low", False, "inspect_requires_grounded_target")

    if display_action == "measure":
        if tail_anchor in {"Signal", "Component", "State"}:
            return ("high", True, None)
        return ("low", False, "measure_requires_grounded_target")

    if display_action == "compare":
        if tail_anchor in {"Signal", "Component", "State"}:
            return ("medium", True, None)
        return ("low", False, "compare_requires_grounded_target")

    if display_action in {"expose", "remove", "repair"}:
        if tail_anchor == "Component":
            return ("high", True, None)
        if display_action == "repair" and tail_anchor in {"State", "Fault"}:
            return ("medium", True, None)
        return ("low", False, f"{display_action}_requires_component_target")

    if display_action == "verify":
        if tail_anchor in {"State", "Fault"}:
            return ("high", True, None)
        if tail_anchor in {"Signal", "Component"}:
            return ("medium", True, None)
        return ("low", False, "verify_requires_grounded_target")

    return ("low", False, "unsupported_workflow_action")


def _default_step_object_phrase(action: str, dominant_anchor: str | None) -> str:
    if action == "record":
        return "issue evidence"
    if action == "inspect":
        if dominant_anchor == "Component":
            return "critical components"
        if dominant_anchor in {"State", "Fault"}:
            return "fault boundary"
        return "key evidence"
    if action == "measure":
        return "critical dimensions"
    if action == "expose":
        return "local assembly"
    if action == "compare":
        return "reference dimensions"
    if action == "repair":
        return "failed interface"
    if action == "verify":
        return "repair outcome"
    if action == "remove":
        return "access cover"
    return "workflow step"


def _build_step_display_label(step_record) -> str:
    step_action = _canonical_step_action(step_record)
    tail_anchor_map = _step_tail_anchor_map(step_record)
    candidate_edges: list[tuple[int, str, str | None, str]] = []

    for relation in step_record.relation_mentions:
        if _extract_step_id(relation.head) != _extract_step_id(step_record.step_id):
            continue
        display_action = _workflow_display_action(
            raw_label=relation.label,
            step_action=step_action,
            tail_anchor=tail_anchor_map.get(relation.tail),
        )
        salience, admitted, _ = _workflow_edge_display_policy(
            raw_label=relation.label,
            display_action=display_action,
            tail_label=relation.tail,
            tail_anchor=tail_anchor_map.get(relation.tail),
        )
        if not admitted or not display_action:
            continue
        salience_rank = {"high": 0, "medium": 1, "low": 2}[salience]
        candidate_edges.append((salience_rank, display_action, tail_anchor_map.get(relation.tail), relation.tail))

    chosen_action = step_action or (candidate_edges[0][1] if candidate_edges else None)
    if not chosen_action:
        fallback = _truncate_step_summary(_step_summary_text(step_record))
        if not fallback:
            return step_record.step_id
        return f"{fallback} ({step_record.step_id})"

    candidate_edges.sort(key=lambda item: (item[0], item[1] != chosen_action, len(item[3]), item[3]))
    matching_tails = [item for item in candidate_edges if item[1] == chosen_action]
    dominant_anchor = matching_tails[0][2] if matching_tails else (candidate_edges[0][2] if candidate_edges else None)

    if len(matching_tails) == 1:
        object_phrase = matching_tails[0][3]
    elif len(matching_tails) > 1:
        object_phrase = _default_step_object_phrase(chosen_action, dominant_anchor)
    else:
        object_phrase = _default_step_object_phrase(chosen_action, dominant_anchor)

    summary = f"{_sentence_case(chosen_action)} {object_phrase}"
    return f"{summary} ({step_record.step_id})"


def _node_semantic_type(node: GraphNode) -> str | None:
    if node.node_type == "backbone_concept":
        return node.label
    if node.node_type == "workflow_step":
        return "Task"
    return node.parent_anchor


def _dedupe_relation_mentions(relations):
    seen: set[tuple[str, str, str, str]] = set()
    deduped = []
    for relation in relations:
        key = (relation.label, relation.family, relation.head, relation.tail)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def _normalize_document_relations(
    relations,
    node_anchor_map: dict[str, str | None],
):
    _ = node_anchor_map
    return _dedupe_relation_mentions(relations)


def _record_workflow_relation_inputs(record) -> list[GraphRelationInput]:
    relation_inputs: list[GraphRelationInput] = []
    for step_record in record.step_records:
        for head_step, tail_step in _step_sequence_edges(step_record):
            relation_inputs.append(
                GraphRelationInput(
                    label="triggers",
                    family="task_dependency",
                    head=head_step,
                    tail=tail_step,
                    source_field="sequence_next",
                    head_step=head_step,
                    tail_step=tail_step,
                )
            )
        for action_type, target_label, raw_label in _step_action_edges(step_record):
            relation_inputs.append(
                GraphRelationInput(
                    label=raw_label,
                    family="task_dependency",
                    head=step_record.step_id,
                    tail=target_label,
                    source_field="step_actions",
                    head_step=step_record.step_id,
                )
            )
    return relation_inputs


def _record_v2_semantic_relation_inputs(record) -> list[GraphRelationInput]:
    relation_inputs: list[GraphRelationInput] = []
    for step_record in record.step_records:
        for label, head, tail in _step_structural_edges(step_record):
            relation_inputs.append(
                GraphRelationInput(
                    label=label,
                    family="structural",
                    head=head,
                    tail=tail,
                    source_field="structural_edges",
                    head_step=step_record.step_id,
                    tail_step=step_record.step_id,
                )
            )
        for diagnostic_edge in step_record.diagnostic_edges:
            mechanism = diagnostic_edge.mechanism or "communication"
            if mechanism not in {"communication", "propagation"}:
                mechanism = "communication"
            relation_inputs.append(
                GraphRelationInput(
                    label="indicates" if mechanism == "communication" else "causes",
                    family=mechanism,
                    head=diagnostic_edge.evidence_label,
                    tail=diagnostic_edge.indicated_label,
                    source_field="diagnostic_edges",
                    head_step=step_record.step_id,
                    tail_step=step_record.step_id,
                    mechanism=mechanism,
                    evidence_label=diagnostic_edge.evidence_label,
                )
            )
        for state_transition in step_record.state_transitions:
            relation_inputs.append(
                GraphRelationInput(
                    label="transitionsTo",
                    family="lifecycle",
                    head=state_transition.from_state,
                    tail=state_transition.to_state,
                    source_field="state_transitions",
                    head_step=state_transition.trigger_step or step_record.step_id,
                    tail_step=step_record.step_id,
                    evidence_label=state_transition.evidence_label,
                )
            )
    return relation_inputs


def _relation_input_from_mention(relation, source_field: str) -> GraphRelationInput:
    return GraphRelationInput(
        label=relation.label,
        family=relation.family,
        head=relation.head,
        tail=relation.tail,
        source_field=source_field,
    )


def _cross_step_metadata(record) -> dict[tuple[str, str, str, str], object]:
    metadata: dict[tuple[str, str, str, str], object] = {}
    for relation in record.cross_step_relations:
        key = (relation.head, relation.label, relation.family, relation.tail)
        metadata[key] = relation
    return metadata


def _ensure_adapter_anchor_edge(
    *,
    edge_map: OrderedDict[str, GraphEdge],
    domain_id: str,
    label: str,
    parent_anchor: str | None,
    evidence_id: str,
    timestamp: str,
    write_temporal_metadata: bool,
    new_edge_ids: list[str],
    first_observation_time: dict[str, str],
) -> None:
    if not parent_anchor:
        return
    edge_id = f"{domain_id}::edge::{label}::is_a::{parent_anchor}"
    if edge_id not in edge_map:
        edge_map[edge_id] = GraphEdge(
            edge_id=edge_id,
            domain_id=domain_id,
            label="is_a",
            raw_label="is_a",
            display_label="is_a",
            family="is_a",
            edge_layer="semantic",
            edge_salience="medium",
            display_admitted=True,
            head=label,
            tail=parent_anchor,
            source_field="attachment_decision",
            provenance_evidence_ids=[evidence_id],
            valid_from=timestamp if write_temporal_metadata else None,
        )
        new_edge_ids.append(edge_id)
        first_observation_time[edge_id] = timestamp
    elif evidence_id not in edge_map[edge_id].provenance_evidence_ids:
        edge_map[edge_id].provenance_evidence_ids.append(evidence_id)


def _build_record_step_support(record) -> dict[str, set[str]]:
    support: dict[str, set[str]] = {}
    for step_record in record.step_records:
        step_id = _extract_step_id(step_record.step_id) or step_record.step_id
        if not step_id:
            continue
        for mention in step_record.concept_mentions:
            label = _normalize_space(mention.label)
            if label:
                support.setdefault(label, set()).add(step_id)
        for relation in step_record.relation_mentions:
            for endpoint in (relation.head, relation.tail):
                label = _normalize_space(endpoint)
                if not label or _extract_step_id(label):
                    continue
                support.setdefault(label, set()).add(step_id)
    return support


def _document_semantic_reject_reason(
    *,
    relation_origin: str,
    relation_family: str,
    head: str,
    tail: str,
    concept_step_support: dict[str, set[str]],
) -> str | None:
    if relation_origin != "document" or relation_family not in {"communication", "propagation", "lifecycle"}:
        return None

    head_steps = concept_step_support.get(head, set())
    tail_steps = concept_step_support.get(tail, set())
    if not head_steps or not tail_steps:
        return "document_semantic_requires_step_grounding"

    if len(head_steps | tail_steps) == 1:
        return "single_step_diagnostic_hypothesis"

    return None


def _classify_task_dependency(
    *,
    head_in_graph: bool,
    tail_in_graph: bool,
    head_layer: str | None,
    tail_layer: str | None,
    raw_head: str,
    raw_tail: str,
) -> tuple[str, str | None, str | None]:
    if _extract_step_id(raw_head) and _extract_step_id(raw_tail):
        return ("workflow", "sequence", None)
    if _extract_step_id(raw_head):
        return ("workflow", "action_object", None)
    if not head_in_graph or not tail_in_graph:
        return ("semantic", None, None)
    if head_layer == "workflow" and tail_layer == "workflow":
        return ("workflow", "sequence", None)
    if head_layer == "workflow" and tail_layer == "semantic":
        return ("workflow", "action_object", None)
    if head_layer == "semantic" and tail_layer == "workflow":
        return ("semantic", None, "semantic_to_workflow_not_allowed")
    return ("semantic", None, "task_dependency_requires_workflow_head")


def _semantic_edge_display_policy(family: str) -> tuple[str, bool, str | None]:
    if family in {"communication", "propagation", "lifecycle"}:
        return ("high", True, None)
    if family == "structural":
        return ("medium", True, None)
    return ("low", True, None)


def build_domain_schemas(
    config: PipelineConfig,
    candidates_by_domain: dict[str, list[SchemaCandidate]],
    decisions_by_domain,
    backbone_concepts: list[str],
) -> dict[str, DomainSchema]:
    schemas: dict[str, DomainSchema] = {}
    backbone_set = set(backbone_concepts)
    for domain_id, candidates in candidates_by_domain.items():
        schema = DomainSchema(
            domain_id=domain_id,
            backbone_concepts=list(backbone_concepts),
        )
        for candidate in candidates:
            if candidate.label in backbone_set:
                continue
            decision = decisions_by_domain[domain_id][candidate.candidate_id]
            if not decision.admit_as_node:
                continue
            if decision.route == "vertical_specialize":
                schema.adapter_concepts.append(
                    AdapterConcept(
                        label=candidate.label,
                        parent_anchor=decision.parent_anchor,
                        description=candidate.description,
                        evidence_ids=list(candidate.evidence_ids),
                    )
                )
        schema.adapter_concepts.sort(key=lambda item: item.label)
        schemas[domain_id] = schema
    return schemas


def assemble_domain_graphs(
    config: PipelineConfig,
    variant: VariantConfig,
    records_by_domain,
    schemas: dict[str, DomainSchema],
    decisions_by_domain,
    backbone_concepts: list[str],
) -> dict[str, DomainGraphArtifacts]:
    relation_families = set(config.relations.relation_families)
    domain_graphs: dict[str, DomainGraphArtifacts] = {}
    backbone_set = set(backbone_concepts)
    write_temporal_metadata = variant.write_temporal_metadata

    constraints = None
    validation_stats_total = {"total_edges": 0, "valid_edges": 0, "invalid_edges": 0, "invalid_by_family": {}}
    if config.runtime.enable_relation_validation and config.runtime.relation_constraints_path:
        try:
            constraints = load_relation_constraints(config.runtime.relation_constraints_path)
            logger.info("Loaded relation constraints from %s", config.runtime.relation_constraints_path)
        except FileNotFoundError as exc:
            logger.warning("Relation constraints file not found, validation disabled: %s", exc)

    for domain in config.domains:
        records = records_by_domain[domain.domain_id]
        schema = schemas[domain.domain_id]
        adapter_parent = {item.label: item.parent_anchor for item in schema.adapter_concepts}
        decisions_for_domain = decisions_by_domain[domain.domain_id]

        node_map: OrderedDict[str, GraphNode] = OrderedDict()
        edge_map: OrderedDict[str, GraphEdge] = OrderedDict()
        triples: list[CandidateTriple] = []
        temporal_assertions: list[TemporalAssertion] = []
        snapshot_states: list[SnapshotState] = []
        snapshots: list[SnapshotManifest] = []
        accepted_evidence_ids: list[str] = []
        previous_snapshot_id: str | None = None
        materialized_candidate_ids: set[str] = set()

        first_observation_time: dict[str, str] = {}
        previous_assertions_by_object: dict[str, TemporalAssertion] = {}

        for backbone_label in backbone_concepts:
            node_id = f"{domain.domain_id}::node::{backbone_label}"
            node_map[node_id] = GraphNode(
                node_id=node_id,
                label=backbone_label,
                display_label=backbone_label,
                domain_id=domain.domain_id,
                node_type="backbone_concept",
                node_layer="semantic",
                parent_anchor=None,
                surface_form=backbone_label,
                provenance_evidence_ids=[],
                valid_from=None,
            )
            materialized_candidate_ids.add(f"{domain.domain_id}::{backbone_label}")

        for record_index, record in enumerate(records, start=1):
            accepted_evidence_ids.append(record.evidence_id)
            new_node_ids: list[str] = []
            new_edge_ids: list[str] = []
            step_action_by_label: dict[str, str | None] = {}

            for step_position, step_record in enumerate(record.step_records, start=1):
                scoped_label = _task_candidate_label(record.evidence_id, step_record.step_id)
                step_action_by_label[scoped_label] = _canonical_step_action(step_record)
                materialized_candidate_ids.add(f"{domain.domain_id}::workflow_step::{scoped_label}")
                node_id = f"{domain.domain_id}::node::{scoped_label}"
                if node_id not in node_map:
                    node_map[node_id] = GraphNode(
                        node_id=node_id,
                        label=scoped_label,
                        display_label=_build_step_display_label(step_record),
                        domain_id=domain.domain_id,
                        node_type="workflow_step",
                        node_layer="workflow",
                        parent_anchor=None,
                        surface_form=step_record.task.surface_form,
                        step_id=step_record.step_id,
                        order_index=_step_order_index(step_record.step_id, step_position),
                        provenance_evidence_ids=[record.evidence_id],
                        valid_from=record.timestamp if write_temporal_metadata else None,
                        step_phase=getattr(step_record, "step_phase", None),
                    )
                    new_node_ids.append(node_id)
                    first_observation_time[node_id] = record.timestamp
                elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                    node_map[node_id].provenance_evidence_ids.append(record.evidence_id)

            for mention in record.document_concept_mentions:
                candidate_id = f"{domain.domain_id}::{mention.label}"
                decision = decisions_for_domain.get(candidate_id)
                if decision is None or not decision.admit_as_node:
                    continue
                materialized_candidate_ids.add(candidate_id)
                node_id = f"{domain.domain_id}::node::{mention.label}"
                if node_id not in node_map:
                    node_map[node_id] = GraphNode(
                        node_id=node_id,
                        label=mention.label,
                        display_label=mention.label,
                        domain_id=domain.domain_id,
                        node_type="backbone_concept" if mention.label in backbone_set else "adapter_concept",
                        node_layer="semantic",
                        parent_anchor=None if mention.label in backbone_set else decision.parent_anchor,
                        surface_form=mention.surface_form or mention.label,
                        provenance_evidence_ids=[record.evidence_id],
                        valid_from=record.timestamp if write_temporal_metadata else None,
                        shared_hypernym=getattr(mention, "shared_hypernym", None),
                    )
                    new_node_ids.append(node_id)
                    first_observation_time[node_id] = record.timestamp
                elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                    node_map[node_id].provenance_evidence_ids.append(record.evidence_id)
                if mention.label not in backbone_set:
                    _ensure_adapter_anchor_edge(
                        edge_map=edge_map,
                        domain_id=domain.domain_id,
                        label=mention.label,
                        parent_anchor=decision.parent_anchor,
                        evidence_id=record.evidence_id,
                        timestamp=record.timestamp,
                        write_temporal_metadata=write_temporal_metadata,
                        new_edge_ids=new_edge_ids,
                        first_observation_time=first_observation_time,
                    )

            for step_record in record.step_records:
                for mention in step_record.concept_mentions:
                    candidate_id = f"{domain.domain_id}::{mention.label}"
                    decision = decisions_for_domain.get(candidate_id)
                    if decision is None or not decision.admit_as_node:
                        continue
                    materialized_candidate_ids.add(candidate_id)
                    node_id = f"{domain.domain_id}::node::{mention.label}"
                    if node_id not in node_map:
                        node_map[node_id] = GraphNode(
                            node_id=node_id,
                            label=mention.label,
                            display_label=mention.label,
                            domain_id=domain.domain_id,
                            node_type="backbone_concept" if mention.label in backbone_set else "adapter_concept",
                            node_layer="semantic",
                            parent_anchor=None if mention.label in backbone_set else decision.parent_anchor,
                            surface_form=mention.surface_form or mention.label,
                            provenance_evidence_ids=[record.evidence_id],
                            valid_from=record.timestamp if write_temporal_metadata else None,
                            shared_hypernym=getattr(mention, "shared_hypernym", None),
                        )
                        new_node_ids.append(node_id)
                        first_observation_time[node_id] = record.timestamp
                    elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                        node_map[node_id].provenance_evidence_ids.append(record.evidence_id)
                    if mention.label not in backbone_set:
                        _ensure_adapter_anchor_edge(
                            edge_map=edge_map,
                            domain_id=domain.domain_id,
                            label=mention.label,
                            parent_anchor=decision.parent_anchor,
                            evidence_id=record.evidence_id,
                            timestamp=record.timestamp,
                            write_temporal_metadata=write_temporal_metadata,
                            new_edge_ids=new_edge_ids,
                            first_observation_time=first_observation_time,
                        )

            materialized_labels = {node.label for node in node_map.values()}
            node_layer_map = {node.label: node.node_layer for node in node_map.values()}
            current_node_types = {
                node.label: _node_semantic_type(node)
                for node in node_map.values()
            }

            normalized_document_relations = _normalize_document_relations(
                record.document_relation_mentions,
                current_node_types,
            )
            concept_step_support = _build_record_step_support(record)
            multi_target_document_relation_keys: set[tuple[str, str, str]] = set()
            document_relation_targets: dict[tuple[str, str, str], set[str]] = {}
            for relation in normalized_document_relations:
                if relation.family not in {"communication", "propagation"}:
                    continue
                key = (relation.head, relation.label, relation.family)
                document_relation_targets.setdefault(key, set()).add(relation.tail)
            for key, tails in document_relation_targets.items():
                if len(tails) > 1:
                    multi_target_document_relation_keys.add(key)
            cross_step_metadata = _cross_step_metadata(record)
            relation_stream: list[tuple[GraphRelationInput, str]] = [
                (relation, "workflow")
                for relation in _record_workflow_relation_inputs(record)
            ]
            relation_stream.extend(
                (relation, "v2_semantic")
                for relation in _record_v2_semantic_relation_inputs(record)
            )
            relation_stream.extend(
                (_relation_input_from_mention(relation, "document_relation_mentions"), "document")
                for relation in normalized_document_relations
            )

            for relation_index, (relation, relation_origin) in enumerate(relation_stream, start=1):
                cross_metadata = cross_step_metadata.get((relation.head, relation.label, relation.family, relation.tail))
                relation_source_field = relation.source_field
                relation_head_step = relation.head_step
                relation_tail_step = relation.tail_step
                relation_mechanism = relation.mechanism
                relation_evidence_label = relation.evidence_label
                if cross_metadata is not None:
                    relation_source_field = "cross_step_relations"
                    relation_head_step = cross_metadata.head_step
                    relation_tail_step = cross_metadata.tail_step
                triple_id = f"{domain.domain_id}::triple::{record.evidence_id}::{relation_index}"
                resolved_head = _resolve_record_task_label(record.evidence_id, relation.head)
                resolved_tail = _resolve_record_task_label(record.evidence_id, relation.tail)
                head_candidate_id = _candidate_id_from_endpoint(domain.domain_id, record.evidence_id, relation.head)
                tail_candidate_id = _candidate_id_from_endpoint(domain.domain_id, record.evidence_id, relation.tail)
                head_decision = decisions_for_domain.get(head_candidate_id)
                tail_decision = decisions_for_domain.get(tail_candidate_id)
                reject_reason: str | None = None
                graph_layer = "semantic"
                workflow_kind: str | None = None
                head_in_graph = resolved_head in materialized_labels
                tail_in_graph = resolved_tail in materialized_labels
                head_layer = node_layer_map.get(resolved_head)
                tail_layer = node_layer_map.get(resolved_tail)

                if relation.family not in relation_families:
                    accepted = False
                    reject_reason = "invalid_relation_family"
                elif (
                    relation_origin == "document"
                    and relation.family in {"communication", "propagation"}
                    and (relation.head, relation.label, relation.family) in multi_target_document_relation_keys
                ):
                    accepted = False
                    reject_reason = "multi_target_diagnostic_hypothesis"
                elif relation.family == "structural" and resolved_head == resolved_tail:
                    accepted = False
                    reject_reason = "structural_self_loop"
                elif relation.family == "structural" and _STRUCTURAL_CONTEXTUAL_HEAD_PATTERN.search(resolved_head):
                    accepted = False
                    reject_reason = "structural_contextual_head"
                else:
                    if relation.family == "task_dependency":
                        graph_layer, workflow_kind, task_reject_reason = _classify_task_dependency(
                            head_in_graph=head_in_graph,
                            tail_in_graph=tail_in_graph,
                            head_layer=head_layer,
                            tail_layer=tail_layer,
                            raw_head=relation.head,
                            raw_tail=relation.tail,
                        )
                        if task_reject_reason is not None:
                            accepted = False
                            reject_reason = task_reject_reason
                        elif not (head_in_graph and tail_in_graph):
                            accepted = False
                            rejection_parts: list[str] = []
                            if not head_in_graph:
                                if head_decision and head_decision.reject_reason:
                                    rejection_parts.append(f"head:{head_decision.reject_reason}")
                                else:
                                    rejection_parts.append("head:not_in_graph")
                            if not tail_in_graph:
                                if tail_decision and tail_decision.reject_reason:
                                    rejection_parts.append(f"tail:{tail_decision.reject_reason}")
                                else:
                                    rejection_parts.append("tail:not_in_graph")
                            reject_reason = ";".join(rejection_parts)
                        else:
                            relation_accepted, relation_filter_reason = filter_relation_mention(
                                family=relation.family,
                                head=resolved_head,
                                tail=resolved_tail,
                                relation_label=relation.label,
                                head_in_graph=head_in_graph,
                                tail_in_graph=tail_in_graph,
                                node_anchor_map=current_node_types,
                            )
                            accepted = relation_accepted
                            reject_reason = None if relation_accepted else relation_filter_reason
                    elif head_layer != "semantic" or tail_layer != "semantic":
                        accepted = False
                        reject_reason = "semantic_relation_requires_semantic_nodes"
                    else:
                        semantic_gate_reason = _document_semantic_reject_reason(
                            relation_origin=relation_origin,
                            relation_family=relation.family,
                            head=resolved_head,
                            tail=resolved_tail,
                            concept_step_support=concept_step_support,
                        )
                        if semantic_gate_reason:
                            accepted = False
                            reject_reason = semantic_gate_reason
                            graph_layer = "semantic"
                            workflow_kind = None
                            relation_accepted = False
                        else:
                            relation_accepted, relation_filter_reason = filter_relation_mention(
                                family=relation.family,
                                head=resolved_head,
                                tail=resolved_tail,
                                relation_label=relation.label,
                                head_in_graph=head_in_graph,
                                tail_in_graph=tail_in_graph,
                                node_anchor_map=current_node_types,
                            )
                            if not relation_accepted:
                                accepted = False
                                reject_reason = relation_filter_reason
                            else:
                                accepted = head_in_graph and tail_in_graph
                                if not accepted:
                                    rejection_parts = []
                                    if not head_in_graph:
                                        if head_decision and head_decision.reject_reason:
                                            rejection_parts.append(f"head:{head_decision.reject_reason}")
                                        else:
                                            rejection_parts.append("head:not_in_graph")
                                    if not tail_in_graph:
                                        if tail_decision and tail_decision.reject_reason:
                                            rejection_parts.append(f"tail:{tail_decision.reject_reason}")
                                        else:
                                            rejection_parts.append("tail:not_in_graph")
                                    reject_reason = ";".join(rejection_parts)
                                graph_layer = "semantic"
                                workflow_kind = None

                type_valid = True
                if accepted and constraints:
                    edge_dict = {
                        "family": relation.family,
                        "head": resolved_head,
                        "tail": resolved_tail,
                        "edge_id": triple_id,
                    }
                    type_valid, type_invalid_reason = validate_edge(edge_dict, current_node_types, constraints)
                    if not type_valid:
                        reject_reason = f"type_constraint:{type_invalid_reason}"
                        validation_stats_total["invalid_edges"] += 1
                        family = relation.family
                        validation_stats_total["invalid_by_family"][family] = validation_stats_total["invalid_by_family"].get(family, 0) + 1

                if accepted and type_valid:
                    validation_stats_total["valid_edges"] += 1
                validation_stats_total["total_edges"] += 1

                final_accepted = accepted and type_valid
                final_status = "accepted" if final_accepted else ("rejected_type" if accepted and not type_valid else "rejected")
                raw_relation = relation.label
                display_relation = relation.label
                edge_salience: str | None = None
                display_admitted = False
                display_reject_reason = "not_accepted"

                if final_accepted:
                    if graph_layer == "workflow" and workflow_kind == "sequence":
                        display_relation = "triggers"
                        edge_salience = "high"
                        display_admitted = True
                        display_reject_reason = None
                    elif graph_layer == "workflow" and workflow_kind == "action_object":
                        step_action = step_action_by_label.get(resolved_head)
                        tail_anchor = current_node_types.get(resolved_tail)
                        display_relation = (
                            _workflow_display_action(
                                raw_label=raw_relation,
                                step_action=step_action,
                                tail_anchor=tail_anchor,
                            )
                            or raw_relation
                        )
                        edge_salience, display_admitted, display_reject_reason = _workflow_edge_display_policy(
                            raw_label=raw_relation,
                            display_action=display_relation if display_relation in _WORKFLOW_DISPLAY_ACTIONS else None,
                            tail_label=resolved_tail,
                            tail_anchor=tail_anchor,
                        )
                    else:
                        edge_salience, display_admitted, display_reject_reason = _semantic_edge_display_policy(relation.family)
                        display_relation = relation.label

                triples.append(
                    CandidateTriple(
                        triple_id=triple_id,
                        domain_id=domain.domain_id,
                        head=resolved_head,
                        relation=relation.label,
                        raw_relation=raw_relation,
                        display_relation=display_relation,
                        tail=resolved_tail,
                        relation_family=relation.family,
                        graph_layer=graph_layer,
                        workflow_kind=workflow_kind,
                        edge_salience=edge_salience,
                        display_admitted=display_admitted,
                        display_reject_reason=display_reject_reason,
                        evidence_ids=[record.evidence_id],
                        attachment_refs=[
                            head_decision.candidate_id if head_decision else resolved_head,
                            tail_decision.candidate_id if tail_decision else resolved_tail,
                        ],
                        confidence=1.0 if final_accepted else 0.0,
                        reject_reason=None if final_accepted else reject_reason,
                        status=final_status,
                    )
                )
                if not final_accepted:
                    continue

                # Fix: workflow grounding edges should have family="action_object"
                # not the original family from relation_mentions (which is "task_dependency")
                edge_family = "action_object" if workflow_kind == "action_object" else relation.family

                edge_id = f"{domain.domain_id}::edge::{resolved_head}::{relation.label}::{resolved_tail}"
                if edge_id not in edge_map:
                    edge_map[edge_id] = GraphEdge(
                        edge_id=edge_id,
                        domain_id=domain.domain_id,
                        label=relation.label,
                        raw_label=raw_relation,
                        display_label=display_relation,
                        family=edge_family,
                        edge_layer=graph_layer,
                        workflow_kind=workflow_kind,
                        edge_salience=edge_salience,
                        display_admitted=display_admitted,
                        display_reject_reason=display_reject_reason,
                        head=resolved_head,
                        tail=resolved_tail,
                        head_step=relation_head_step,
                        tail_step=relation_tail_step,
                        source_field=relation_source_field,
                        mechanism=relation_mechanism,
                        evidence_label=relation_evidence_label,
                        provenance_evidence_ids=[record.evidence_id],
                        valid_from=record.timestamp if write_temporal_metadata else None,
                    )
                    new_edge_ids.append(edge_id)
                    first_observation_time[edge_id] = record.timestamp
                elif record.evidence_id not in edge_map[edge_id].provenance_evidence_ids:
                    edge_map[edge_id].provenance_evidence_ids.append(record.evidence_id)
                if edge_id in edge_map:
                    edge = edge_map[edge_id]
                    if relation_head_step and edge.head_step is None:
                        edge.head_step = relation_head_step
                    if relation_tail_step and edge.tail_step is None:
                        edge.tail_step = relation_tail_step
                    if relation_source_field and edge.source_field is None:
                        edge.source_field = relation_source_field
                    if relation_mechanism and edge.mechanism is None:
                        edge.mechanism = relation_mechanism
                    if relation_evidence_label and edge.evidence_label is None:
                        edge.evidence_label = relation_evidence_label

            if variant.enable_snapshots:
                snapshot_id = f"{domain.domain_id}-snapshot-{record_index:03d}"
                current_nodes = [node.model_copy(deep=True) for node in node_map.values()]
                current_edges = [edge.model_copy(deep=True) for edge in edge_map.values()]
                snapshot_states.append(SnapshotState(snapshot_id=snapshot_id, nodes=current_nodes, edges=current_edges))
                snapshots.append(
                    SnapshotManifest(
                        snapshot_id=snapshot_id,
                        domain_id=domain.domain_id,
                        created_at=record.timestamp,
                        parent_snapshot_id=previous_snapshot_id,
                        accepted_schema_ids=sorted(materialized_candidate_ids),
                        accepted_triple_ids=[triple.triple_id for triple in triples if triple.status == "accepted"],
                        consistency_results_path=f"snapshots/{snapshot_id}/consistency.json",
                        notes=f"variant={variant.variant_id}",
                        node_count=len(current_nodes),
                        edge_count=len(current_edges),
                        accepted_evidence_ids=list(accepted_evidence_ids),
                    )
                )

                for node_id in new_node_ids:
                    valid_time_start = first_observation_time.get(node_id)
                    prev_assertion = previous_assertions_by_object.get(node_id)
                    supersedes_id = prev_assertion.assertion_id if prev_assertion else None
                    current_assertion = TemporalAssertion(
                        assertion_id=f"{snapshot_id}::schema::{node_id}",
                        object_type="schema",
                        object_id=node_id,
                        valid_time_start=valid_time_start,
                        valid_time_end=None,
                        transaction_time=record.timestamp,
                        supersedes=supersedes_id,
                        snapshot_id=snapshot_id,
                    )
                    temporal_assertions.append(current_assertion)
                    if prev_assertion:
                        prev_assertion.valid_time_end = record.timestamp
                    previous_assertions_by_object[node_id] = current_assertion

                for edge_id in new_edge_ids:
                    valid_time_start = first_observation_time.get(edge_id)
                    prev_assertion = previous_assertions_by_object.get(edge_id)
                    supersedes_id = prev_assertion.assertion_id if prev_assertion else None
                    current_assertion = TemporalAssertion(
                        assertion_id=f"{snapshot_id}::triple::{edge_id}",
                        object_type="triple",
                        object_id=edge_id,
                        valid_time_start=valid_time_start,
                        valid_time_end=None,
                        transaction_time=record.timestamp,
                        supersedes=supersedes_id,
                        snapshot_id=snapshot_id,
                    )
                    temporal_assertions.append(current_assertion)
                    if prev_assertion:
                        prev_assertion.valid_time_end = record.timestamp
                    previous_assertions_by_object[edge_id] = current_assertion
                previous_snapshot_id = snapshot_id

        # Detect lifecycle events from temporal assertions and edges
        lifecycle_events: list[LifecycleEvent] = []
        if variant.enable_snapshots and variant.detect_lifecycle_events and temporal_assertions:
            try:
                from temporal.lifecycle import DeviceLifecycleTracker
                tracker = DeviceLifecycleTracker()
                lifecycle_events = tracker.detect_lifecycle_events(
                    temporal_assertions,
                    list(edge_map.values()),
                    domain.domain_id,
                )
                lifecycle_events = [
                    LifecycleEvent.model_validate(event.model_dump(mode="json") if hasattr(event, "model_dump") else event)
                    for event in lifecycle_events
                ]
            except ImportError:
                pass

        domain_graphs[domain.domain_id] = DomainGraphArtifacts(
            domain_id=domain.domain_id,
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
            triples=triples,
            temporal_assertions=temporal_assertions,
            snapshots=snapshots,
            snapshot_states=snapshot_states,
            lifecycle_events=lifecycle_events,
        )

    if constraints and validation_stats_total["total_edges"] > 0:
        total = validation_stats_total["total_edges"]
        valid = validation_stats_total["valid_edges"]
        invalid = validation_stats_total["invalid_edges"]
        invalid_rate = invalid / total if total > 0 else 0
        logger.info("Edge validation summary: %d/%d valid (%.2f%% rejected)", valid, total, invalid_rate * 100)

    return domain_graphs
