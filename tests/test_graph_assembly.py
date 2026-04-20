from __future__ import annotations

from crossextend_kg.config import PipelineConfig, VariantConfig
from crossextend_kg.models import (
    AttachmentDecision,
    ConceptMention,
    EvidenceRecord,
    SchemaCandidate,
    StepConceptMention,
    StepRecord,
    RelationMention,
)
from crossextend_kg.pipeline.graph import assemble_domain_graphs, build_domain_schemas


def _build_config() -> PipelineConfig:
    return PipelineConfig.model_validate(
        {
            "project_name": "test",
            "benchmark_name": "test",
            "prompts": {"attachment_judge_template_path": "unused"},
            "llm": {
                "base_url": "https://api.deepseek.com",
                "api_key": "test",
                "model": "deepseek-chat",
            },
            "embedding": {
                "base_url": "http://127.0.0.1:11434/v1",
                "api_key": "",
                "model": "bge-m3:latest",
            },
            "backbone": {
                "seed_concepts": ["Task", "Signal"],
                "seed_descriptions": {
                    "Task": "task",
                    "Signal": "signal",
                },
            },
            "relations": {
                "relation_families": [
                    "task_dependency",
                    "communication",
                    "propagation",
                    "lifecycle",
                    "structural",
                ],
                "family_descriptions": {},
                "allowed_routes": ["reuse_backbone", "vertical_specialize", "reject"],
            },
            "data": {"normalize_whitespace": True},
            "runtime": {
                "artifact_root": "artifacts",
                "retrieval_top_k": 3,
                "llm_attachment_batch_size": 8,
                "enable_temporal_memory_bank": False,
                "temporal_memory_top_k": 3,
                "temporal_memory_max_entries": 100,
                "save_latest_summary": False,
                "write_detailed_working_artifacts": False,
                "write_jsonl_artifacts": False,
                "write_graph_db_csv": False,
                "write_property_graph_jsonl": False,
                "run_prefix": "test",
                "relation_constraints_path": None,
                "enable_relation_validation": False,
            },
            "variants": [
                {
                    "variant_id": "full_llm",
                    "description": "test",
                    "attachment_strategy": "llm",
                    "use_embedding_routing": False,
                    "use_rule_filter": False,
                    "allow_free_form_growth": False,
                    "enable_snapshots": True,
                    "enable_memory_bank": False,
                    "export_artifacts": False,
                }
            ],
            "domains": [
                {
                    "domain_id": "battery",
                    "domain_name": "Battery",
                    "role": "target",
                    "data_path": "unused.json",
                    "source_types": ["om_manual"],
                    "domain_keywords": [],
                }
            ],
        }
    )


def test_graph_assembly_resolves_step_ids_to_scoped_task_nodes() -> None:
    config = _build_config()
    variant = VariantConfig.model_validate(config.variants[0].model_dump(mode="json"))
    record = EvidenceRecord(
        evidence_id="BATOM_001",
        domain_id="battery",
        source_type="om_manual",
        timestamp="2026-04-19T00:00:00Z",
        raw_text="| T1 | Inspect coolant level. |",
        step_records=[
            StepRecord(
                step_id="T1",
                task=StepConceptMention(label="T1", surface_form="Inspect coolant level."),
                concept_mentions=[
                    ConceptMention(label="coolant level", description="measured coolant level", surface_form="coolant level")
                ],
                relation_mentions=[
                    RelationMention(label="observes", family="task_dependency", head="T1", tail="coolant level"),
                    RelationMention(label="triggers", family="task_dependency", head="T1", tail="T2"),
                ],
            ),
            StepRecord(
                step_id="T2",
                task=StepConceptMention(label="T2", surface_form="Close inspection."),
            ),
        ],
    )

    candidates_by_domain = {
        "battery": [
            SchemaCandidate(
                candidate_id="battery::BATOM_001:T1",
                domain_id="battery",
                label="BATOM_001:T1",
                description="",
                evidence_ids=["BATOM_001"],
                routing_features={"is_task_candidate": True, "task_step_id": "T1", "task_evidence_id": "BATOM_001"},
            ),
            SchemaCandidate(
                candidate_id="battery::BATOM_001:T2",
                domain_id="battery",
                label="BATOM_001:T2",
                description="",
                evidence_ids=["BATOM_001"],
                routing_features={"is_task_candidate": True, "task_step_id": "T2", "task_evidence_id": "BATOM_001"},
            ),
            SchemaCandidate(
                candidate_id="battery::coolant level",
                domain_id="battery",
                label="coolant level",
                description="measured coolant level",
                evidence_ids=["BATOM_001"],
                routing_features={"semantic_type_hint": "Signal"},
            ),
        ]
    }
    decisions_by_domain = {
        "battery": {
            "battery::BATOM_001:T1": AttachmentDecision(
                candidate_id="battery::BATOM_001:T1",
                label="BATOM_001:T1",
                route="vertical_specialize",
                parent_anchor="Task",
                accept=True,
                admit_as_node=True,
            ),
            "battery::BATOM_001:T2": AttachmentDecision(
                candidate_id="battery::BATOM_001:T2",
                label="BATOM_001:T2",
                route="vertical_specialize",
                parent_anchor="Task",
                accept=True,
                admit_as_node=True,
            ),
            "battery::coolant level": AttachmentDecision(
                candidate_id="battery::coolant level",
                label="coolant level",
                route="vertical_specialize",
                parent_anchor="Signal",
                accept=True,
                admit_as_node=True,
            ),
        }
    }

    schemas = build_domain_schemas(
        config=config,
        candidates_by_domain=candidates_by_domain,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )
    graphs = assemble_domain_graphs(
        config=config,
        variant=variant,
        records_by_domain={"battery": [record]},
        schemas=schemas,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )

    graph = graphs["battery"]
    node_labels = {node.label for node in graph.nodes}
    assert "BATOM_001:T1" in node_labels
    assert "BATOM_001:T2" in node_labels
    assert "coolant level" in node_labels

    edge_labels = {(edge.head, edge.label, edge.tail) for edge in graph.edges}
    assert ("BATOM_001:T1", "triggers", "BATOM_001:T2") in edge_labels
    assert ("BATOM_001:T1", "observes", "coolant level") not in edge_labels

    snapshot = graph.snapshots[0]
    assert "battery::BATOM_001:T1" in snapshot.accepted_schema_ids
    assert "battery::BATOM_001:T2" in snapshot.accepted_schema_ids


def test_graph_assembly_keeps_non_step_task_dependency_only_in_evidence_layer() -> None:
    config = _build_config()
    variant = VariantConfig.model_validate(config.variants[0].model_dump(mode="json"))
    record = EvidenceRecord(
        evidence_id="BATOM_001",
        domain_id="battery",
        source_type="om_manual",
        timestamp="2026-04-19T00:00:00Z",
        raw_text="| T1 | Inspect coolant level. |",
        step_records=[
            StepRecord(
                step_id="T1",
                task=StepConceptMention(label="T1", surface_form="Inspect coolant level."),
                concept_mentions=[
                    ConceptMention(label="coolant level", description="measured coolant level", surface_form="coolant level")
                ],
                relation_mentions=[
                    RelationMention(label="observes", family="task_dependency", head="T1", tail="coolant level"),
                    RelationMention(label="triggers", family="task_dependency", head="T1", tail="T2"),
                ],
            ),
            StepRecord(
                step_id="T2",
                task=StepConceptMention(label="T2", surface_form="Close inspection."),
            ),
        ],
    )

    candidates_by_domain = {
        "battery": [
            SchemaCandidate(
                candidate_id="battery::BATOM_001:T1",
                domain_id="battery",
                label="BATOM_001:T1",
                description="",
                evidence_ids=["BATOM_001"],
                routing_features={"is_task_candidate": True, "task_step_id": "T1", "task_evidence_id": "BATOM_001"},
            ),
            SchemaCandidate(
                candidate_id="battery::BATOM_001:T2",
                domain_id="battery",
                label="BATOM_001:T2",
                description="",
                evidence_ids=["BATOM_001"],
                routing_features={"is_task_candidate": True, "task_step_id": "T2", "task_evidence_id": "BATOM_001"},
            ),
            SchemaCandidate(
                candidate_id="battery::coolant level",
                domain_id="battery",
                label="coolant level",
                description="measured coolant level",
                evidence_ids=["BATOM_001"],
                routing_features={"semantic_type_hint": "Signal"},
            ),
        ]
    }
    decisions_by_domain = {
        "battery": {
            "battery::BATOM_001:T1": AttachmentDecision(
                candidate_id="battery::BATOM_001:T1",
                label="BATOM_001:T1",
                route="vertical_specialize",
                parent_anchor="Task",
                accept=True,
                admit_as_node=True,
            ),
            "battery::BATOM_001:T2": AttachmentDecision(
                candidate_id="battery::BATOM_001:T2",
                label="BATOM_001:T2",
                route="vertical_specialize",
                parent_anchor="Task",
                accept=True,
                admit_as_node=True,
            ),
            "battery::coolant level": AttachmentDecision(
                candidate_id="battery::coolant level",
                label="coolant level",
                route="vertical_specialize",
                parent_anchor="Signal",
                accept=True,
                admit_as_node=True,
            ),
        }
    }

    schemas = build_domain_schemas(
        config=config,
        candidates_by_domain=candidates_by_domain,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )
    graphs = assemble_domain_graphs(
        config=config,
        variant=variant,
        records_by_domain={"battery": [record]},
        schemas=schemas,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )

    graph = graphs["battery"]
    edge_labels = {(edge.head, edge.label, edge.tail) for edge in graph.edges}
    assert ("BATOM_001:T1", "triggers", "BATOM_001:T2") in edge_labels
    assert ("BATOM_001:T1", "observes", "coolant level") not in edge_labels


def test_graph_assembly_rejects_contextual_structural_heads() -> None:
    config = _build_config()
    variant = VariantConfig.model_validate(config.variants[0].model_dump(mode="json"))
    record = EvidenceRecord(
        evidence_id="BATOM_002",
        domain_id="battery",
        source_type="om_manual",
        timestamp="2026-04-19T00:00:00Z",
        raw_text="| T1 | Inspect cooling branch relation. |",
        document_concept_mentions=[
            ConceptMention(label="cooling branch", description="branch section", surface_form="cooling branch"),
            ConceptMention(label="green O-ring", description="seal ring", surface_form="green O-ring"),
        ],
        document_relation_mentions=[
            RelationMention(label="contains", family="structural", head="cooling branch", tail="green O-ring")
        ],
        step_records=[
            StepRecord(
                step_id="T1",
                task=StepConceptMention(label="T1", surface_form="Inspect cooling branch relation."),
            )
        ],
    )

    candidates_by_domain = {
        "battery": [
            SchemaCandidate(
                candidate_id="battery::BATOM_002:T1",
                domain_id="battery",
                label="BATOM_002:T1",
                description="",
                evidence_ids=["BATOM_002"],
                routing_features={"is_task_candidate": True, "task_step_id": "T1", "task_evidence_id": "BATOM_002"},
            ),
            SchemaCandidate(
                candidate_id="battery::cooling branch",
                domain_id="battery",
                label="cooling branch",
                description="branch section",
                evidence_ids=["BATOM_002"],
                routing_features={"semantic_type_hint": "Component"},
            ),
            SchemaCandidate(
                candidate_id="battery::green O-ring",
                domain_id="battery",
                label="green O-ring",
                description="seal ring",
                evidence_ids=["BATOM_002"],
                routing_features={"semantic_type_hint": "Component"},
            ),
        ]
    }
    decisions_by_domain = {
        "battery": {
            "battery::BATOM_002:T1": AttachmentDecision(
                candidate_id="battery::BATOM_002:T1",
                label="BATOM_002:T1",
                route="vertical_specialize",
                parent_anchor="Task",
                accept=True,
                admit_as_node=True,
            ),
            "battery::cooling branch": AttachmentDecision(
                candidate_id="battery::cooling branch",
                label="cooling branch",
                route="vertical_specialize",
                parent_anchor="Component",
                accept=True,
                admit_as_node=True,
            ),
            "battery::green O-ring": AttachmentDecision(
                candidate_id="battery::green O-ring",
                label="green O-ring",
                route="vertical_specialize",
                parent_anchor="Component",
                accept=True,
                admit_as_node=True,
            ),
        }
    }

    schemas = build_domain_schemas(
        config=config,
        candidates_by_domain=candidates_by_domain,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )
    graphs = assemble_domain_graphs(
        config=config,
        variant=variant,
        records_by_domain={"battery": [record]},
        schemas=schemas,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=["Task", "Signal"],
    )

    graph = graphs["battery"]
    edge_labels = {(edge.head, edge.label, edge.tail) for edge in graph.edges}

    assert ("cooling branch", "contains", "green O-ring") not in edge_labels
