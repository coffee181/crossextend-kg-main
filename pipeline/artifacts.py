#!/usr/bin/env python3
"""Artifact export and snapshot replay helpers."""

from __future__ import annotations

from pathlib import Path

try:
    from crossextend_kg.file_io import ensure_dir, read_json, read_jsonl, write_csv, write_json, write_jsonl
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import ensure_dir, read_json, read_jsonl, write_csv, write_json, write_jsonl
try:
    from crossextend_kg.models import PipelineBenchmarkResult, VariantRunResult
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import PipelineBenchmarkResult, VariantRunResult
from pipeline.exports.graphml import export_domain_graphml
from pipeline.utils import utc_now

ADAPTER_ROUTES = {"vertical_specialize"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"


def _graphml_variant_root(run_root: Path, variant_id: str) -> Path:
    graphml_root = PROJECT_ROOT / "graphml"
    try:
        relative_run_root = run_root.resolve().relative_to(PROJECT_ARTIFACTS_ROOT.resolve())
        return graphml_root / relative_run_root / variant_id
    except ValueError:
        return graphml_root / run_root.name / variant_id


def _build_backbone_seed_payload(result: VariantRunResult) -> dict[str, object]:
    return {
        "concepts": result.seed_backbone_concepts,
        "descriptions": result.seed_backbone_descriptions,
        "count": len(result.seed_backbone_concepts),
    }


def _build_backbone_final_payload(result: VariantRunResult) -> dict[str, object]:
    """Build the final predefined backbone payload."""
    return {
        "concepts": result.backbone_concepts,
        "descriptions": result.backbone_descriptions,
        "seed_concepts": result.seed_backbone_concepts,
        "curated_concepts": result.curated_backbone_concepts,
        "counts": {
            "seed": len(result.seed_backbone_concepts),
            "curated": len(result.curated_backbone_concepts),
            "final": len(result.backbone_concepts),
        },
    }


def _build_candidate_payloads(result: VariantRunResult, domain_id: str) -> list[dict[str, object]]:
    backbone_labels = set(result.backbone_concepts)
    retrievals = result.retrievals[domain_id]
    decisions = result.attachment_decisions[domain_id]
    payloads: list[dict[str, object]] = []
    for candidate in result.candidates_by_domain[domain_id]:
        decision = decisions[candidate.candidate_id]
        payloads.append(
            {
                "candidate": candidate.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
                "retrievals": [item.model_dump(mode="json") for item in retrievals.get(candidate.candidate_id, [])],
                "is_existing_backbone_label": candidate.label in backbone_labels,
                "accepted_as_adapter": decision.admit_as_node and decision.route in ADAPTER_ROUTES,
                "accepted_as_backbone_reuse": decision.admit_as_node and decision.route == "reuse_backbone",
                "rejected": not decision.admit_as_node,
            }
        )
    return payloads


def _group_rejected_candidates_by_reason(candidate_payloads: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in candidate_payloads:
        if not item["rejected"]:
            continue
        decision = item["decision"]
        reason = str(decision.get("reject_reason") or "unspecified")
        grouped.setdefault(reason, []).append(item)
    return grouped


def _build_final_graph_payload(result: VariantRunResult, domain_id: str) -> dict[str, object]:
    graph_root = result.domain_graphs[domain_id]
    accepted_triples = [triple for triple in graph_root.triples if triple.status == "accepted"]
    rejected_triples = [triple for triple in graph_root.triples if triple.status == "rejected"]
    rejected_type_triples = [triple for triple in graph_root.triples if triple.status == "rejected_type"]
    workflow_nodes = [node for node in graph_root.nodes if node.node_layer == "workflow"]
    semantic_nodes = [node for node in graph_root.nodes if node.node_layer == "semantic"]
    workflow_edges = [edge for edge in graph_root.edges if edge.edge_layer == "workflow"]
    semantic_edges = [edge for edge in graph_root.edges if edge.edge_layer == "semantic"]

    total_triples = len(graph_root.triples)
    type_rejected_count = len(rejected_type_triples)

    return {
        "domain_id": domain_id,
        "summary": {
            "node_count": len(graph_root.nodes),
            "edge_count": len(graph_root.edges),
            "workflow_step_node_count": len(workflow_nodes),
            "semantic_node_count": len(semantic_nodes),
            "workflow_edge_count": len(workflow_edges),
            "semantic_edge_count": len(semantic_edges),
            "candidate_triple_count": len(graph_root.triples),
            "accepted_triple_count": len(accepted_triples),
            "rejected_triple_count": len(rejected_triples),
            "type_rejected_triple_count": type_rejected_count,
            "snapshot_count": len(graph_root.snapshots),
        },
        "relation_validation": {
            "total_candidates": total_triples,
            "accepted": len(accepted_triples),
            "rejected_family": len(rejected_triples),
            "rejected_type": type_rejected_count,
            "rejected_type_examples": [
                {
                    "triple_id": triple.triple_id,
                    "head": triple.head,
                    "tail": triple.tail,
                    "family": triple.relation_family,
                }
                for triple in rejected_type_triples[:10]
            ],
        },
        "nodes": [node.model_dump(mode="json") for node in graph_root.nodes],
        "edges": [edge.model_dump(mode="json") for edge in graph_root.edges],
    }


def _build_relation_audit_payload(result: VariantRunResult, domain_id: str) -> dict[str, object]:
    graph_root = result.domain_graphs[domain_id]
    triples = graph_root.triples
    status_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    graph_layer_counts: dict[str, int] = {}
    workflow_kind_counts: dict[str, int] = {}
    reject_reason_counts: dict[str, int] = {}

    for triple in triples:
        status_counts[triple.status] = status_counts.get(triple.status, 0) + 1
        family_counts[triple.relation_family] = family_counts.get(triple.relation_family, 0) + 1
        graph_layer_counts[triple.graph_layer] = graph_layer_counts.get(triple.graph_layer, 0) + 1
        if triple.workflow_kind:
            workflow_kind_counts[triple.workflow_kind] = workflow_kind_counts.get(triple.workflow_kind, 0) + 1
        if triple.reject_reason:
            reject_reason_counts[triple.reject_reason] = reject_reason_counts.get(triple.reject_reason, 0) + 1

    items = [
        {
            "triple_id": triple.triple_id,
            "head": triple.head,
            "relation": triple.relation,
            "tail": triple.tail,
            "family": triple.relation_family,
            "graph_layer": triple.graph_layer,
            "workflow_kind": triple.workflow_kind,
            "status": triple.status,
            "reject_reason": triple.reject_reason,
            "confidence": triple.confidence,
            "evidence_ids": triple.evidence_ids,
            "attachment_refs": triple.attachment_refs,
        }
        for triple in triples
    ]

    return {
        "domain_id": domain_id,
        "summary": {
            "candidate_relation_count": len(triples),
            "accepted_count": status_counts.get("accepted", 0),
            "rejected_count": status_counts.get("rejected", 0),
            "rejected_type_count": status_counts.get("rejected_type", 0),
            "status_counts": status_counts,
            "family_counts": family_counts,
            "graph_layer_counts": graph_layer_counts,
            "workflow_kind_counts": workflow_kind_counts,
            "reject_reason_counts": reject_reason_counts,
        },
        "items": items,
    }


def _build_data_flow_trace_payload(result: VariantRunResult) -> dict[str, object]:
    domains: dict[str, dict[str, object]] = {}
    for domain_id, graph_root in result.domain_graphs.items():
        candidates = result.candidates_by_domain[domain_id]
        decisions = result.attachment_decisions[domain_id]
        admitted_candidate_labels = [
            candidate.label
            for candidate in candidates
            if decisions[candidate.candidate_id].admit_as_node
        ]
        rejected_by_reason: dict[str, int] = {}
        for candidate in candidates:
            decision = decisions[candidate.candidate_id]
            if decision.admit_as_node:
                continue
            reason = decision.reject_reason or "unspecified"
            rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
        domains[domain_id] = {
            "evidence_unit_count": sum(1 for unit in result.evidence_units if unit.domain_id == domain_id),
            "schema_candidate_count": len(candidates),
            "admitted_candidate_count": len(admitted_candidate_labels),
            "rejected_candidate_count": len(candidates) - len(admitted_candidate_labels),
            "rejected_candidate_reasons": rejected_by_reason,
            "adapter_concept_count": len(result.schemas[domain_id].adapter_concepts),
            "graph_node_count": len(graph_root.nodes),
            "graph_edge_count": len(graph_root.edges),
            "workflow_step_node_count": sum(1 for node in graph_root.nodes if node.node_layer == "workflow"),
            "semantic_node_count": sum(1 for node in graph_root.nodes if node.node_layer == "semantic"),
            "workflow_edge_count": sum(1 for edge in graph_root.edges if edge.edge_layer == "workflow"),
            "semantic_edge_count": sum(1 for edge in graph_root.edges if edge.edge_layer == "semantic"),
            "candidate_triple_count": len(graph_root.triples),
            "accepted_triple_count": sum(1 for triple in graph_root.triples if triple.status == "accepted"),
            "rejected_triple_count": sum(1 for triple in graph_root.triples if triple.status == "rejected"),
            "type_rejected_triple_count": sum(1 for triple in graph_root.triples if triple.status == "rejected_type"),
            "admitted_candidate_labels": admitted_candidate_labels,
            "accepted_edges": [
                {
                    "head": edge.head,
                    "relation": edge.label,
                    "tail": edge.tail,
                    "family": edge.family,
                    "edge_layer": edge.edge_layer,
                    "workflow_kind": edge.workflow_kind,
                }
                for edge in graph_root.edges
            ],
        }
    return {
        "variant_id": result.variant_id,
        "variant_description": result.variant_description,
        "backbone_concept_count": len(result.backbone_concepts),
        "domains": domains,
    }


def export_variant_run(
    run_dir: str | Path,
    result: VariantRunResult,
    write_detailed_working_artifacts: bool,
    write_jsonl_artifacts: bool,
    write_graphml: bool,
    write_property_graph_jsonl: bool,
    write_graph_db_csv: bool,
) -> None:
    root = ensure_dir(run_dir)
    run_root = root.parent
    graphml_variant_root = _graphml_variant_root(run_root, result.variant_id)
    write_json(
        root / "run_meta.json",
        {
            "variant_id": result.variant_id,
            "variant_description": result.variant_description,
            "exported_at": utc_now(),
            "backbone_size": len(result.backbone_concepts),
        },
    )
    write_json(root / "backbone_final.json", _build_backbone_final_payload(result))
    write_json(root / "construction_summary.json", result.construction_summary)

    if write_detailed_working_artifacts:
        write_json(root / "backbone_seed.json", _build_backbone_seed_payload(result))
        write_json(
            root / "backbone.json",
            {
                "seed_concepts": result.seed_backbone_concepts,
                "seed_descriptions": result.seed_backbone_descriptions,
                "concepts": result.backbone_concepts,
                "descriptions": result.backbone_descriptions,
                "curated_concepts": result.curated_backbone_concepts,
            },
        )
        write_json(root / "data_flow_trace.json", _build_data_flow_trace_payload(result))

    working_root = ensure_dir(root / "working")
    for domain_id, schema in result.schemas.items():
        domain_root = ensure_dir(working_root / domain_id)
        graph_root = result.domain_graphs[domain_id]
        evidence_units = [unit for unit in result.evidence_units if unit.domain_id == domain_id]
        candidates = result.candidates_by_domain[domain_id]
        retrievals = result.retrievals[domain_id]
        decisions = result.attachment_decisions[domain_id]
        candidate_payloads = _build_candidate_payloads(result, domain_id)
        accepted_adapter_candidates = [item for item in candidate_payloads if item["accepted_as_adapter"]]
        rejected_adapter_candidates = [item for item in candidate_payloads if item["rejected"]]
        rejected_adapter_candidates_by_reason = _group_rejected_candidates_by_reason(candidate_payloads)
        backbone_reuse_candidates = [item for item in candidate_payloads if item["accepted_as_backbone_reuse"]]

        if write_detailed_working_artifacts and write_jsonl_artifacts:
            write_jsonl(domain_root / "evidence_units.jsonl", evidence_units)
            write_jsonl(domain_root / "schema_candidates.jsonl", candidates)
            write_jsonl(domain_root / "graph_nodes.jsonl", graph_root.nodes)
            write_jsonl(domain_root / "graph_edges.jsonl", graph_root.edges)
            write_jsonl(domain_root / "candidate_triples.jsonl", graph_root.triples)
            write_jsonl(domain_root / "temporal_assertions.jsonl", graph_root.temporal_assertions)
            write_jsonl(domain_root / "snapshot_manifest.jsonl", graph_root.snapshots)

        write_json(
            domain_root / "attachment_audit.json",
            {
                "domain_id": domain_id,
                "summary": {
                    "candidate_count": len(candidates),
                    "accepted_adapter_candidate_count": len(accepted_adapter_candidates),
                    "accepted_backbone_reuse_count": len(backbone_reuse_candidates),
                    "rejected_candidate_count": len(rejected_adapter_candidates),
                    "rejected_by_reason": {
                        reason: len(items)
                        for reason, items in rejected_adapter_candidates_by_reason.items()
                    },
                },
                "items": candidate_payloads,
            },
        )
        write_json(domain_root / "final_graph.json", _build_final_graph_payload(result, domain_id))
        write_json(domain_root / "relation_audit.json", _build_relation_audit_payload(result, domain_id))
        if write_graphml:
            export_domain_graphml(
                domain_graph=graph_root,
                graphml_variant_root=graphml_variant_root,
                domain_id=domain_id,
            )

        if write_detailed_working_artifacts:
            write_json(domain_root / "adapter_schema.json", schema.model_dump(mode="json"))
            write_json(domain_root / "adapter_candidates.json", candidate_payloads)
            write_json(domain_root / "adapter_candidates.accepted.json", accepted_adapter_candidates)
            write_json(domain_root / "adapter_candidates.rejected.json", rejected_adapter_candidates)
            write_json(domain_root / "adapter_candidates.rejected_by_reason.json", rejected_adapter_candidates_by_reason)
            write_json(domain_root / "backbone_reuse_candidates.json", backbone_reuse_candidates)
            write_json(
                domain_root / "retrievals.json",
                {key: [item.model_dump(mode="json") for item in values] for key, values in retrievals.items()},
            )
            write_json(
                domain_root / "attachment_decisions.json",
                {key: value.model_dump(mode="json") for key, value in decisions.items()},
            )

            if len(graph_root.snapshots) != len(graph_root.snapshot_states):
                raise ValueError(
                    f"snapshot manifest/state length mismatch for domain {domain_id}: "
                    f"{len(graph_root.snapshots)} manifests vs {len(graph_root.snapshot_states)} states"
                )
            snapshots_root = ensure_dir(domain_root / "snapshots")
            for manifest, state in zip(graph_root.snapshots, graph_root.snapshot_states, strict=True):
                snapshot_root = ensure_dir(snapshots_root / manifest.snapshot_id)
                write_jsonl(snapshot_root / "nodes.jsonl", state.nodes)
                write_jsonl(snapshot_root / "edges.jsonl", state.edges)
                write_json(
                    snapshot_root / "consistency.json",
                    {
                        "snapshot_id": manifest.snapshot_id,
                        "node_count": manifest.node_count,
                        "edge_count": manifest.edge_count,
                        "accepted_evidence_ids": manifest.accepted_evidence_ids,
                    },
                )

            exports_root = ensure_dir(domain_root / "exports")
            if write_property_graph_jsonl:
                property_root = ensure_dir(exports_root / "property_graph")
                write_jsonl(property_root / "nodes.jsonl", graph_root.nodes)
                write_jsonl(property_root / "edges.jsonl", graph_root.edges)
            if write_graph_db_csv:
                graph_db_root = ensure_dir(exports_root / "graph_db")
                write_csv(
                    graph_db_root / "nodes.csv",
                    [node.model_dump(mode="json") for node in graph_root.nodes],
                    fieldnames=[
                        "node_id",
                        "label",
                        "display_label",
                        "domain_id",
                        "node_type",
                        "node_layer",
                        "parent_anchor",
                        "step_id",
                        "order_index",
                        "provenance_evidence_ids",
                    ],
                )
                write_csv(
                    graph_db_root / "edges.csv",
                    [edge.model_dump(mode="json") for edge in graph_root.edges],
                    fieldnames=[
                        "edge_id",
                        "domain_id",
                        "label",
                        "family",
                        "edge_layer",
                        "workflow_kind",
                        "head",
                        "tail",
                        "provenance_evidence_ids",
                    ],
                )


def export_benchmark_summary(run_root: str | Path, result: PipelineBenchmarkResult) -> None:
    root = ensure_dir(run_root)
    write_json(root / "benchmark_summary.json", result.summary)
    write_json(
        root / "benchmark_meta.json",
        {
            "project_name": result.project_name,
            "benchmark_name": result.benchmark_name,
            "config_path": result.config_path,
            "generated_dataset_path": result.generated_dataset_path,
            "variants": list(result.variant_results),
        },
    )


def write_latest_summary(artifact_root: str | Path, summary: dict) -> None:
    write_json(Path(artifact_root) / "latest_summary.json", summary)


def load_snapshot_state(run_dir: str | Path, domain_id: str, snapshot_id: str) -> dict:
    snapshot_root = Path(run_dir) / "working" / domain_id / "snapshots" / snapshot_id
    required_paths = [
        snapshot_root / "nodes.jsonl",
        snapshot_root / "edges.jsonl",
        snapshot_root / "consistency.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "snapshot artifacts are incomplete or not exported: " + ", ".join(missing)
        )
    return {
        "snapshot_id": snapshot_id,
        "nodes": read_jsonl(snapshot_root / "nodes.jsonl"),
        "edges": read_jsonl(snapshot_root / "edges.jsonl"),
        "consistency": read_json(snapshot_root / "consistency.json"),
    }


def rollback_snapshot(run_dir: str | Path, domain_id: str, snapshot_id: str) -> dict:
    return load_snapshot_state(run_dir, domain_id, snapshot_id)
