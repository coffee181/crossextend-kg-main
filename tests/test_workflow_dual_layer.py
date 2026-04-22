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
    DomainSchema,
    EvidenceRecord,
    GraphEdge,
    GraphNode,
    RelationMention,
    StepConceptMention,
    StepEvidenceRecord,
)
from pipeline.exports.graphml import export_graphml
from pipeline.graph import assemble_domain_graphs
from rules.filtering import filter_attachment_decision


class WorkflowDualLayerTests(unittest.TestCase):
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
                    "tail": "coolant odor",
                    "family": "task_dependency",
                    "edge_layer": "workflow",
                    "workflow_kind": "action_object",
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
        self.assertNotIn(("T1", "observes", "coolant odor", "task_dependency"), relation_set)
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
        self.assertEqual(workflow_edges[0].workflow_kind, "action_object")
        self.assertEqual(workflow_edges[0].tail, "coolant odor")

    def test_graph_assembly_normalizes_structural_interface_container_edges(self) -> None:
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
        self.assertIn(("Helion PackCore-544 AWD", "contains", "front manifold face"), edge_tuples)
        self.assertIn(("front manifold face", "contains", "composite manifold body"), edge_tuples)
        self.assertIn(("front manifold face", "contains", "M6 retaining bolts"), edge_tuples)

    def test_graph_assembly_filters_document_local_semantic_relations(self) -> None:
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

        edge_tuples = {(edge.head, edge.label, edge.tail) for edge in graph.edges}
        self.assertNotIn(("body off header plate", "indicates", "hose-induced preload"), edge_tuples)
        rejected = [triple for triple in graph.triples if triple.reject_reason == "document_local_semantic_relation"]
        self.assertEqual(len(rejected), 1)

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
                    )
                ],
                edges=[
                    GraphEdge(
                        edge_id="battery::edge::BATOM_002:T1::observes::coolant odor",
                        domain_id="battery",
                        label="observes",
                        family="task_dependency",
                        edge_layer="workflow",
                        workflow_kind="action_object",
                        head="BATOM_002:T1",
                        tail="coolant odor",
                        provenance_evidence_ids=["BATOM_002"],
                    )
                ],
                path=path,
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("display_label", text)
            self.assertIn("node_layer", text)
            self.assertIn("workflow_kind", text)

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
                        "family": "task_dependency",
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
                        "family": "task_dependency",
                        "edge_layer": "workflow",
                        "workflow_kind": "action_object",
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


if __name__ == "__main__":
    unittest.main()
