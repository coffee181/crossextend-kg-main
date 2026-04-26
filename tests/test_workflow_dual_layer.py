#!/usr/bin/env python3
"""Targeted regression tests for the dual-layer workflow graph."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from experiments.metrics.core import compute_metrics, predicted_concepts, predicted_relations, workflow_grounding_edges
from models import (
    AdapterConcept,
    AttachmentDecision,
    ConceptMention,
    CrossStepRelation,
    DiagnosticEdge,
    DomainGraphArtifacts,
    DomainSchema,
    EvidenceRecord,
    GraphEdge,
    GraphNode,
    ProcedureMeta,
    RelationMention,
    SchemaCandidate,
    SnapshotManifest,
    SnapshotState,
    StepAction,
    StepConceptMention,
    StepEvidenceRecord,
    StateTransition,
    StructuralEdge,
    VariantRunResult,
)
from pipeline.artifacts import export_variant_run, load_snapshot_state
from pipeline.exports.graphml import export_graphml
from pipeline.graph import assemble_domain_graphs
from pipeline.router import retrieve_anchor_rankings
from rules.filtering import filter_attachment_decision


class WorkflowDualLayerTests(unittest.TestCase):
    def test_baseline_embedding_router_keeps_cosine_ranking(self) -> None:
        class FakeEmbeddingBackend:
            vectors = {
                "Asset: machine equipment": [1.0, 0.0, 0.0],
                "Signal: alarm telemetry": [0.0, 1.0, 0.0],
                "alarm candidate: warning code": [0.0, 1.0, 0.0],
            }

            def embed_texts(self, texts):
                return [self.vectors[text] for text in texts]

        candidate = SchemaCandidate(
            candidate_id="battery::alarm candidate",
            domain_id="battery",
            label="alarm candidate",
            description="warning code",
        )

        rankings = retrieve_anchor_rankings(
            embedding_backend=FakeEmbeddingBackend(),
            backbone_descriptions={"Asset": "machine equipment", "Signal": "alarm telemetry"},
            candidates=[candidate],
            top_k=2,
            mode="baseline",
        )

        anchors = [item.anchor for item in rankings[candidate.candidate_id]]
        self.assertEqual(anchors, ["Signal", "Asset"])

    def test_contextual_rerank_can_promote_semantic_relation_match(self) -> None:
        class FakeEmbeddingBackend:
            def embed_texts(self, texts):
                vectors = []
                for text in texts:
                    if text.startswith("Asset:"):
                        vectors.append([1.0, 0.0, 0.0])
                    elif text.startswith("Signal:"):
                        vectors.append([0.75, 0.25, 0.0])
                    elif "busbar temperature alarm" in text:
                        vectors.append([1.0, 0.0, 0.0])
                    else:
                        vectors.append([0.0, 0.0, 1.0])
                return vectors

        candidate = SchemaCandidate(
            candidate_id="battery::busbar temperature alarm",
            domain_id="battery",
            label="busbar temperature alarm",
            description="alarm reported by the battery controller for busbar temperature",
            routing_features={
                "semantic_type_hint": "Signal",
                "relation_families": ["communication"],
            },
        )

        baseline = retrieve_anchor_rankings(
            embedding_backend=FakeEmbeddingBackend(),
            backbone_descriptions={"Asset": "machine equipment", "Signal": "alarm telemetry"},
            candidates=[candidate],
            top_k=1,
            mode="baseline",
        )
        reranked = retrieve_anchor_rankings(
            embedding_backend=FakeEmbeddingBackend(),
            backbone_descriptions={"Asset": "machine equipment", "Signal": "alarm telemetry"},
            candidates=[candidate],
            top_k=1,
            mode="contextual_rerank",
        )

        self.assertEqual(baseline[candidate.candidate_id][0].anchor, "Asset")
        self.assertEqual(reranked[candidate.candidate_id][0].anchor, "Signal")

    def test_metrics_project_workflow_nodes_to_legacy_task(self) -> None:
        graph_payload = {
            "nodes": [
                {
                    "label": "BATOM_002:T1",
                    "display_label": "capture issue context (T1)",
                    "domain_id": "battery",
                    "node_type": "workflow_step",
                    "node_layer": "workflow",
                    "step_id": "T1",
                    "provenance_evidence_ids": ["BATOM_002"],
                },
                {
                    "label": "BATOM_002:T2",
                    "display_label": "remove cover (T2)",
                    "domain_id": "battery",
                    "node_type": "workflow_step",
                    "node_layer": "workflow",
                    "step_id": "T2",
                    "provenance_evidence_ids": ["BATOM_002"],
                },
                {
                    "label": "coolant odor",
                    "display_label": "coolant odor",
                    "domain_id": "battery",
                    "node_type": "adapter_concept",
                    "node_layer": "semantic",
                    "parent_anchor": "Signal",
                    "provenance_evidence_ids": ["BATOM_002"],
                },
            ],
            "edges": [
                {
                    "head": "BATOM_002:T1",
                    "label": "triggers",
                    "tail": "BATOM_002:T2",
                    "family": "task_dependency",
                    "edge_layer": "workflow",
                    "workflow_kind": "sequence",
                    "provenance_evidence_ids": ["BATOM_002"],
                },
                {
                    "head": "BATOM_002:T1",
                    "label": "observes",
                    "raw_label": "observes",
                    "display_label": "inspect",
                    "tail": "coolant odor",
                    "family": "action_object",
                    "edge_layer": "workflow",
                    "workflow_kind": "action_object",
                    "display_admitted": True,
                    "provenance_evidence_ids": ["BATOM_002"],
                },
            ],
        }
        doc_ids = {"BATOM_002"}

        concept_map = predicted_concepts(graph_payload, doc_ids)
        relation_set = predicted_relations(graph_payload, doc_ids)
        grounding = workflow_grounding_edges(graph_payload, doc_ids)

        self.assertEqual(concept_map["T1"], "Task")
        self.assertEqual(concept_map["T2"], "Task")
        self.assertEqual(concept_map["coolant odor"], "Signal")
        self.assertIn(("T1", "triggers", "T2", "task_dependency"), relation_set)
        self.assertNotIn(("T1", "observes", "coolant odor", "action_object"), relation_set)
        self.assertEqual(len(grounding), 1)
        self.assertEqual(grounding[0]["tail"], "coolant odor")

    def test_filter_rejects_task_parent_for_semantic_attachment(self) -> None:
        candidate = SimpleNamespace(
            label="coolant odor",
            description="odor observed near manifold face",
            evidence_ids=["BATOM_002"],
            routing_features={"semantic_type_hint": "Signal"},
        )
        decision = AttachmentDecision(
            candidate_id="battery::coolant odor",
            label="coolant odor",
            route="vertical_specialize",
            parent_anchor="Task",
            accept=True,
            admit_as_node=True,
            reject_reason=None,
            confidence=0.9,
            justification="bad route",
            evidence_ids=["BATOM_002"],
        )
        filtered = filter_attachment_decision(
            candidate=candidate,
            decision=decision,
            backbone_concepts={"Asset", "Component", "Task", "Signal", "State", "Fault"},
            allowed_routes={"reuse_backbone", "vertical_specialize", "reject"},
            allow_free_form_growth=False,
        )
        self.assertEqual(filtered.route, "reject")
        self.assertEqual(filtered.reject_reason, "invalid_backbone_parent")

    def test_graph_assembly_promotes_workflow_action_object_edges(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="T1 Observe coolant odor.",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Observe coolant odor near the joint."),
                    concept_mentions=[
                        ConceptMention(
                            label="coolant odor",
                            description="odor observed near the joint",
                            surface_form="coolant odor",
                            semantic_type_hint="Signal",
                        )
                    ],
                    relation_mentions=[
                        RelationMention(
                            label="observes",
                            family="task_dependency",
                            head="T1",
                            tail="coolant odor",
                        )
                    ],
                    step_actions=[StepAction(action_type="observes", target_label="coolant odor")],
                )
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(
                    label="coolant odor",
                    parent_anchor="Signal",
                    description="odor observed near the joint",
                    evidence_ids=["BATOM_002"],
                )
            ],
        )
        decision = AttachmentDecision(
            candidate_id="battery::coolant odor",
            label="coolant odor",
            route="vertical_specialize",
            parent_anchor="Signal",
            accept=True,
            admit_as_node=True,
            reject_reason=None,
            confidence=0.8,
            justification="semantic hint",
            evidence_ids=["BATOM_002"],
        )

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": {decision.candidate_id: decision}},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        workflow_nodes = [node for node in graph.nodes if node.node_type == "workflow_step"]
        workflow_edges = [edge for edge in graph.edges if edge.edge_layer == "workflow"]
        self.assertEqual(len(workflow_nodes), 1)
        self.assertEqual(workflow_nodes[0].step_id, "T1")
        self.assertEqual(workflow_nodes[0].display_label, "Inspect coolant odor (T1)")
        self.assertEqual(workflow_edges[0].workflow_kind, "action_object")
        self.assertEqual(workflow_edges[0].tail, "coolant odor")
        self.assertEqual(workflow_edges[0].raw_label, "observes")
        self.assertEqual(workflow_edges[0].display_label, "inspect")
        self.assertTrue(workflow_edges[0].display_admitted)

    def test_graph_assembly_keeps_hidden_workflow_edges_in_final_graph(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="T1 Perform inspection on asset.",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Perform inspection on the pack asset."),
                    concept_mentions=[],
                    relation_mentions=[
                        RelationMention(
                            label="performed_on",
                            family="task_dependency",
                            head="T1",
                            tail="BatteryPack",
                        )
                    ],
                    step_actions=[StepAction(action_type="performed_on", target_label="BatteryPack")],
                )
            ],
            document_concept_mentions=[ConceptMention(label="BatteryPack", surface_form="BatteryPack")],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[],
        )
        decisions = {
            "battery::BatteryPack": AttachmentDecision(
                candidate_id="battery::BatteryPack",
                label="BatteryPack",
                route="vertical_specialize",
                parent_anchor="Asset",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="asset present",
                evidence_ids=["BATOM_002"],
            )
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        workflow_edges = [edge for edge in graph.edges if edge.edge_layer == "workflow"]
        self.assertEqual(len(workflow_edges), 1)
        self.assertFalse(workflow_edges[0].display_admitted)
        self.assertEqual(workflow_edges[0].display_reject_reason, "workflow_asset_context")

    def test_graph_assembly_preserves_stable_structural_containers(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            step_records=[],
            document_concept_mentions=[
                ConceptMention(label="Helion PackCore-544 AWD", surface_form="Helion PackCore-544 AWD"),
                ConceptMention(label="composite manifold body", surface_form="composite manifold body"),
                ConceptMention(label="front manifold face", surface_form="front manifold face"),
                ConceptMention(label="M6 retaining bolts", surface_form="M6 retaining bolts"),
            ],
            document_relation_mentions=[
                RelationMention(label="contains", family="structural", head="Helion PackCore-544 AWD", tail="composite manifold body"),
                RelationMention(label="contains", family="structural", head="composite manifold body", tail="front manifold face"),
                RelationMention(label="contains", family="structural", head="composite manifold body", tail="M6 retaining bolts"),
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="Helion PackCore-544 AWD", parent_anchor="Asset", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="composite manifold body", parent_anchor="Component", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="front manifold face", parent_anchor="Component", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="M6 retaining bolts", parent_anchor="Component", description="", evidence_ids=["BATOM_002"]),
            ],
        )
        decisions = {
            label: AttachmentDecision(
                candidate_id=label,
                label=label.split("::", 1)[1],
                route="vertical_specialize",
                parent_anchor=anchor,
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            )
            for label, anchor in {
                "battery::Helion PackCore-544 AWD": "Asset",
                "battery::composite manifold body": "Component",
                "battery::front manifold face": "Component",
                "battery::M6 retaining bolts": "Component",
            }.items()
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        edge_tuples = {(edge.head, edge.label, edge.tail) for edge in graph.edges}
        self.assertIn(("Helion PackCore-544 AWD", "contains", "composite manifold body"), edge_tuples)
        self.assertIn(("composite manifold body", "contains", "M6 retaining bolts"), edge_tuples)
        self.assertNotIn(("composite manifold body", "contains", "front manifold face"), edge_tuples)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "structural_low_value_tail"]
        self.assertEqual(len(rejected), 1)

    def test_graph_assembly_rejects_structural_interface_heads(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="nev")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="EVMAN_002",
            domain_id="nev",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            step_records=[],
            document_concept_mentions=[
                ConceptMention(label="service-disconnect cavity", surface_form="service-disconnect cavity"),
                ConceptMention(label="blade set", surface_form="blade set"),
            ],
            document_relation_mentions=[
                RelationMention(
                    label="contains",
                    family="structural",
                    head="service-disconnect cavity",
                    tail="blade set",
                )
            ],
        )
        schema = DomainSchema(
            domain_id="nev",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="service-disconnect cavity", parent_anchor="Component", description="", evidence_ids=["EVMAN_002"]),
                AdapterConcept(label="blade set", parent_anchor="Component", description="", evidence_ids=["EVMAN_002"]),
            ],
        )
        decisions = {
            "nev::service-disconnect cavity": AttachmentDecision(
                candidate_id="nev::service-disconnect cavity",
                label="service-disconnect cavity",
                route="vertical_specialize",
                parent_anchor="Component",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["EVMAN_002"],
            ),
            "nev::blade set": AttachmentDecision(
                candidate_id="nev::blade set",
                label="blade set",
                route="vertical_specialize",
                parent_anchor="Component",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["EVMAN_002"],
            ),
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"nev": [record]},
            schemas={"nev": schema},
            decisions_by_domain={"nev": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["nev"]

        domain_edges = [edge for edge in graph.edges if edge.family != "is_a"]
        self.assertEqual(len(domain_edges), 0)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "structural_contextual_head"]
        self.assertEqual(len(rejected), 1)

    def test_graph_assembly_accepts_cross_step_document_semantic_relations(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Inspect"),
                    concept_mentions=[
                        ConceptMention(label="body off header plate", surface_form="body off header plate"),
                    ],
                    relation_mentions=[],
                ),
                StepEvidenceRecord(
                    step_id="T2",
                    task=StepConceptMention(label="T2", surface_form="Diagnose"),
                    concept_mentions=[
                        ConceptMention(label="hose-induced preload", surface_form="hose-induced preload"),
                    ],
                    relation_mentions=[],
                )
            ],
            document_concept_mentions=[],
            document_relation_mentions=[
                RelationMention(
                    label="indicates",
                    family="communication",
                    head="body off header plate",
                    tail="hose-induced preload",
                )
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="body off header plate", parent_anchor="State", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="hose-induced preload", parent_anchor="Fault", description="", evidence_ids=["BATOM_002"]),
            ],
        )
        decisions = {
            "battery::body off header plate": AttachmentDecision(
                candidate_id="battery::body off header plate",
                label="body off header plate",
                route="vertical_specialize",
                parent_anchor="State",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            ),
            "battery::hose-induced preload": AttachmentDecision(
                candidate_id="battery::hose-induced preload",
                label="hose-induced preload",
                route="vertical_specialize",
                parent_anchor="Fault",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            ),
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        edge_tuples = {(edge.head, edge.label, edge.tail) for edge in graph.edges}
        self.assertIn(("body off header plate", "indicates", "hose-induced preload"), edge_tuples)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "document_local_semantic_relation"]
        self.assertEqual(len(rejected), 0)

    def test_graph_assembly_rejects_single_step_document_semantic_hypotheses(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Inspect"),
                    concept_mentions=[
                        ConceptMention(label="body off header plate", surface_form="body off header plate"),
                        ConceptMention(label="hose-induced preload", surface_form="hose-induced preload"),
                    ],
                    relation_mentions=[],
                )
            ],
            document_concept_mentions=[],
            document_relation_mentions=[
                RelationMention(
                    label="indicates",
                    family="communication",
                    head="body off header plate",
                    tail="hose-induced preload",
                )
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="body off header plate", parent_anchor="State", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="hose-induced preload", parent_anchor="Fault", description="", evidence_ids=["BATOM_002"]),
            ],
        )
        decisions = {
            "battery::body off header plate": AttachmentDecision(
                candidate_id="battery::body off header plate",
                label="body off header plate",
                route="vertical_specialize",
                parent_anchor="State",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            ),
            "battery::hose-induced preload": AttachmentDecision(
                candidate_id="battery::hose-induced preload",
                label="hose-induced preload",
                route="vertical_specialize",
                parent_anchor="Fault",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            ),
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        domain_edges = [edge for edge in graph.edges if edge.family != "is_a"]
        self.assertEqual(len(domain_edges), 0)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "single_step_diagnostic_hypothesis"]
        self.assertEqual(len(rejected), 1)

    def test_graph_assembly_rejects_structural_self_loops(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            document_concept_mentions=[ConceptMention(label="Belleville stack housing", surface_form="Belleville stack housing")],
            document_relation_mentions=[
                RelationMention(
                    label="contains",
                    family="structural",
                    head="Belleville stack housing",
                    tail="Belleville stack housing",
                )
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="Belleville stack housing", parent_anchor="Component", description="", evidence_ids=["BATOM_002"]),
            ],
        )
        decisions = {
            "battery::Belleville stack housing": AttachmentDecision(
                candidate_id="battery::Belleville stack housing",
                label="Belleville stack housing",
                route="vertical_specialize",
                parent_anchor="Component",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            )
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        domain_edges = [edge for edge in graph.edges if edge.family != "is_a"]
        self.assertEqual(len(domain_edges), 0)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "structural_self_loop"]
        self.assertEqual(len(rejected), 1)

    def test_graph_assembly_rejects_multi_target_document_diagnostic_hypotheses(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            role="target",
            source_type="om_manual",
            timestamp="2026-04-22T00:00:00Z",
            raw_text="",
            document_concept_mentions=[
                ConceptMention(label="forced downward hose", surface_form="forced downward hose"),
                ConceptMention(label="hose-induced preload", surface_form="hose-induced preload"),
                ConceptMention(label="manifold warp", surface_form="manifold warp"),
            ],
            document_relation_mentions=[
                RelationMention(
                    label="indicates",
                    family="communication",
                    head="forced downward hose",
                    tail="hose-induced preload",
                ),
                RelationMention(
                    label="indicates",
                    family="communication",
                    head="forced downward hose",
                    tail="manifold warp",
                ),
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Task", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="forced downward hose", parent_anchor="Signal", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="hose-induced preload", parent_anchor="Fault", description="", evidence_ids=["BATOM_002"]),
                AdapterConcept(label="manifold warp", parent_anchor="Fault", description="", evidence_ids=["BATOM_002"]),
            ],
        )
        decisions = {
            f"battery::{label}": AttachmentDecision(
                candidate_id=f"battery::{label}",
                label=label,
                route="vertical_specialize",
                parent_anchor=anchor,
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["BATOM_002"],
            )
            for label, anchor in {
                "forced downward hose": "Signal",
                "hose-induced preload": "Fault",
                "manifold warp": "Fault",
            }.items()
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        domain_edges = [edge for edge in graph.edges if edge.family != "is_a"]
        self.assertEqual(len(domain_edges), 0)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "multi_target_diagnostic_hypothesis"]
        self.assertEqual(len(rejected), 2)

    def test_graphml_exports_dual_layer_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "battery.graphml"
            export_graphml(
                nodes=[
                    GraphNode(
                        node_id="battery::node::BATOM_002:T1",
                        label="BATOM_002:T1",
                        display_label="capture issue context (T1)",
                        domain_id="battery",
                        node_type="workflow_step",
                        node_layer="workflow",
                        surface_form="Observe coolant odor near the joint.",
                        step_id="T1",
                        order_index=1,
                        provenance_evidence_ids=["BATOM_002"],
                    ),
                    GraphNode(
                        node_id="battery::node::coolant odor",
                        label="coolant odor",
                        display_label="coolant odor",
                        domain_id="battery",
                        node_type="adapter_concept",
                        node_layer="semantic",
                        parent_anchor="Signal",
                        provenance_evidence_ids=["BATOM_002"],
                    ),
                    GraphNode(
                        node_id="battery::node::BatteryPack",
                        label="BatteryPack",
                        display_label="BatteryPack",
                        domain_id="battery",
                        node_type="backbone_concept",
                        node_layer="semantic",
                        parent_anchor="Asset",
                        provenance_evidence_ids=["BATOM_002"],
                    )
                ],
                edges=[
                    GraphEdge(
                        edge_id="battery::edge::BATOM_002:T1::observes::coolant odor",
                        domain_id="battery",
                        label="observes",
                        raw_label="observes",
                        display_label="inspect",
                        family="action_object",
                        edge_layer="workflow",
                        workflow_kind="action_object",
                        edge_salience="high",
                        display_admitted=True,
                        head="BATOM_002:T1",
                        tail="coolant odor",
                        provenance_evidence_ids=["BATOM_002"],
                    ),
                    GraphEdge(
                        edge_id="battery::edge::BATOM_002:T1::performed_on::BatteryPack",
                        domain_id="battery",
                        label="performed_on",
                        raw_label="performed_on",
                        display_label="verify",
                        family="action_object",
                        edge_layer="workflow",
                        workflow_kind="action_object",
                        edge_salience="low",
                        display_admitted=False,
                        display_reject_reason="workflow_asset_context",
                        head="BATOM_002:T1",
                        tail="BatteryPack",
                        provenance_evidence_ids=["BATOM_002"],
                    )
                ],
                path=path,
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("display_label", text)
            self.assertIn("raw_label", text)
            self.assertIn("node_layer", text)
            self.assertIn("workflow_kind", text)
            self.assertIn(">inspect<", text)
            self.assertNotIn(">performed_on<", text)

    def test_compute_metrics_reads_optional_workflow_grounding_gold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gold_path = Path(temp_dir) / "gold.json"
            graph_path = Path(temp_dir) / "graph.json"
            gold_payload = {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_002", "doc_type": "om_manual"}],
                "concept_ground_truth": [
                    {"evidence_id": "BATOM_002", "label": "T1", "should_be_in_graph": True, "expected_anchor": "Task"},
                    {"evidence_id": "BATOM_002", "label": "coolant odor", "should_be_in_graph": True, "expected_anchor": "Signal"},
                ],
                "relation_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "head": "T1",
                        "relation": "triggers",
                        "tail": "T2",
                        "family": "task_dependency",
                        "valid": False,
                    }
                ],
                "workflow_relation_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "head": "T1",
                        "relation": "observes",
                        "tail": "coolant odor",
                        "family": "action_object",
                        "valid": True,
                    }
                ],
            }
            graph_payload = {
                "nodes": [
                    {
                        "label": "BATOM_002:T1",
                        "display_label": "capture issue context (T1)",
                        "domain_id": "battery",
                        "node_type": "workflow_step",
                        "node_layer": "workflow",
                        "step_id": "T1",
                        "provenance_evidence_ids": ["BATOM_002"],
                    },
                    {
                        "label": "coolant odor",
                        "display_label": "coolant odor",
                        "domain_id": "battery",
                        "node_type": "adapter_concept",
                        "node_layer": "semantic",
                        "parent_anchor": "Signal",
                        "provenance_evidence_ids": ["BATOM_002"],
                    },
                ],
                "edges": [
                    {
                        "head": "BATOM_002:T1",
                        "label": "observes",
                        "tail": "coolant odor",
                        "raw_label": "observes",
                        "display_label": "inspect",
                        "family": "action_object",
                        "edge_layer": "workflow",
                        "workflow_kind": "action_object",
                        "display_admitted": True,
                        "provenance_evidence_ids": ["BATOM_002"],
                    }
                ],
            }
            gold_path.write_text(json.dumps(gold_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            graph_path.write_text(json.dumps(graph_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            metrics = compute_metrics(gold_path, graph_path)

            self.assertTrue(metrics["workflow_grounding_metrics"]["available"])
            self.assertEqual(metrics["workflow_grounding_metrics"]["f1"], 1.0)
            self.assertEqual(metrics["workflow_grounding_metrics"]["gold_count"], 1)
            self.assertEqual(metrics["workflow_grounding_metrics"]["predicted_count"], 1)
            self.assertIn("diagnostics", metrics)
            self.assertIn("legacy_strict_metrics", metrics["diagnostics"])
            self.assertIn("relation_metrics", metrics["diagnostics"]["legacy_strict_metrics"])
            self.assertNotIn("relation_metrics", metrics)

    def test_v2_step_evidence_record_with_new_fields(self) -> None:
        """Test that StepEvidenceRecord v2 fields are optional and backward compatible."""
        # Old-style construction still works
        old_record = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Inspect seal"),
            concept_mentions=[
                ConceptMention(label="O-ring", shared_hypernym="Seal", semantic_type_hint="Component"),
            ],
            relation_mentions=[
                RelationMention(label="observes", family="task_dependency", head="T1", tail="O-ring"),
            ],
        )
        self.assertIsNone(old_record.step_phase)
        self.assertEqual(old_record.step_actions, [])
        self.assertIsNone(old_record.sequence_next)

        # v2 construction with new fields
        v2_record = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Inspect seal for damage"),
            concept_mentions=[
                ConceptMention(label="O-ring", shared_hypernym="Seal", semantic_type_hint="Component"),
                ConceptMention(label="seepage", shared_hypernym=None, semantic_type_hint="Signal"),
            ],
            relation_mentions=[
                RelationMention(label="observes", family="task_dependency", head="T1", tail="O-ring"),
            ],
            step_phase="observe",
            step_summary="Inspect seal for damage",
            surface_form="Inspect seal for damage",
            step_actions=[StepAction(action_type="observes", target_label="O-ring")],
            structural_edges=[],
            state_transitions=[],
            diagnostic_edges=[],
            sequence_next="T2",
        )
        self.assertEqual(v2_record.step_phase, "observe")
        self.assertEqual(v2_record.step_summary, "Inspect seal for damage")
        self.assertEqual(len(v2_record.step_actions), 1)
        self.assertEqual(v2_record.step_actions[0].action_type, "observes")
        self.assertEqual(v2_record.step_actions[0].target_label, "O-ring")
        self.assertEqual(v2_record.sequence_next, "T2")

    def test_v2_evidence_record_with_procedure_meta_and_cross_step(self) -> None:
        """Test EvidenceRecord with procedure_meta and cross_step_relations."""
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            source_type="om_manual",
            timestamp="2026-04-26T00:00:00Z",
            raw_text="",
            step_records=[
                StepEvidenceRecord(step_id="T1", task=StepConceptMention(label="T1", surface_form="Observe")),
                StepEvidenceRecord(step_id="T2", task=StepConceptMention(label="T2", surface_form="Diagnose")),
            ],
            document_concept_mentions=[
                ConceptMention(label="seepage", shared_hypernym="Media", semantic_type_hint="Signal"),
                ConceptMention(label="corrosion", semantic_type_hint="Fault"),
            ],
            procedure_meta=ProcedureMeta(
                asset_name="pack",
                procedure_type="diagnosis",
                primary_fault_type="seepage",
            ),
            cross_step_relations=[
                CrossStepRelation(
                    label="indicates",
                    family="communication",
                    head="seepage",
                    tail="corrosion",
                    head_step="T1",
                    tail_step="T2",
                ),
            ],
        )
        self.assertIsNotNone(record.procedure_meta)
        self.assertEqual(record.procedure_meta.procedure_type, "diagnosis")
        self.assertEqual(len(record.cross_step_relations), 1)
        self.assertEqual(record.cross_step_relations[0].head_step, "T1")

    def test_v2_graph_assembly_uses_step_phase_and_hypernym(self) -> None:
        """Test that graph assembly propagates step_phase and shared_hypernym to GraphNode."""
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="BATOM_002",
            domain_id="battery",
            source_type="om_manual",
            timestamp="2026-04-26T00:00:00Z",
            raw_text="T1 Inspect O-ring for seepage.",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Inspect O-ring for seepage"),
                    concept_mentions=[
                        ConceptMention(label="O-ring", shared_hypernym="Seal", semantic_type_hint="Component"),
                        ConceptMention(label="seepage", shared_hypernym="Media", semantic_type_hint="Signal"),
                    ],
                    relation_mentions=[
                        RelationMention(label="observes", family="task_dependency", head="T1", tail="O-ring"),
                        RelationMention(label="records", family="task_dependency", head="T1", tail="seepage"),
                    ],
                    step_phase="observe",
                    step_summary="Inspect O-ring for seepage",
                    sequence_next=None,
                ),
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Signal", "State", "Fault", "Seal", "Connector", "Sensor", "Controller", "Coolant", "Actuator", "Power", "Housing", "Fastener", "Media"],
            adapter_concepts=[],
        )
        decisions = {
            "battery::O-ring": AttachmentDecision(
                candidate_id="battery::O-ring",
                label="O-ring",
                route="reuse_backbone",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="backbone label",
                evidence_ids=["BATOM_002"],
            ),
            "battery::seepage": AttachmentDecision(
                candidate_id="battery::seepage",
                label="seepage",
                route="vertical_specialize",
                parent_anchor="Signal",
                accept=True,
                admit_as_node=True,
                confidence=0.9,
                justification="signal hint",
                evidence_ids=["BATOM_002"],
            ),
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        workflow_nodes = [node for node in graph.nodes if node.node_type == "workflow_step"]
        self.assertEqual(len(workflow_nodes), 1)
        self.assertEqual(workflow_nodes[0].step_phase, "observe")

        semantic_nodes = {node.label: node for node in graph.nodes if node.node_layer == "semantic"}
        o_ring_node = semantic_nodes.get("O-ring")
        self.assertIsNotNone(o_ring_node)
        self.assertEqual(o_ring_node.shared_hypernym, "Seal")

    def test_v2_concept_mention_shared_hypernym_roundtrip(self) -> None:
        """Test that shared_hypernym survives JSON round-trip."""
        mention = ConceptMention(
            label="coolant hose",
            description="coolant delivery hose",
            semantic_type_hint="Component",
            shared_hypernym="Coolant",
        )
        data = mention.model_dump(mode="json")
        restored = ConceptMention.model_validate(data)
        self.assertEqual(restored.shared_hypernym, "Coolant")

    def test_v2_filtering_uses_hypernym_as_anchor_fallback(self) -> None:
        """Test that filtering uses shared_hypernym as anchor fallback."""
        candidate = SimpleNamespace(
            label="O-ring",
            description="EPDM O-ring seal",
            evidence_ids=["BATOM_002"],
            routing_features={"semantic_type_hint": None, "shared_hypernym": "Seal"},
        )
        from rules.filtering import preferred_parent_anchor
        anchor = preferred_parent_anchor(candidate)
        self.assertEqual(anchor, "Seal")

    def test_v2_step_action_edges_from_v2_fields(self) -> None:
        """Test that _step_action_edges uses v2 step_actions when available."""
        from pipeline.graph import _step_action_edges
        step = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Inspect seal"),
            concept_mentions=[ConceptMention(label="O-ring")],
            relation_mentions=[
                RelationMention(label="observes", family="task_dependency", head="T1", tail="O-ring"),
            ],
            step_actions=[StepAction(action_type="inspects", target_label="O-ring")],
        )
        edges = _step_action_edges(step)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0][0], "inspects")
        self.assertEqual(edges[0][1], "O-ring")

        # No fallback: relation_mentions are not an action-object source.
        step_no_v2 = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Inspect seal"),
            concept_mentions=[ConceptMention(label="O-ring")],
            relation_mentions=[
                RelationMention(label="observes", family="task_dependency", head="T1", tail="O-ring"),
            ],
        )
        edges_fallback = _step_action_edges(step_no_v2)
        self.assertEqual(edges_fallback, [])

    def test_v2_sequence_edges_from_sequence_next(self) -> None:
        """Test that _step_sequence_edges uses v2 sequence_next when available."""
        from pipeline.graph import _step_sequence_edges
        step = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Observe"),
            relation_mentions=[
                RelationMention(label="triggers", family="task_dependency", head="T1", tail="T2"),
            ],
            sequence_next="T2",
        )
        edges = _step_sequence_edges(step)
        self.assertEqual(edges, [("T1", "T2")])

        # No fallback: relation_mentions are not a sequence source.
        step_no_v2 = StepEvidenceRecord(
            step_id="T1",
            task=StepConceptMention(label="T1", surface_form="Observe"),
            relation_mentions=[
                RelationMention(label="triggers", family="task_dependency", head="T1", tail="T2"),
            ],
        )
        edges_fallback = _step_sequence_edges(step_no_v2)
        self.assertEqual(edges_fallback, [])

    def test_v2_only_authoritative_workflow_sources(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="DOC1",
            domain_id="battery",
            source_type="om_manual",
            timestamp="2026-04-26T00:00:00Z",
            raw_text="",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Inspect seal"),
                    concept_mentions=[ConceptMention(label="seal leak", semantic_type_hint="Fault")],
                    relation_mentions=[
                        RelationMention(label="triggers", family="task_dependency", head="T1", tail="T9"),
                        RelationMention(label="observes", family="task_dependency", head="T1", tail="legacy target"),
                    ],
                    step_actions=[StepAction(action_type="inspects", target_label="seal leak")],
                    sequence_next="T2",
                ),
                StepEvidenceRecord(
                    step_id="T2",
                    task=StepConceptMention(label="T2", surface_form="Verify repair"),
                ),
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Signal", "State", "Fault"],
            adapter_concepts=[AdapterConcept(label="seal leak", parent_anchor="Fault", description="", evidence_ids=["DOC1"])],
        )
        decisions = {
            "battery::seal leak": AttachmentDecision(
                candidate_id="battery::seal leak",
                label="seal leak",
                route="vertical_specialize",
                parent_anchor="Fault",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["DOC1"],
            )
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        workflow_edges = [edge for edge in graph.edges if edge.edge_layer == "workflow"]
        workflow_tuples = {(edge.head, edge.label, edge.tail, edge.workflow_kind, edge.source_field) for edge in workflow_edges}
        self.assertIn(("DOC1:T1", "triggers", "DOC1:T2", "sequence", "sequence_next"), workflow_tuples)
        self.assertIn(("DOC1:T1", "inspects", "seal leak", "action_object", "step_actions"), workflow_tuples)
        self.assertNotIn(("DOC1:T1", "triggers", "DOC1:T9", "sequence", "relation_mentions"), workflow_tuples)
        self.assertNotIn(("DOC1:T1", "observes", "legacy target", "action_object", "relation_mentions"), workflow_tuples)

    def test_cross_step_relations_annotate_existing_semantic_edge(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(
                relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]
            ),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(
            write_temporal_metadata=False,
            enable_snapshots=False,
            detect_lifecycle_events=False,
            variant_id="test_variant",
        )
        record = EvidenceRecord(
            evidence_id="DOC2",
            domain_id="battery",
            source_type="om_manual",
            timestamp="2026-04-26T00:00:00Z",
            raw_text="",
            step_records=[
                StepEvidenceRecord(
                    step_id="T1",
                    task=StepConceptMention(label="T1", surface_form="Observe"),
                    concept_mentions=[ConceptMention(label="seepage trace", semantic_type_hint="Signal")],
                ),
                StepEvidenceRecord(
                    step_id="T2",
                    task=StepConceptMention(label="T2", surface_form="Diagnose"),
                    concept_mentions=[ConceptMention(label="seal failure", semantic_type_hint="Fault")],
                ),
            ],
            document_relation_mentions=[
                RelationMention(label="indicates", family="communication", head="seepage trace", tail="seal failure")
            ],
            cross_step_relations=[
                CrossStepRelation(
                    label="indicates",
                    family="communication",
                    head="seepage trace",
                    tail="seal failure",
                    head_step="T1",
                    tail_step="T2",
                )
            ],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=["Asset", "Component", "Signal", "State", "Fault"],
            adapter_concepts=[
                AdapterConcept(label="seepage trace", parent_anchor="Signal", description="", evidence_ids=["DOC2"]),
                AdapterConcept(label="seal failure", parent_anchor="Fault", description="", evidence_ids=["DOC2"]),
            ],
        )
        decisions = {
            f"battery::{label}": AttachmentDecision(
                candidate_id=f"battery::{label}",
                label=label,
                route="vertical_specialize",
                parent_anchor=anchor,
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["DOC2"],
            )
            for label, anchor in {"seepage trace": "Signal", "seal failure": "Fault"}.items()
        }

        graph = assemble_domain_graphs(
            config=config,
            variant=variant,
            records_by_domain={"battery": [record]},
            schemas={"battery": schema},
            decisions_by_domain={"battery": decisions},
            backbone_concepts=schema.backbone_concepts,
        )["battery"]

        communication_edges = [edge for edge in graph.edges if edge.family == "communication"]
        self.assertEqual(len(communication_edges), 1)
        self.assertEqual(communication_edges[0].head_step, "T1")
        self.assertEqual(communication_edges[0].tail_step, "T2")
        self.assertEqual(communication_edges[0].source_field, "cross_step_relations")

    def test_backbone_nodes_and_adapter_is_a_edges_are_materialized(self) -> None:
        config = SimpleNamespace(
            relations=SimpleNamespace(relation_families=["task_dependency", "communication", "propagation", "lifecycle", "structural"]),
            runtime=SimpleNamespace(enable_relation_validation=False, relation_constraints_path=None),
            domains=[SimpleNamespace(domain_id="battery")],
        )
        variant = SimpleNamespace(write_temporal_metadata=False, enable_snapshots=False, detect_lifecycle_events=False, variant_id="test")
        backbone = ["Asset", "Component", "Signal", "State", "Fault", "Seal", "Connector", "Sensor", "Controller", "Coolant", "Actuator", "Power", "Housing", "Fastener", "Media"]
        record = EvidenceRecord(
            evidence_id="DOC3",
            domain_id="battery",
            source_type="om_manual",
            timestamp="2026-04-26T00:00:00Z",
            raw_text="",
            document_concept_mentions=[ConceptMention(label="coolant hose", semantic_type_hint="Component")],
        )
        schema = DomainSchema(
            domain_id="battery",
            backbone_concepts=backbone,
            adapter_concepts=[AdapterConcept(label="coolant hose", parent_anchor="Coolant", description="", evidence_ids=["DOC3"])],
        )
        decisions = {
            "battery::coolant hose": AttachmentDecision(
                candidate_id="battery::coolant hose",
                label="coolant hose",
                route="vertical_specialize",
                parent_anchor="Coolant",
                accept=True,
                admit_as_node=True,
                confidence=1.0,
                justification="test",
                evidence_ids=["DOC3"],
            )
        }

        graph = assemble_domain_graphs(config, variant, {"battery": [record]}, {"battery": schema}, {"battery": decisions}, backbone)["battery"]

        backbone_nodes = [node for node in graph.nodes if node.node_type == "backbone_concept"]
        self.assertEqual(len(backbone_nodes), 15)
        self.assertIn(("coolant hose", "is_a", "Coolant"), {(edge.head, edge.label, edge.tail) for edge in graph.edges})

    def test_snapshot_export_does_not_require_detailed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            node = GraphNode(
                node_id="battery::node::Asset",
                label="Asset",
                display_label="Asset",
                domain_id="battery",
                node_type="backbone_concept",
            )
            graph = DomainGraphArtifacts(
                domain_id="battery",
                nodes=[node],
                edges=[],
                snapshots=[
                    SnapshotManifest(
                        snapshot_id="battery-snapshot-001",
                        domain_id="battery",
                        created_at="2026-04-26T00:00:00Z",
                        node_count=1,
                        edge_count=0,
                    )
                ],
                snapshot_states=[SnapshotState(snapshot_id="battery-snapshot-001", nodes=[node], edges=[])],
            )
            result = VariantRunResult(
                variant_id="full_llm",
                variant_description="test",
                seed_backbone_concepts=["Asset"],
                seed_backbone_descriptions={"Asset": "asset"},
                backbone_concepts=["Asset"],
                backbone_descriptions={"Asset": "asset"},
                evidence_units=[],
                candidates_by_domain={"battery": []},
                retrievals={"battery": {}},
                attachment_decisions={"battery": {}},
                schemas={"battery": DomainSchema(domain_id="battery", backbone_concepts=["Asset"])},
                domain_graphs={"battery": graph},
                construction_summary={},
            )

            export_variant_run(
                Path(temp_dir) / "full_llm",
                result,
                write_detailed_working_artifacts=False,
                write_jsonl_artifacts=False,
                write_graphml=False,
                write_property_graph_jsonl=False,
                write_graph_db_csv=False,
            )
            state = load_snapshot_state(Path(temp_dir) / "full_llm", "battery", "battery-snapshot-001")
            self.assertEqual(state["consistency"]["node_count"], 1)


if __name__ == "__main__":
    unittest.main()
