#!/usr/bin/env python3
"""Schema materialization, graph assembly, and snapshot creation."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict

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

_STRUCTURAL_CONTEXTUAL_HEAD_PATTERN = re.compile(r"\b(branch|path|condition|state)\b", re.IGNORECASE)
_INTERFACE_CONTAINER_PATTERN = re.compile(r"\b(face|surface|interface)\b", re.IGNORECASE)
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


def _step_summary_source(step_record) -> str:
    description = _normalize_space(step_record.task.description)
    if description and description.lower() != step_record.step_id.lower():
        return description
    surface_form = _normalize_space(step_record.task.surface_form)
    if surface_form:
        return surface_form
    return _normalize_space(step_record.task.label)


def _build_step_display_label(step_record) -> str:
    source = _step_summary_source(step_record)
    if not source:
        return step_record.step_id

    summary = _STEP_SUMMARY_PREFIX_PATTERN.sub("", source, count=1).strip()
    lowered = summary.lower()
    split_points = [lowered.find(splitter) for splitter in _STEP_SUMMARY_SPLITTERS if lowered.find(splitter) > 0]
    if split_points:
        summary = summary[: min(split_points)].strip()
    summary = _truncate_step_summary(summary)
    if not summary:
        return step_record.step_id
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


def _build_structural_interface_maps(
    relations,
    node_anchor_map: dict[str, str | None],
) -> tuple[dict[str, str], dict[str, str]]:
    component_interface_candidates: dict[str, set[str]] = {}
    for relation in relations:
        if relation.family != "structural" or relation.label != "contains":
            continue
        if node_anchor_map.get(relation.head) != "Component" or node_anchor_map.get(relation.tail) != "Component":
            continue
        if not _INTERFACE_CONTAINER_PATTERN.search(relation.tail):
            continue
        component_interface_candidates.setdefault(relation.head, set()).add(relation.tail)

    component_interface_map = {
        head: next(iter(candidates))
        for head, candidates in component_interface_candidates.items()
        if len(candidates) == 1
    }

    asset_interface_candidates: dict[str, set[str]] = {}
    for relation in relations:
        if relation.family != "structural" or relation.label != "contains":
            continue
        if node_anchor_map.get(relation.head) != "Asset":
            continue
        candidate = None
        if node_anchor_map.get(relation.tail) == "Component" and _INTERFACE_CONTAINER_PATTERN.search(relation.tail):
            candidate = relation.tail
        elif relation.tail in component_interface_map:
            candidate = component_interface_map[relation.tail]
        if candidate is not None:
            asset_interface_candidates.setdefault(relation.head, set()).add(candidate)

    asset_interface_map = {
        head: next(iter(candidates))
        for head, candidates in asset_interface_candidates.items()
        if len(candidates) == 1
    }
    return component_interface_map, asset_interface_map


def _normalize_document_relations(
    relations,
    node_anchor_map: dict[str, str | None],
):
    component_interface_map, asset_interface_map = _build_structural_interface_maps(relations, node_anchor_map)
    normalized = []
    for relation in relations:
        current = relation
        if relation.family == "structural" and relation.label == "contains":
            head_anchor = node_anchor_map.get(relation.head)
            tail_anchor = node_anchor_map.get(relation.tail)
            if (
                head_anchor == "Component"
                and tail_anchor == "Component"
                and _INTERFACE_CONTAINER_PATTERN.search(relation.tail)
            ):
                current = relation.model_copy(update={"head": relation.tail, "tail": relation.head})
            elif head_anchor == "Asset" and tail_anchor == "Component":
                tail_interface = component_interface_map.get(relation.tail)
                if tail_interface and tail_interface != relation.tail:
                    current = relation.model_copy(update={"tail": tail_interface})
                else:
                    preferred_interface = asset_interface_map.get(relation.head)
                    if preferred_interface and preferred_interface != relation.tail:
                        current = relation.model_copy(update={"head": preferred_interface})
            elif head_anchor == "Component" and tail_anchor == "Component":
                preferred_interface = component_interface_map.get(relation.head)
                if preferred_interface and preferred_interface != relation.tail:
                    current = relation.model_copy(update={"head": preferred_interface})
        normalized.append(current)
    return _dedupe_relation_mentions(normalized)


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

        for record_index, record in enumerate(records, start=1):
            accepted_evidence_ids.append(record.evidence_id)
            new_node_ids: list[str] = []
            new_edge_ids: list[str] = []

            for step_position, step_record in enumerate(record.step_records, start=1):
                scoped_label = _task_candidate_label(record.evidence_id, step_record.step_id)
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
                    )
                    new_node_ids.append(node_id)
                    first_observation_time[node_id] = record.timestamp
                elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                    node_map[node_id].provenance_evidence_ids.append(record.evidence_id)

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
                        )
                        new_node_ids.append(node_id)
                        first_observation_time[node_id] = record.timestamp
                    elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                        node_map[node_id].provenance_evidence_ids.append(record.evidence_id)

            materialized_labels = {node.label for node in node_map.values()}
            node_layer_map = {node.label: node.node_layer for node in node_map.values()}
            current_node_types = {
                node.label: _node_semantic_type(node)
                for node in node_map.values()
            }

            document_concept_labels = {mention.label for mention in record.document_concept_mentions}
            normalized_document_relations = _normalize_document_relations(
                record.document_relation_mentions,
                current_node_types,
            )
            relation_stream: list[tuple[object, str]] = [
                (relation, "document")
                for relation in normalized_document_relations
            ]
            for step_record in record.step_records:
                relation_stream.extend((relation, "step") for relation in step_record.relation_mentions)

            for relation_index, (relation, relation_origin) in enumerate(relation_stream, start=1):
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
                    and relation.family in {"communication", "propagation", "lifecycle"}
                    and (resolved_head not in document_concept_labels or resolved_tail not in document_concept_labels)
                ):
                    accepted = False
                    reject_reason = "document_local_semantic_relation"
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
                triples.append(
                    CandidateTriple(
                        triple_id=triple_id,
                        domain_id=domain.domain_id,
                        head=resolved_head,
                        relation=relation.label,
                        tail=resolved_tail,
                        relation_family=relation.family,
                        graph_layer=graph_layer,
                        workflow_kind=workflow_kind,
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

                edge_id = f"{domain.domain_id}::edge::{resolved_head}::{relation.label}::{resolved_tail}"
                if edge_id not in edge_map:
                    edge_map[edge_id] = GraphEdge(
                        edge_id=edge_id,
                        domain_id=domain.domain_id,
                        label=relation.label,
                        family=relation.family,
                        edge_layer=graph_layer,
                        workflow_kind=workflow_kind,
                        head=resolved_head,
                        tail=resolved_tail,
                        provenance_evidence_ids=[record.evidence_id],
                        valid_from=record.timestamp if write_temporal_metadata else None,
                    )
                    new_edge_ids.append(edge_id)
                    first_observation_time[edge_id] = record.timestamp
                elif record.evidence_id not in edge_map[edge_id].provenance_evidence_ids:
                    edge_map[edge_id].provenance_evidence_ids.append(record.evidence_id)

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
