#!/usr/bin/env python3
"""Schema materialization, graph assembly, and snapshot creation."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import json
import logging

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


def build_domain_schemas(
    config: PipelineConfig,
    candidates_by_domain: dict[str, list[SchemaCandidate]],
    decisions_by_domain,
    backbone_concepts: list[str],
) -> dict[str, DomainSchema]:
    """Build domain schemas for unified construction method."""
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

    # Load relation constraints if validation is enabled
    constraints = None
    validation_stats_total = {"total_edges": 0, "valid_edges": 0, "invalid_edges": 0, "invalid_by_family": {}}
    if config.runtime.enable_relation_validation and config.runtime.relation_constraints_path:
        try:
            constraints = load_relation_constraints(config.runtime.relation_constraints_path)
            logger.info(f"Loaded relation constraints from {config.runtime.relation_constraints_path}")
        except FileNotFoundError as e:
            logger.warning(f"Relation constraints file not found, validation disabled: {e}")

    for domain in config.domains:
        records = records_by_domain[domain.domain_id]
        schema = schemas[domain.domain_id]
        accepted_labels = backbone_set | {item.label for item in schema.adapter_concepts}
        adapter_parent = {item.label: item.parent_anchor for item in schema.adapter_concepts}
        decisions_for_domain = decisions_by_domain[domain.domain_id]

        node_map: "OrderedDict[str, GraphNode]" = OrderedDict()
        edge_map: "OrderedDict[str, GraphEdge]" = OrderedDict()
        triples: list[CandidateTriple] = []
        temporal_assertions: list[TemporalAssertion] = []
        snapshot_states: list[SnapshotState] = []
        snapshots: list[SnapshotManifest] = []
        accepted_evidence_ids: list[str] = []
        previous_snapshot_id: str | None = None

        # Track first observation times for valid_time_start
        first_observation_time: dict[str, str] = {}
        # Track previous assertions for supersedes chain
        previous_assertions_by_object: dict[str, TemporalAssertion] = {}

        for record_index, record in enumerate(records, start=1):
            accepted_evidence_ids.append(record.evidence_id)
            new_node_ids: list[str] = []
            new_edge_ids: list[str] = []

            for mention in record.concept_mentions:
                if not mention.node_worthy or mention.label not in accepted_labels:
                    continue
                node_id = f"{domain.domain_id}::node::{mention.label}"
                if node_id not in node_map:
                    node_map[node_id] = GraphNode(
                        node_id=node_id,
                        label=mention.label,
                        domain_id=domain.domain_id,
                        node_type="backbone_concept" if mention.label in backbone_set else "adapter_concept",
                        parent_anchor=adapter_parent.get(mention.label),
                        provenance_evidence_ids=[record.evidence_id],
                    )
                    new_node_ids.append(node_id)
                    # Record first observation time
                    first_observation_time[node_id] = record.timestamp
                elif record.evidence_id not in node_map[node_id].provenance_evidence_ids:
                    node_map[node_id].provenance_evidence_ids.append(record.evidence_id)

            for relation_index, relation in enumerate(record.relation_mentions, start=1):
                triple_id = f"{domain.domain_id}::triple::{record.evidence_id}::{relation_index}"
                reject_reason: str | None = None
                if relation.family not in relation_families:
                    accepted = False
                    reject_reason = "invalid_relation_family"
                else:
                    head_decision = decisions_for_domain.get(f"{domain.domain_id}::{relation.head}")
                    tail_decision = decisions_for_domain.get(f"{domain.domain_id}::{relation.tail}")
                    accepted = relation.head in accepted_labels and relation.tail in accepted_labels
                    if not accepted:
                        rejection_parts: list[str] = []
                        if relation.head not in accepted_labels:
                            if head_decision and head_decision.reject_reason:
                                rejection_parts.append(f"head:{head_decision.reject_reason}")
                            else:
                                rejection_parts.append("head:not_in_graph")
                        if relation.tail not in accepted_labels:
                            if tail_decision and tail_decision.reject_reason:
                                rejection_parts.append(f"tail:{tail_decision.reject_reason}")
                            else:
                                rejection_parts.append("tail:not_in_graph")
                        reject_reason = ";".join(rejection_parts)

                # Additional type constraint validation
                type_valid = True
                type_invalid_reason = None
                if accepted and constraints:
                    # Build node types dict for validation
                    # backbone concepts have their own label as type, adapter concepts use parent_anchor
                    node_types = {}
                    for label in backbone_set:
                        node_types[label] = label  # Backbone type is the concept itself
                    for item in schema.adapter_concepts:
                        node_types[item.label] = item.parent_anchor

                    edge_dict = {
                        "family": relation.family,
                        "head": relation.head,
                        "tail": relation.tail,
                        "edge_id": triple_id
                    }
                    type_valid, type_invalid_reason = validate_edge(edge_dict, node_types, constraints)
                    if not type_valid:
                        reject_reason = f"type_constraint:{type_invalid_reason}"
                        validation_stats_total["invalid_edges"] += 1
                        family = relation.family
                        validation_stats_total["invalid_by_family"][family] = validation_stats_total["invalid_by_family"].get(family, 0) + 1
                        logger.debug(f"Edge rejected: {relation.head} -> {relation.tail} ({relation.family}): {type_invalid_reason}")

                if accepted and type_valid:
                    validation_stats_total["valid_edges"] += 1
                validation_stats_total["total_edges"] += 1

                # Mark as rejected if either check fails
                final_accepted = accepted and type_valid
                final_status = "accepted" if final_accepted else ("rejected_type" if accepted and not type_valid else "rejected")

                triple = CandidateTriple(
                    triple_id=triple_id,
                    domain_id=domain.domain_id,
                    head=relation.head,
                    relation=relation.label,
                    tail=relation.tail,
                    relation_family=relation.family,
                    evidence_ids=[record.evidence_id],
                    attachment_refs=[
                        decisions_by_domain[domain.domain_id][f"{domain.domain_id}::{relation.head}"].candidate_id
                        if f"{domain.domain_id}::{relation.head}" in decisions_by_domain[domain.domain_id]
                        else relation.head,
                        decisions_by_domain[domain.domain_id][f"{domain.domain_id}::{relation.tail}"].candidate_id
                        if f"{domain.domain_id}::{relation.tail}" in decisions_by_domain[domain.domain_id]
                        else relation.tail,
                    ],
                    confidence=1.0 if final_accepted else 0.0,
                    reject_reason=None if final_accepted else reject_reason,
                    status=final_status,
                )
                triples.append(triple)
                if not final_accepted:
                    continue
                edge_id = f"{domain.domain_id}::edge::{relation.head}::{relation.label}::{relation.tail}"
                if edge_id not in edge_map:
                    edge_map[edge_id] = GraphEdge(
                        edge_id=edge_id,
                        domain_id=domain.domain_id,
                        label=relation.label,
                        family=relation.family,
                        head=relation.head,
                        tail=relation.tail,
                        provenance_evidence_ids=[record.evidence_id],
                    )
                    new_edge_ids.append(edge_id)
                    # Record first observation time
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
                        accepted_schema_ids=sorted(accepted_labels),
                        accepted_triple_ids=[triple.triple_id for triple in triples if triple.status == "accepted"],
                        consistency_results_path=f"snapshots/{snapshot_id}/consistency.json",
                        notes=f"variant={variant.variant_id}",
                        node_count=len(current_nodes),
                        edge_count=len(current_edges),
                        accepted_evidence_ids=list(accepted_evidence_ids),
                    )
                )
                for node_id in new_node_ids:
                    # Get first observation time
                    valid_time_start = first_observation_time.get(node_id)
                    # Check if there's a previous assertion for this object
                    prev_assertion = previous_assertions_by_object.get(node_id)
                    supersedes_id = prev_assertion.assertion_id if prev_assertion else None

                    current_assertion = TemporalAssertion(
                        assertion_id=f"{snapshot_id}::schema::{node_id}",
                        object_type="schema",
                        object_id=node_id,
                        valid_time_start=valid_time_start,
                        valid_time_end=None,  # Currently valid
                        transaction_time=record.timestamp,
                        supersedes=supersedes_id,
                        snapshot_id=snapshot_id,
                    )
                    temporal_assertions.append(current_assertion)

                    # Update previous assertion's valid_time_end if superseded
                    if prev_assertion:
                        prev_assertion.valid_time_end = record.timestamp

                    # Track this assertion for future superseding
                    previous_assertions_by_object[node_id] = current_assertion

                for edge_id in new_edge_ids:
                    # Get first observation time
                    valid_time_start = first_observation_time.get(edge_id)
                    # Check if there's a previous assertion for this object
                    prev_assertion = previous_assertions_by_object.get(edge_id)
                    supersedes_id = prev_assertion.assertion_id if prev_assertion else None

                    current_assertion = TemporalAssertion(
                        assertion_id=f"{snapshot_id}::triple::{edge_id}",
                        object_type="triple",
                        object_id=edge_id,
                        valid_time_start=valid_time_start,
                        valid_time_end=None,  # Currently valid
                        transaction_time=record.timestamp,
                        supersedes=supersedes_id,
                        snapshot_id=snapshot_id,
                    )
                    temporal_assertions.append(current_assertion)

                    # Update previous assertion's valid_time_end if superseded
                    if prev_assertion:
                        prev_assertion.valid_time_end = record.timestamp

                    # Track this assertion for future superseding
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

    # Log validation summary
    if constraints and validation_stats_total["total_edges"] > 0:
        total = validation_stats_total["total_edges"]
        valid = validation_stats_total["valid_edges"]
        invalid = validation_stats_total["invalid_edges"]
        invalid_rate = invalid / total if total > 0 else 0
        logger.info(f"Edge validation summary: {valid}/{total} valid ({invalid_rate:.2%} rejected)")
        if validation_stats_total["invalid_by_family"]:
            logger.info(f"Invalid by family: {validation_stats_total['invalid_by_family']}")

    return domain_graphs
