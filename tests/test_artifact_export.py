from __future__ import annotations

from pathlib import Path

from crossextend_kg.models import (
    AttachmentDecision,
    CandidateTriple,
    DomainGraphArtifacts,
    DomainSchema,
    EvidenceUnit,
    GraphEdge,
    GraphNode,
    MemoryEntry,
    SchemaCandidate,
    SnapshotManifest,
    SnapshotState,
    VariantRunResult,
)
from crossextend_kg.pipeline.artifacts import export_variant_run


def _build_result() -> VariantRunResult:
    node = GraphNode(
        node_id="battery::node::BATOM_002:T1",
        label="BATOM_002:T1",
        domain_id="battery",
        node_type="adapter_concept",
        parent_anchor="Task",
        surface_form="Inspect connector condition.",
        provenance_evidence_ids=["BATOM_002"],
    )
    edge = GraphEdge(
        edge_id="battery::edge::BATOM_002:T1::observes::coolant level",
        domain_id="battery",
        label="observes",
        family="task_dependency",
        head="BATOM_002:T1",
        tail="coolant level",
        provenance_evidence_ids=["BATOM_002"],
    )
    triple = CandidateTriple(
        triple_id="battery::triple::BATOM_002::1",
        domain_id="battery",
        head="BATOM_002:T1",
        relation="observes",
        tail="coolant level",
        relation_family="task_dependency",
        evidence_ids=["BATOM_002"],
        attachment_refs=["battery::BATOM_002:T1", "battery::coolant level"],
        confidence=1.0,
        status="accepted",
    )
    snapshot = SnapshotManifest(
        snapshot_id="battery-snapshot-001",
        domain_id="battery",
        created_at="2026-04-20T00:00:00Z",
        parent_snapshot_id=None,
        accepted_schema_ids=["battery::BATOM_002:T1", "battery::coolant level"],
        accepted_triple_ids=["battery::triple::BATOM_002::1"],
        consistency_results_path="snapshots/battery-snapshot-001/consistency.json",
        notes="test",
        node_count=1,
        edge_count=1,
        accepted_evidence_ids=["BATOM_002"],
    )

    return VariantRunResult(
        variant_id="full_llm",
        variant_description="test",
        seed_backbone_concepts=["Task", "Signal"],
        seed_backbone_descriptions={"Task": "task", "Signal": "signal"},
        backbone_concepts=["Task", "Signal"],
        backbone_descriptions={"Task": "task", "Signal": "signal"},
        curated_backbone_concepts=[],
        evidence_units=[
            EvidenceUnit(
                evidence_id="BATOM_002",
                domain_id="battery",
                source_id="battery_evidence_records_llm.json",
                source_type="om_manual",
                locator="battery/om_manual/0",
                raw_text="| T1 | Inspect connector condition. |",
                normalized_text="| T1 | Inspect connector condition. |",
                metadata={"timestamp": "2026-04-20T00:00:00Z"},
            )
        ],
        candidates_by_domain={
            "battery": [
                SchemaCandidate(
                    candidate_id="battery::BATOM_002:T1",
                    domain_id="battery",
                    label="BATOM_002:T1",
                    description="",
                    evidence_ids=["BATOM_002"],
                    evidence_texts=["Inspect connector condition."],
                    routing_features={
                        "is_task_candidate": True,
                        "task_step_id": "T1",
                        "task_evidence_id": "BATOM_002",
                    },
                ),
                SchemaCandidate(
                    candidate_id="battery::coolant level",
                    domain_id="battery",
                    label="coolant level",
                    description="measured coolant level",
                    evidence_ids=["BATOM_002"],
                    evidence_texts=["coolant level"],
                    routing_features={"semantic_type_hint": "Signal"},
                ),
            ]
        },
        retrievals={"battery": {"battery::coolant level": []}},
        historical_context_by_domain={"battery": {"battery::coolant level": []}},
        attachment_decisions={
            "battery": {
                "battery::BATOM_002:T1": AttachmentDecision(
                    candidate_id="battery::BATOM_002:T1",
                    label="BATOM_002:T1",
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
        },
        schemas={
            "battery": DomainSchema(
                domain_id="battery",
                backbone_concepts=["Task", "Signal"],
            )
        },
        domain_graphs={
            "battery": DomainGraphArtifacts(
                domain_id="battery",
                nodes=[node],
                edges=[edge],
                triples=[triple],
                temporal_assertions=[],
                snapshots=[snapshot],
                snapshot_states=[SnapshotState(snapshot_id="battery-snapshot-001", nodes=[node], edges=[edge])],
            )
        },
        construction_summary={"variant_id": "full_llm"},
        memory_entries=[
            MemoryEntry(
                memory_id="test::memory",
                entry_type="attachment",
                domain_id="battery",
                timestamp="2026-04-20T00:00:00Z",
                summary="test",
            )
        ],
    )


def test_export_variant_run_minimizes_working_artifacts_by_default(tmp_path: Path) -> None:
    result = _build_result()
    run_dir = tmp_path / "run"

    export_variant_run(
        run_dir=run_dir,
        result=result,
        write_detailed_working_artifacts=False,
        write_jsonl_artifacts=True,
        write_property_graph_jsonl=True,
        write_graph_db_csv=True,
    )

    domain_root = run_dir / "working" / "battery"
    assert (run_dir / "run_meta.json").exists()
    assert (run_dir / "backbone_final.json").exists()
    assert (run_dir / "construction_summary.json").exists()
    assert (run_dir / "temporal_memory_entries.jsonl").exists()
    assert (domain_root / "attachment_audit.json").exists()
    assert (domain_root / "final_graph.json").exists()
    assert (domain_root / "snapshots" / "battery-snapshot-001" / "nodes.jsonl").exists()

    assert not (run_dir / "data_flow_trace.json").exists()
    assert not (domain_root / "adapter_candidates.json").exists()
    assert not (domain_root / "retrievals.json").exists()
    assert not (domain_root / "exports").exists()
