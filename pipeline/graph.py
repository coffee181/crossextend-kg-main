#!/usr/bin/env python3
"""Schema materialization, graph assembly, and snapshot creation."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict

from ..config import PipelineConfig, VariantConfig
from ..models import (
    AdapterConcept,
    CandidateTriple,
    DomainGraphArtifacts,
    DomainSchema,
    GraphEdge,
    GraphNode,
    SchemaCandidate,
    SnapshotManifest,
    SnapshotState,
    TemporalAssertion,
)
from .relation_validation import load_relation_constraints, validate_edge

logger = logging.getLogger(__name__)

_STRUCTURAL_CONTEXTUAL_HEAD_PATTERN = re.compile(r"\b(branch|path|condition|state)\b", re.IGNORECASE)


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

            for step_record in record.step_records:
                scoped_label = _task_candidate_label(record.evidence_id, step_record.step_id)
                candidate_id = f"{domain.domain_id}::{scoped_label}"
                decision = decisions_for_domain.get(candidate_id)
                if not decision or not decision.admit_as_node:
                    continue
                materialized_candidate_ids.add(candidate_id)
                node_id = f"{domain.domain_id}::node::{scoped_label}"
                if node_id not in node_map:
                    node_map[node_id] = GraphNode(
                        node_id=node_id,
                        label=scoped_label,
                        domain_id=domain.domain_id,
                        node_type="adapter_concept",
                        parent_anchor="Task",
                        surface_form=step_record.task.surface_form,
                        provenance_evidence_ids=[record.evidence_id],
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
                        domain_id=domain.domain_id,
                        node_type="backbone_concept" if mention.label in backbone_set else "adapter_concept",
                        parent_anchor=None if mention.label in backbone_set else decision.parent_anchor,
                        surface_form=mention.surface_form or mention.label,
                        provenance_evidence_ids=[record.evidence_id],
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
                            domain_id=domain.domain_id,
                            node_type="backbone_concept" if mention.label in backbone_set else "adapter_concept",
                            parent_anchor=None if mention.label in backbone_set else decision.parent_anchor,
                            surface_form=mention.surface_form or mention.label,
                            provenance_evidence_ids=[record.evidence_id],
                        )
                        new_node_ids.append(node_id)
                        first_observation_time[node_id] = record.timestamp
                    elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                        node_map[node_id].provenance_evidence_ids.append(record.evidence_id)

            materialized_labels = {node.label for node in node_map.values()}
            current_node_types = {
                node.label: (node.label if node.node_type == "backbone_concept" else node.parent_anchor)
                for node in node_map.values()
            }

            relation_stream = list(record.document_relation_mentions)
            for step_record in record.step_records:
                relation_stream.extend(step_record.relation_mentions)

            for relation_index, relation in enumerate(relation_stream, start=1):
                triple_id = f"{domain.domain_id}::triple::{record.evidence_id}::{relation_index}"
                resolved_head = _resolve_record_task_label(record.evidence_id, relation.head)
                resolved_tail = _resolve_record_task_label(record.evidence_id, relation.tail)
                head_candidate_id = _candidate_id_from_endpoint(domain.domain_id, record.evidence_id, relation.head)
                tail_candidate_id = _candidate_id_from_endpoint(domain.domain_id, record.evidence_id, relation.tail)
                head_decision = decisions_for_domain.get(head_candidate_id)
                tail_decision = decisions_for_domain.get(tail_candidate_id)
                reject_reason: str | None = None

                if relation.family not in relation_families:
                    accepted = False
                    reject_reason = "invalid_relation_family"
                elif relation.family == "structural" and _STRUCTURAL_CONTEXTUAL_HEAD_PATTERN.search(resolved_head):
                    accepted = False
                    reject_reason = "structural_contextual_head"
                elif relation.family == "task_dependency" and not (
                    _extract_step_id(relation.head) and _extract_step_id(relation.tail)
                ):
                    # Step-local action/object relations remain visible in the
                    # step-centric evidence record, but they are not promoted
                    # into the final cross-document graph.
                    accepted = False
                    reject_reason = "task_dependency_explainability_only"
                else:
                    accepted = resolved_head in materialized_labels and resolved_tail in materialized_labels
                    if not accepted:
                        rejection_parts: list[str] = []
                        if resolved_head not in materialized_labels:
                            if head_decision and head_decision.reject_reason:
                                rejection_parts.append(f"head:{head_decision.reject_reason}")
                            else:
                                rejection_parts.append("head:not_in_graph")
                        if resolved_tail not in materialized_labels:
                            if tail_decision and tail_decision.reject_reason:
                                rejection_parts.append(f"tail:{tail_decision.reject_reason}")
                            else:
                                rejection_parts.append("tail:not_in_graph")
                        reject_reason = ";".join(rejection_parts)

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
                        head=resolved_head,
                        tail=resolved_tail,
                        provenance_evidence_ids=[record.evidence_id],
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

        domain_graphs[domain.domain_id] = DomainGraphArtifacts(
            domain_id=domain.domain_id,
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
            triples=triples,
            temporal_assertions=temporal_assertions,
            snapshots=snapshots,
            snapshot_states=snapshot_states,
        )

    if constraints and validation_stats_total["total_edges"] > 0:
        total = validation_stats_total["total_edges"]
        valid = validation_stats_total["valid_edges"]
        invalid = validation_stats_total["invalid_edges"]
        invalid_rate = invalid / total if total > 0 else 0
        logger.info("Edge validation summary: %d/%d valid (%.2f%% rejected)", valid, total, invalid_rate * 100)

    return domain_graphs
