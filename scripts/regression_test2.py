#!/usr/bin/env python3
"""Regression Test 2: Three-domain, single-document each (battery+cnc+nev)."""

import json
import logging
import sys

logging.basicConfig(level=logging.WARNING)

from config import load_pipeline_config
from pipeline.evidence import (
    load_records_by_domain,
    normalize_records_by_domain,
    build_evidence_units,
    aggregate_schema_candidates,
)
from pipeline.backbone import build_backbone
from rules.filtering import filter_attachment_decision, preferred_parent_anchor
from pipeline.graph import assemble_domain_graphs, build_domain_schemas
from models import VariantRunResult, AttachmentDecision
from collections import Counter
from types import SimpleNamespace


def main():
    print("=" * 60)
    print("REGRESSION TEST 2: Battery+CNC+NEV (1 doc each)")
    print("(Rule-based attachment, no LLM/embedding)")
    print("=" * 60)

    config = load_pipeline_config("config/persistent/pipeline.deepseek.yaml")
    config = config.config_for_domains(["battery", "cnc", "nev"])

    # Override data paths to single-doc files
    config.domains[0].data_path = "data/evidence_records/battery_single_doc.json"
    config.domains[1].data_path = "data/evidence_records/cnc_single_doc.json"
    config.domains[2].data_path = "data/evidence_records/nev_single_doc.json"

    # Load & normalize
    records_by_domain = normalize_records_by_domain(load_records_by_domain(config))
    evidence_units = build_evidence_units(config, records_by_domain)
    candidates_by_domain = aggregate_schema_candidates(
        records_by_domain, assume_normalized=True
    )

    for domain_id in ["battery", "cnc", "nev"]:
        print(f"\n--- {domain_id} ---")
        print(f"  Records: {len(records_by_domain[domain_id])}")
        print(f"  Schema candidates: {len(candidates_by_domain[domain_id])}")

    # v2 check: shared_hypernym in routing_features
    for domain_id in ["battery", "cnc", "nev"]:
        hypernym_cands = [
            c
            for c in candidates_by_domain[domain_id]
            if c.routing_features.get("shared_hypernym")
        ]
        print(f"  Candidates with shared_hypernym ({domain_id}): {len(hypernym_cands)}")

    # Build backbone
    backbone_concepts, backbone_descriptions, curated_concepts = build_backbone(
        config=config
    )
    print(f"\nBackbone concepts ({len(backbone_concepts)}): {backbone_concepts}")
    backbone_set = set(backbone_concepts)

    # Rule-based attachment (deterministic, no LLM needed)
    decisions_by_domain = {}
    for domain in config.domains:
        decisions = {}
        for candidate in candidates_by_domain[domain.domain_id]:
            if candidate.label in backbone_set:
                route = "reuse_backbone"
                parent = None
            else:
                route = "vertical_specialize"
                parent = preferred_parent_anchor(candidate)
                if parent is None:
                    route = "reject"

            decision = AttachmentDecision(
                candidate_id=candidate.candidate_id,
                label=candidate.label,
                route=route,
                parent_anchor=parent,
                accept=(route != "reject"),
                admit_as_node=(route != "reject"),
                reject_reason=None if route != "reject" else "cannot_anchor_backbone",
                confidence=1.0 if route == "reuse_backbone" else 0.5,
                justification=f"rule-based: {route}",
                evidence_ids=list(candidate.evidence_ids),
            )
            decisions[candidate.candidate_id] = decision
        decisions_by_domain[domain.domain_id] = decisions

    # Attachment summary per domain
    for domain_id in ["battery", "cnc", "nev"]:
        accepted = sum(
            1 for d in decisions_by_domain[domain_id].values() if d.admit_as_node
        )
        total = len(decisions_by_domain[domain_id])
        route_dist = Counter(d.route for d in decisions_by_domain[domain_id].values())
        rejected_reasons = Counter(
            d.reject_reason
            for d in decisions_by_domain[domain_id].values()
            if not d.admit_as_node
        )
        print(f"\n  {domain_id} attachment: {accepted}/{total} accepted")
        print(f"    Routes: {dict(route_dist)}")
        if rejected_reasons:
            print(f"    Rejected: {dict(rejected_reasons)}")

    # Build schema & graph
    variant = SimpleNamespace(
        write_temporal_metadata=False,
        enable_snapshots=False,
        detect_lifecycle_events=False,
        variant_id="rule_based_test2",
    )
    schemas = build_domain_schemas(
        config, candidates_by_domain, decisions_by_domain, backbone_concepts
    )
    graphs = assemble_domain_graphs(
        config, variant, records_by_domain, schemas, decisions_by_domain, backbone_concepts
    )

    # Per-domain graph stats
    all_stats = {}
    for domain_id in ["battery", "cnc", "nev"]:
        graph = graphs[domain_id]
        print(f"\n=== {domain_id} Graph ===")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")
        accepted_t = sum(1 for t in graph.triples if t.status == "accepted")
        rejected_t = sum(1 for t in graph.triples if t.status == "rejected")
        rejected_type_t = sum(1 for t in graph.triples if t.status == "rejected_type")
        print(f"  Accepted triples: {accepted_t}")
        print(f"  Rejected triples: {rejected_t}")
        print(f"  Rejected_type triples: {rejected_type_t}")

        nt = Counter(n.node_type for n in graph.nodes)
        nl = Counter(n.node_layer for n in graph.nodes)
        el = Counter(e.edge_layer for e in graph.edges)
        ef = Counter(e.family for e in graph.edges)
        wk = Counter(e.workflow_kind for e in graph.edges if e.workflow_kind)
        print(f"  Node types: {dict(nt)}")
        print(f"  Node layers: {dict(nl)}")
        print(f"  Edge layers: {dict(el)}")
        print(f"  Edge families: {dict(ef)}")
        print(f"  Workflow kinds: {dict(wk)}")

        # v2 specific
        workflow_nodes = [n for n in graph.nodes if n.node_layer == "workflow"]
        semantic_nodes = [n for n in graph.nodes if n.node_layer == "semantic"]
        phase_counts = Counter(n.step_phase for n in workflow_nodes if n.step_phase)
        hypernym_nodes = [n for n in semantic_nodes if n.shared_hypernym]
        hypernym_dist = Counter(n.shared_hypernym for n in hypernym_nodes)

        print(f"  Workflow nodes: {len(workflow_nodes)}")
        print(f"  Step phases: {dict(phase_counts)}")
        print(f"  Semantic nodes: {len(semantic_nodes)}")
        print(f"  Nodes with shared_hypernym: {len(hypernym_nodes)}")
        if semantic_nodes:
            print(f"  Hypernym coverage: {len(hypernym_nodes)/len(semantic_nodes):.2%}")
        print(f"  Hypernym distribution: {dict(hypernym_dist)}")

        # Workflow step details
        for n in sorted(workflow_nodes, key=lambda n: n.order_index or 0):
            phase_str = f" phase={n.step_phase}" if n.step_phase else ""
            print(f"    Step: {n.label}: \"{n.display_label}\"{phase_str}")

        all_stats[domain_id] = {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "accepted_triples": accepted_t,
            "rejected_triples": rejected_t,
            "rejected_type_triples": rejected_type_t,
            "node_types": dict(nt),
            "node_layers": dict(nl),
            "edge_layers": dict(el),
            "edge_families": dict(ef),
            "workflow_kinds": dict(wk),
            "workflow_nodes": len(workflow_nodes),
            "step_phases": dict(phase_counts),
            "semantic_nodes": len(semantic_nodes),
            "hypernym_nodes": len(hypernym_nodes),
            "hypernym_coverage": round(len(hypernym_nodes) / len(semantic_nodes), 4) if semantic_nodes else 0,
            "hypernym_distribution": dict(hypernym_dist),
        }

    # Cross-domain hypernym consistency check
    print(f"\n=== Cross-Domain Hypernym Consistency ===")
    all_hypernym_labels = {}
    for domain_id in ["battery", "cnc", "nev"]:
        graph = graphs[domain_id]
        semantic_nodes = {n.label: n for n in graph.nodes if n.node_layer == "semantic"}
        for label, node in semantic_nodes.items():
            if node.shared_hypernym:
                all_hypernym_labels.setdefault(label, {})[domain_id] = node.shared_hypernym

    consistent = 0
    inconsistent = 0
    for label, domain_map in sorted(all_hypernym_labels.items()):
        values = set(domain_map.values())
        if len(values) == 1:
            consistent += 1
        else:
            inconsistent += 1
            print(f"  INCONSISTENT: '{label}' -> {domain_map}")

    print(f"  Total cross-domain labels with hypernym: {len(all_hypernym_labels)}")
    print(f"  Consistent: {consistent}")
    print(f"  Inconsistent: {inconsistent}")

    # Save result
    result = VariantRunResult(
        variant_id=variant.variant_id,
        variant_description="rule-based regression test2: 3-domain single-doc",
        seed_backbone_concepts=config.backbone.seed_concepts,
        seed_backbone_descriptions=config.backbone.seed_descriptions,
        backbone_concepts=backbone_concepts,
        backbone_descriptions=backbone_descriptions,
        curated_backbone_concepts=curated_concepts,
        evidence_units=evidence_units,
        candidates_by_domain=candidates_by_domain,
        retrievals={d: {} for d in records_by_domain},
        attachment_decisions=decisions_by_domain,
        schemas=schemas,
        domain_graphs=graphs,
        construction_summary={"test": "regression_test2_three_domain_single"},
    )
    from pipeline.artifacts import export_variant_run

    export_variant_run(
        "results/regression_v2/test2", result, False, False, True, False, False
    )
    print(f"\nResults exported to results/regression_v2/test2/")

    # Save structured report
    report = {
        "test": "regression_test2",
        "description": "Three-domain single-document (battery+cnc+nev, 1 each)",
        "attachment_method": "rule-based",
        "backbone_concepts": backbone_concepts,
        "domain_stats": all_stats,
        "cross_domain_hypernym": {
            "total_labels": len(all_hypernym_labels),
            "consistent": consistent,
            "inconsistent": inconsistent,
            "details": {k: v for k, v in sorted(all_hypernym_labels.items())},
        },
    }
    with open("results/regression_v2/test2_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved to results/regression_v2/test2_report.json")


if __name__ == "__main__":
    main()
