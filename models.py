#!/usr/bin/env python3
"""Core data models for CrossExtend-KG."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RejectReason = Literal[
    "person_name",
    "document_title",
    "observation_like_not_grounded",
    "cannot_anchor_backbone",
    "weak_relation_support",
    "low_graph_value",
    "unsupported_semantic_type",
    "route_not_allowed",
    "invalid_backbone_parent",
    "llm_no_decision",
    "backbone_label_mismatch",
]


class ConceptMention(BaseModel):
    label: str
    kind: Literal["concept"] = "concept"
    description: str = ""
    node_worthy: bool = True


class RelationMention(BaseModel):
    label: str
    family: str
    head: str
    tail: str


class EvidenceRecord(BaseModel):
    evidence_id: str
    domain_id: str
    role: Literal["target"] = "target"
    source_type: str
    timestamp: str
    raw_text: str
    concept_mentions: list[ConceptMention]
    relation_mentions: list[RelationMention]


class EvidenceUnit(BaseModel):
    evidence_id: str
    domain_id: str
    role: Literal["target"] = "target"
    source_id: str
    source_type: str
    locator: str
    raw_text: str
    normalized_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SchemaCandidate(BaseModel):
    candidate_id: str
    domain_id: str
    role: Literal["target"] = "target"
    label: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_texts: list[str] = Field(default_factory=list)
    support_count: int = 0
    routing_features: dict[str, Any] = Field(default_factory=dict)


class RetrievedAnchor(BaseModel):
    anchor: str
    score: float
    rank: int


class AttachmentDecision(BaseModel):
    candidate_id: str
    label: str
    route: Literal["reuse_backbone", "vertical_specialize", "reject"]
    parent_anchor: str | None = None
    accept: bool = True
    admit_as_node: bool = True
    reject_reason: RejectReason | None = None
    confidence: float = 0.0
    justification: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class AdapterConcept(BaseModel):
    label: str
    parent_anchor: str | None = None
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class DomainSchema(BaseModel):
    domain_id: str
    backbone_concepts: list[str]
    adapter_concepts: list[AdapterConcept] = Field(default_factory=list)


class GraphNode(BaseModel):
    node_id: str
    label: str
    domain_id: str
    node_type: str
    parent_anchor: str | None = None
    provenance_evidence_ids: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    edge_id: str
    domain_id: str
    label: str
    family: str
    head: str
    tail: str
    provenance_evidence_ids: list[str] = Field(default_factory=list)


class CandidateTriple(BaseModel):
    triple_id: str
    domain_id: str
    head: str
    relation: str
    tail: str
    relation_family: str
    evidence_ids: list[str] = Field(default_factory=list)
    attachment_refs: list[str] = Field(default_factory=list)
    confidence: float | None = None
    reject_reason: str | None = None
    status: Literal["proposed", "accepted", "rejected", "rejected_type"] = "proposed"


class TemporalAssertion(BaseModel):
    assertion_id: str
    object_type: Literal["schema", "triple", "state"]
    object_id: str
    valid_time_start: str | None = None
    valid_time_end: str | None = None
    transaction_time: str
    supersedes: str | None = None
    snapshot_id: str


class SnapshotManifest(BaseModel):
    snapshot_id: str
    domain_id: str
    created_at: str
    parent_snapshot_id: str | None = None
    accepted_schema_ids: list[str] = Field(default_factory=list)
    accepted_triple_ids: list[str] = Field(default_factory=list)
    consistency_results_path: str = ""
    notes: str = ""
    node_count: int = 0
    edge_count: int = 0
    accepted_evidence_ids: list[str] = Field(default_factory=list)


class SnapshotState(BaseModel):
    snapshot_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class HistoricalContextHit(BaseModel):
    memory_id: str
    entry_type: Literal["evidence", "attachment", "snapshot"]
    domain_id: str
    timestamp: str
    score: float
    summary: str
    parent_anchor: str | None = None
    snapshot_id: str | None = None
    variant_id: str | None = None
    matched_labels: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    memory_id: str
    entry_type: Literal["evidence", "attachment", "snapshot"]
    domain_id: str
    timestamp: str
    summary: str
    label_refs: list[str] = Field(default_factory=list)
    relation_families: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    parent_anchor: str | None = None
    snapshot_id: str | None = None
    variant_id: str | None = None
    run_root: str | None = None
    tags: list[str] = Field(default_factory=list)
    embedding_text: str = ""
    confidence: float = 1.0


class DomainGraphArtifacts(BaseModel):
    domain_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    triples: list[CandidateTriple] = Field(default_factory=list)
    temporal_assertions: list[TemporalAssertion] = Field(default_factory=list)
    snapshots: list[SnapshotManifest] = Field(default_factory=list)
    snapshot_states: list[SnapshotState] = Field(default_factory=list)


class VariantRunResult(BaseModel):
    variant_id: str
    variant_description: str
    seed_backbone_concepts: list[str] = Field(default_factory=list)
    seed_backbone_descriptions: dict[str, str] = Field(default_factory=dict)
    backbone_concepts: list[str]
    backbone_descriptions: dict[str, str]
    curated_backbone_concepts: list[str] = Field(default_factory=list)
    evidence_units: list[EvidenceUnit]
    candidates_by_domain: dict[str, list[SchemaCandidate]]
    retrievals: dict[str, dict[str, list[RetrievedAnchor]]]
    historical_context_by_domain: dict[str, dict[str, list[HistoricalContextHit]]] = Field(default_factory=dict)
    attachment_decisions: dict[str, dict[str, AttachmentDecision]]
    schemas: dict[str, DomainSchema]
    domain_graphs: dict[str, DomainGraphArtifacts]
    construction_summary: dict[str, Any]
    memory_entries: list[MemoryEntry] = Field(default_factory=list)
    run_dir: str | None = None


class PipelineBenchmarkResult(BaseModel):
    project_name: str
    benchmark_name: str
    config_path: str
    run_root: str
    generated_dataset_path: str | None = None
    variant_results: dict[str, VariantRunResult]
    summary: dict[str, Any]
