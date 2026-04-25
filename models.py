#!/usr/bin/env python3
"""Core data models for CrossExtend-KG."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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

SemanticTypeHint = Literal["Asset", "Component", "Signal", "State", "Fault"]
SharedHypernym = Literal[
    "Seal", "Connector", "Sensor", "Controller",
    "Coolant", "Actuator", "Power", "Housing",
    "Fastener", "Media",
]
StepPhase = Literal["observe", "diagnose", "repair", "verify"]
NodeLayer = Literal["semantic", "workflow"]
EdgeLayer = Literal["semantic", "workflow"]
WorkflowKind = Literal["sequence", "action_object"]
EdgeSalience = Literal["high", "medium", "low"]


def _normalize_semantic_type_hint(value: Any) -> SemanticTypeHint | None:
    if not isinstance(value, str):
        return None
    compact = value.strip().lower()
    mapping: dict[str, SemanticTypeHint] = {
        "asset": "Asset",
        "component": "Component",
        "signal": "Signal",
        "state": "State",
        "fault": "Fault",
    }
    return mapping.get(compact)


class ConceptMention(BaseModel):
    label: str
    kind: Literal["concept"] = "concept"
    description: str = ""
    node_worthy: bool = True
    surface_form: str = ""
    semantic_type_hint: SemanticTypeHint | None = None
    shared_hypernym: SharedHypernym | None = None

    @model_validator(mode="before")
    @classmethod
    def _upgrade_semantic_type_hint(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        semantic_type_hint = (
            payload.get("semantic_type_hint")
            or payload.get("parent_gold")
            or payload.get("gold_parent")
        )
        normalized_hint = _normalize_semantic_type_hint(semantic_type_hint)
        if normalized_hint is not None:
            payload["semantic_type_hint"] = normalized_hint
        payload.pop("parent_gold", None)
        payload.pop("gold_parent", None)
        return payload


class StepConceptMention(ConceptMention):
    """Semantic alias for concepts attached to O&M steps."""


class RelationMention(BaseModel):
    label: str
    family: str
    head: str
    tail: str


class StepAction(BaseModel):
    action_type: str
    target_label: str


class StructuralEdge(BaseModel):
    label: str
    family: str
    head: str
    tail: str


class StateTransition(BaseModel):
    from_state: str
    to_state: str
    trigger_step: str | None = None
    evidence_label: str | None = None


class DiagnosticEdge(BaseModel):
    evidence_label: str
    indicated_label: str
    mechanism: str | None = None


class ProcedureMeta(BaseModel):
    asset_name: str | None = None
    procedure_type: str | None = None
    primary_fault_type: str | None = None


class CrossStepRelation(BaseModel):
    label: str
    family: str
    head: str
    tail: str
    head_step: str | None = None
    tail_step: str | None = None


class StepEvidenceRecord(BaseModel):
    step_id: str
    task: StepConceptMention
    concept_mentions: list[ConceptMention] = Field(default_factory=list)
    relation_mentions: list[RelationMention] = Field(default_factory=list)
    # v2 fields (all optional with defaults for backward compatibility)
    step_phase: StepPhase | None = None
    step_summary: str = ""
    surface_form: str = ""
    step_actions: list[StepAction] = Field(default_factory=list)
    structural_edges: list[StructuralEdge] = Field(default_factory=list)
    state_transitions: list[StateTransition] = Field(default_factory=list)
    diagnostic_edges: list[DiagnosticEdge] = Field(default_factory=list)
    sequence_next: str | None = None


StepRecord = StepEvidenceRecord


class EvidenceRecord(BaseModel):
    evidence_id: str
    domain_id: str
    role: Literal["target"] = "target"
    source_type: str
    timestamp: str
    raw_text: str
    step_records: list[StepEvidenceRecord] = Field(default_factory=list)
    document_concept_mentions: list[ConceptMention] = Field(default_factory=list)
    document_relation_mentions: list[RelationMention] = Field(default_factory=list)
    # v2 fields (all optional with defaults for backward compatibility)
    procedure_meta: ProcedureMeta | None = None
    cross_step_relations: list[CrossStepRelation] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "step_records" not in payload and (
            "concept_mentions" in payload or "relation_mentions" in payload
        ):
            payload["step_records"] = []
            payload["document_concept_mentions"] = payload.pop("concept_mentions", [])
            payload["document_relation_mentions"] = payload.pop("relation_mentions", [])
        payload.setdefault("step_records", [])
        payload.setdefault("document_concept_mentions", [])
        payload.setdefault("document_relation_mentions", [])
        return payload

    @staticmethod
    def _flatten_step_records(
        step_records: list[StepEvidenceRecord],
    ) -> tuple[list[ConceptMention], list[RelationMention]]:
        concept_mentions: list[ConceptMention] = []
        relation_mentions: list[RelationMention] = []
        for step_record in step_records:
            concept_mentions.append(step_record.task)
            concept_mentions.extend(step_record.concept_mentions)
            relation_mentions.extend(step_record.relation_mentions)
        return concept_mentions, relation_mentions

    @property
    def concept_mentions(self) -> list[ConceptMention]:
        step_mentions, _ = self._flatten_step_records(self.step_records)
        return step_mentions + list(self.document_concept_mentions)

    @property
    def relation_mentions(self) -> list[RelationMention]:
        _, step_relations = self._flatten_step_records(self.step_records)
        return step_relations + list(self.document_relation_mentions)


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
    display_label: str = ""
    domain_id: str
    node_type: str
    node_layer: NodeLayer = "semantic"
    parent_anchor: str | None = None
    surface_form: str = ""
    step_id: str | None = None
    order_index: int | None = None
    provenance_evidence_ids: list[str] = Field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    lifecycle_stage: str | None = None
    shared_hypernym: str | None = None
    step_phase: str | None = None


class GraphEdge(BaseModel):
    edge_id: str
    domain_id: str
    label: str
    raw_label: str = ""
    display_label: str = ""
    family: str
    edge_layer: EdgeLayer = "semantic"
    workflow_kind: WorkflowKind | None = None
    edge_salience: EdgeSalience | None = None
    display_admitted: bool = True
    display_reject_reason: str | None = None
    head: str
    tail: str
    provenance_evidence_ids: list[str] = Field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None


class CandidateTriple(BaseModel):
    triple_id: str
    domain_id: str
    head: str
    relation: str
    raw_relation: str = ""
    display_relation: str | None = None
    tail: str
    relation_family: str
    graph_layer: EdgeLayer = "semantic"
    workflow_kind: WorkflowKind | None = None
    edge_salience: EdgeSalience | None = None
    display_admitted: bool = True
    display_reject_reason: str | None = None
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


LifecycleEventType = Literal[
    "creation",
    "update",
    "deprecation",
    "replacement",
    "fault_occurrence",
    "maintenance",
]


class LifecycleEvent(BaseModel):
    event_id: str
    domain_id: str
    event_type: LifecycleEventType
    object_id: str
    timestamp: str
    description: str = ""
    superseded_by: str | None = None


class DomainGraphArtifacts(BaseModel):
    domain_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    triples: list[CandidateTriple] = Field(default_factory=list)
    temporal_assertions: list[TemporalAssertion] = Field(default_factory=list)
    snapshots: list[SnapshotManifest] = Field(default_factory=list)
    snapshot_states: list[SnapshotState] = Field(default_factory=list)
    lifecycle_events: list[LifecycleEvent] = Field(default_factory=list)


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
    attachment_decisions: dict[str, dict[str, AttachmentDecision]]
    schemas: dict[str, DomainSchema]
    domain_graphs: dict[str, DomainGraphArtifacts]
    construction_summary: dict[str, Any]


class PipelineBenchmarkResult(BaseModel):
    project_name: str
    benchmark_name: str
    config_path: str
    run_root: str
    generated_dataset_path: str | None = None
    variant_results: dict[str, VariantRunResult]
    summary: dict[str, Any]
