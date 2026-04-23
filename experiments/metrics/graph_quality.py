#!/usr/bin/env python3
"""Readable-graph quality diagnostics for GraphML-oriented evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from experiments.metrics.core import read_json


def _edge_display_admitted(edge: dict[str, Any]) -> bool:
    value = edge.get("display_admitted")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _edge_raw_label(edge: dict[str, Any]) -> str:
    return str(edge.get("raw_label") or edge.get("label") or "").strip()


def _edge_display_label(edge: dict[str, Any]) -> str:
    return str(edge.get("display_label") or edge.get("label") or "").strip()


def analyze_graph_payload(graph_payload: dict[str, Any]) -> dict[str, Any]:
    nodes = list(graph_payload.get("nodes", []))
    edges = list(graph_payload.get("edges", []))
    readable_edges = [edge for edge in edges if _edge_display_admitted(edge)]
    readable_labels = {str(edge.get("head", "")).strip() for edge in readable_edges} | {
        str(edge.get("tail", "")).strip() for edge in readable_edges
    }
    readable_nodes = [
        node for node in nodes if str(node.get("label", "")).strip() in readable_labels
    ]

    all_incident = {str(edge.get("head", "")).strip() for edge in edges} | {
        str(edge.get("tail", "")).strip() for edge in edges
    }
    readable_incident = {str(edge.get("head", "")).strip() for edge in readable_edges} | {
        str(edge.get("tail", "")).strip() for edge in readable_edges
    }

    raw_isolated = [
        str(node.get("label", "")).strip()
        for node in nodes
        if str(node.get("label", "")).strip() and str(node.get("label", "")).strip() not in all_incident
    ]
    readable_isolated = [
        str(node.get("label", "")).strip()
        for node in nodes
        if str(node.get("label", "")).strip() and str(node.get("label", "")).strip() not in readable_incident
    ]

    workflow_display_verbs: dict[str, int] = {}
    raw_workflow_verbs: dict[str, int] = {}
    semantic_family_counts: dict[str, int] = {}
    readable_semantic_family_counts: dict[str, int] = {}
    hidden_display_reasons: dict[str, int] = {}

    action_object_edges = [
        edge for edge in edges
        if str(edge.get("workflow_kind") or "").strip() == "action_object"
    ]
    hidden_action_object_edges = [
        edge for edge in action_object_edges if not _edge_display_admitted(edge)
    ]

    for edge in action_object_edges:
        raw_label = _edge_raw_label(edge)
        if raw_label:
            raw_workflow_verbs[raw_label] = raw_workflow_verbs.get(raw_label, 0) + 1
        if _edge_display_admitted(edge):
            display_label = _edge_display_label(edge)
            if display_label:
                workflow_display_verbs[display_label] = workflow_display_verbs.get(display_label, 0) + 1
        else:
            reason = str(edge.get("display_reject_reason") or "not_displayed").strip()
            hidden_display_reasons[reason] = hidden_display_reasons.get(reason, 0) + 1

    for edge in edges:
        if str(edge.get("edge_layer") or "").strip() != "semantic":
            continue
        family = str(edge.get("family") or "").strip()
        if family:
            semantic_family_counts[family] = semantic_family_counts.get(family, 0) + 1
        if _edge_display_admitted(edge) and family:
            readable_semantic_family_counts[family] = readable_semantic_family_counts.get(family, 0) + 1

    readable_edge_summary = {
        "workflow_sequence": sum(
            1
            for edge in readable_edges
            if str(edge.get("workflow_kind") or "").strip() == "sequence"
        ),
        "workflow_action_object": sum(
            1
            for edge in readable_edges
            if str(edge.get("workflow_kind") or "").strip() == "action_object"
        ),
        "semantic": sum(
            1
            for edge in readable_edges
            if str(edge.get("edge_layer") or "").strip() == "semantic"
        ),
    }

    structural_self_loop_count = sum(
        1
        for edge in edges
        if str(edge.get("family") or "").strip() == "structural"
        and str(edge.get("head") or "").strip() == str(edge.get("tail") or "").strip()
    )

    raw_node_count = len(nodes)
    readable_node_count = len(readable_nodes)
    readable_isolated_ratio = round(len(readable_isolated) / raw_node_count, 4) if raw_node_count else 0.0
    raw_isolated_ratio = round(len(raw_isolated) / raw_node_count, 4) if raw_node_count else 0.0
    low_value_action_object_edge_rate = round(
        len(hidden_action_object_edges) / len(action_object_edges),
        4,
    ) if action_object_edges else 0.0

    return {
        "raw_node_count": raw_node_count,
        "raw_edge_count": len(edges),
        "readable_node_count": readable_node_count,
        "readable_edge_count": len(readable_edges),
        "raw_isolated_node_count": len(raw_isolated),
        "raw_isolated_node_ratio": raw_isolated_ratio,
        "readable_isolated_node_count": len(readable_isolated),
        "readable_isolated_node_ratio": readable_isolated_ratio,
        "structural_self_loop_count": structural_self_loop_count,
        "workflow_display_verb_counts": workflow_display_verbs,
        "workflow_display_verb_vocab": sorted(workflow_display_verbs),
        "raw_workflow_verb_counts": raw_workflow_verbs,
        "low_value_action_object_edge_rate": low_value_action_object_edge_rate,
        "hidden_display_reason_counts": hidden_display_reasons,
        "semantic_family_counts": semantic_family_counts,
        "readable_semantic_family_counts": readable_semantic_family_counts,
        "readable_edge_summary": readable_edge_summary,
    }


def analyze_variant_graph_quality(run_root: str | Path, variant_id: str) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    working_root = run_root / variant_id / "working"
    if not working_root.exists():
        raise FileNotFoundError(f"variant working directory not found: {working_root}")

    domains: dict[str, Any] = {}
    global_display_verbs: dict[str, int] = {}
    global_semantic_families: dict[str, int] = {}
    structural_self_loop_total = 0

    for domain_root in sorted(item for item in working_root.iterdir() if item.is_dir()):
        graph_path = domain_root / "final_graph.json"
        if not graph_path.exists():
            continue
        payload = analyze_graph_payload(read_json(graph_path))
        domains[domain_root.name] = payload
        structural_self_loop_total += int(payload["structural_self_loop_count"])
        for label, count in payload["workflow_display_verb_counts"].items():
            global_display_verbs[label] = global_display_verbs.get(label, 0) + int(count)
        for family, count in payload["readable_semantic_family_counts"].items():
            global_semantic_families[family] = global_semantic_families.get(family, 0) + int(count)

    if not domains:
        raise FileNotFoundError(f"no final_graph.json files found under {working_root}")

    domain_payloads = list(domains.values())

    def _avg(key: str) -> float:
        return round(sum(float(item.get(key, 0.0)) for item in domain_payloads) / len(domain_payloads), 4)

    return {
        "variant_id": variant_id,
        "run_root": str(run_root),
        "domains": domains,
        "macro_average": {
            "readable_isolated_node_ratio": _avg("readable_isolated_node_ratio"),
            "low_value_action_object_edge_rate": _avg("low_value_action_object_edge_rate"),
        },
        "global_workflow_display_verb_vocab": sorted(global_display_verbs),
        "global_workflow_display_verb_counts": global_display_verbs,
        "global_readable_semantic_family_counts": global_semantic_families,
        "structural_self_loop_total": structural_self_loop_total,
    }


def diff_graph_quality(baseline: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    domains: dict[str, Any] = {}
    shared_domains = sorted(set(baseline.get("domains", {})) & set(post.get("domains", {})))
    for domain_id in shared_domains:
        before = baseline["domains"][domain_id]
        after = post["domains"][domain_id]
        domains[domain_id] = {
            "readable_node_count_delta": int(after.get("readable_node_count", 0)) - int(before.get("readable_node_count", 0)),
            "readable_edge_count_delta": int(after.get("readable_edge_count", 0)) - int(before.get("readable_edge_count", 0)),
            "readable_isolated_node_ratio_delta": round(
                float(after.get("readable_isolated_node_ratio", 0.0)) - float(before.get("readable_isolated_node_ratio", 0.0)),
                4,
            ),
            "low_value_action_object_edge_rate_delta": round(
                float(after.get("low_value_action_object_edge_rate", 0.0)) - float(before.get("low_value_action_object_edge_rate", 0.0)),
                4,
            ),
            "structural_self_loop_delta": int(after.get("structural_self_loop_count", 0)) - int(before.get("structural_self_loop_count", 0)),
            "workflow_display_verb_vocab_before": before.get("workflow_display_verb_vocab", []),
            "workflow_display_verb_vocab_after": after.get("workflow_display_verb_vocab", []),
        }

    return {
        "variant_id": post.get("variant_id") or baseline.get("variant_id"),
        "domains": domains,
        "macro_average": {
            "readable_isolated_node_ratio_delta": round(
                float(post.get("macro_average", {}).get("readable_isolated_node_ratio", 0.0))
                - float(baseline.get("macro_average", {}).get("readable_isolated_node_ratio", 0.0)),
                4,
            ),
            "low_value_action_object_edge_rate_delta": round(
                float(post.get("macro_average", {}).get("low_value_action_object_edge_rate", 0.0))
                - float(baseline.get("macro_average", {}).get("low_value_action_object_edge_rate", 0.0)),
                4,
            ),
        },
        "structural_self_loop_total_delta": int(post.get("structural_self_loop_total", 0)) - int(baseline.get("structural_self_loop_total", 0)),
        "global_workflow_display_verb_vocab_before": baseline.get("global_workflow_display_verb_vocab", []),
        "global_workflow_display_verb_vocab_after": post.get("global_workflow_display_verb_vocab", []),
        "global_readable_semantic_family_counts_before": baseline.get("global_readable_semantic_family_counts", {}),
        "global_readable_semantic_family_counts_after": post.get("global_readable_semantic_family_counts", {}),
    }

