#!/usr/bin/env python3
"""Aggregate evaluation payloads across files and variants."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from experiments.metrics.core import compute_metrics, list_gold_files, read_json


def _aggregate_error_summary(per_file_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    anchor_confusions: dict[tuple[str, str, str], int] = {}
    relation_buckets = {
        "structural_fp": 0,
        "lifecycle_fp": 0,
        "propagation_target_mismatch": 0,
        "communication_target_mismatch": 0,
        "propagation_missing": 0,
        "communication_missing": 0,
    }

    for payload in per_file_metrics.values():
        error_examples = payload.get("error_examples", {})
        for item in error_examples.get("anchor_confusions", []):
            key = (
                str(item.get("label", "")).strip(),
                str(item.get("predicted_anchor", "")).strip(),
                str(item.get("gold_anchor", "")).strip(),
            )
            if all(key):
                anchor_confusions[key] = anchor_confusions.get(key, 0) + 1

        missing_relations = error_examples.get("missing_relations", [])
        extra_relations = error_examples.get("extra_relations", [])
        for item in extra_relations:
            family = str(item.get("family", "")).strip()
            if family == "structural":
                relation_buckets["structural_fp"] += 1
            elif family == "lifecycle":
                relation_buckets["lifecycle_fp"] += 1

        for item in missing_relations:
            family = str(item.get("family", "")).strip()
            head = str(item.get("head", "")).strip()
            relation = str(item.get("relation", "")).strip()
            tail = str(item.get("tail", "")).strip()
            target_mismatch = any(
                str(extra.get("family", "")).strip() == family
                and str(extra.get("head", "")).strip() == head
                and str(extra.get("relation", "")).strip() == relation
                and str(extra.get("tail", "")).strip() != tail
                for extra in extra_relations
            )
            if family == "propagation":
                relation_buckets["propagation_target_mismatch" if target_mismatch else "propagation_missing"] += 1
            elif family == "communication":
                relation_buckets["communication_target_mismatch" if target_mismatch else "communication_missing"] += 1

    top_anchor_confusions = [
        {
            "label": label,
            "predicted_anchor": predicted_anchor,
            "gold_anchor": gold_anchor,
            "count": count,
        }
        for (label, predicted_anchor, gold_anchor), count in sorted(
            anchor_confusions.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
        )[:15]
    ]
    return {
        "anchor_confusion_table": top_anchor_confusions,
        "relation_error_buckets": relation_buckets,
    }


def aggregate_metric_payloads(per_file_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not per_file_metrics:
        raise ValueError("aggregate_metric_payloads requires at least one metrics payload")

    def nested_value(payload: dict[str, Any], dotted_key: str) -> float:
        current: Any = payload
        for part in dotted_key.split("."):
            if not isinstance(current, dict):
                return 0.0
            current = current.get(part)
        if current is None:
            return 0.0
        return float(current)

    def avg(section: str, key: str) -> float:
        values = [nested_value(item.get(section, {}), key) for item in per_file_metrics.values()]
        return round(sum(values) / len(values), 4)

    def avg_when_available(section: str, key: str, availability_key: str = "available") -> float:
        values = [
            nested_value(item.get(section, {}), key)
            for item in per_file_metrics.values()
            if bool(item.get(section, {}).get(availability_key, False))
        ]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def total(section: str, key: str) -> int:
        values = [int(item.get(section, {}).get(key, 0)) for item in per_file_metrics.values()]
        return sum(values)

    return {
        "evaluated_gold_files": sorted(per_file_metrics),
        "documents": sorted(
            {
                doc_id
                for item in per_file_metrics.values()
                for doc_id in item.get("documents", [])
            }
        ),
        "node_coverage_metrics": {
            "precision": avg("node_coverage_metrics", "precision"),
            "recall": avg("node_coverage_metrics", "recall"),
            "f1": avg("node_coverage_metrics", "f1"),
        },
        "anchored_node_canonical_metrics": {
            "precision": avg("anchored_node_canonical_metrics", "precision"),
            "recall": avg("anchored_node_canonical_metrics", "recall"),
            "f1": avg("anchored_node_canonical_metrics", "f1"),
        },
        "concept_metrics": {
            "precision": avg("concept_metrics", "precision"),
            "recall": avg("concept_metrics", "recall"),
            "f1": avg("concept_metrics", "f1"),
        },
        "concept_label_metrics": {
            "precision": avg("concept_label_metrics", "precision"),
            "recall": avg("concept_label_metrics", "recall"),
            "f1": avg("concept_label_metrics", "f1"),
        },
        "anchor_metrics": {
            "accuracy": avg("anchor_metrics", "accuracy"),
            "macro_f1": avg("anchor_metrics", "macro_f1"),
            "support": total("anchor_metrics", "support"),
        },
        "relation_metrics": {
            "precision": avg("relation_metrics", "precision"),
            "recall": avg("relation_metrics", "recall"),
            "f1": avg("relation_metrics", "f1"),
        },
        "workflow_step_metrics": {
            "precision": avg("workflow_step_metrics", "precision"),
            "recall": avg("workflow_step_metrics", "recall"),
            "f1": avg("workflow_step_metrics", "f1"),
        },
        "workflow_sequence_metrics": {
            "precision": avg("workflow_sequence_metrics", "precision"),
            "recall": avg("workflow_sequence_metrics", "recall"),
            "f1": avg("workflow_sequence_metrics", "f1"),
        },
        "workflow_grounding_metrics": {
            "available_doc_count": sum(
                1
                for item in per_file_metrics.values()
                if bool(item.get("workflow_grounding_metrics", {}).get("available", False))
            ),
            "precision": avg_when_available("workflow_grounding_metrics", "precision"),
            "recall": avg_when_available("workflow_grounding_metrics", "recall"),
            "f1": avg_when_available("workflow_grounding_metrics", "f1"),
        },
        "workflow_grounding_stats": {
            "action_object_edge_count": total("workflow_grounding_stats", "action_object_edge_count"),
            "grounded_step_count": total("workflow_grounding_stats", "grounded_step_count"),
            "ungrounded_step_count": total("workflow_grounding_stats", "ungrounded_step_count"),
            "avg_action_object_edges_per_grounded_step": avg(
                "workflow_grounding_stats",
                "avg_action_object_edges_per_grounded_step",
            ),
        },
        "isolated_node_delta": {
            "full_graph_isolated_count": total("isolated_node_delta", "full_graph_isolated_count"),
            "semantic_only_isolated_count": total("isolated_node_delta", "semantic_only_isolated_count"),
            "workflow_reduction_count": total("isolated_node_delta", "workflow_reduction_count"),
        },
        "diagnostic_metrics": {
            "concept_relaxed_label_metrics": {
                "precision": avg("diagnostic_metrics", "concept_relaxed_label_metrics.precision"),
                "recall": avg("diagnostic_metrics", "concept_relaxed_label_metrics.recall"),
                "f1": avg("diagnostic_metrics", "concept_relaxed_label_metrics.f1"),
            },
            "relation_relaxed_metrics": {
                "precision": avg("diagnostic_metrics", "relation_relaxed_metrics.precision"),
                "recall": avg("diagnostic_metrics", "relation_relaxed_metrics.recall"),
                "f1": avg("diagnostic_metrics", "relation_relaxed_metrics.f1"),
            },
            "relation_family_agnostic_metrics": {
                "precision": avg("diagnostic_metrics", "relation_family_agnostic_metrics.precision"),
                "recall": avg("diagnostic_metrics", "relation_family_agnostic_metrics.recall"),
                "f1": avg("diagnostic_metrics", "relation_family_agnostic_metrics.f1"),
            },
        },
        "predicted_counts": {
            "concepts": total("predicted_counts", "concepts"),
            "relations": total("predicted_counts", "relations"),
        },
        "gold_counts": {
            "concepts": total("gold_counts", "concepts"),
            "relations": total("gold_counts", "relations"),
        },
        "per_gold_file": per_file_metrics,
        "error_summary": _aggregate_error_summary(per_file_metrics),
    }


def _metric_lookup(payload: dict[str, Any], dotted_key: str) -> float:
    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return 0.0
        current = current.get(part)
    if current is None:
        return 0.0
    return float(current)


def evaluate_variant_run(
    run_root: str | Path,
    variant_id: str,
    ground_truth_dir: str | Path | None = None,
    domain_ids: list[str] | None = None,
    gold_file_names: list[str] | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root)
    variant_root = run_root / variant_id / "working"
    if not variant_root.exists():
        raise FileNotFoundError(f"variant working directory not found: {variant_root}")

    per_gold: dict[str, Any] = {}
    selected_gold_files = set(gold_file_names or [])
    selected_domains = set(domain_ids or [])
    gold_files = list_gold_files(ground_truth_dir)
    for gold_path in gold_files:
        if selected_gold_files and gold_path.name not in selected_gold_files:
            continue
        gold_payload = read_json(gold_path)
        domain_id = str(gold_payload.get("domain_id", "")).strip()
        if selected_domains and domain_id not in selected_domains:
            continue
        graph_path = variant_root / domain_id / "final_graph.json"
        if not graph_path.exists():
            continue
        per_gold[gold_path.name] = compute_metrics(gold_path, graph_path)

    if not per_gold:
        raise FileNotFoundError(
            f"no matching gold evaluations produced for variant {variant_id} under {variant_root}"
        )

    aggregate = aggregate_metric_payloads(per_gold)

    return {
        "variant_id": variant_id,
        "run_root": str(run_root.resolve()),
        **aggregate,
        "macro_average": {
            "node_coverage_relaxed_f1": aggregate["node_coverage_metrics"]["f1"],
            "anchored_node_canonical_f1": aggregate["anchored_node_canonical_metrics"]["f1"],
            "anchor_accuracy": aggregate["anchor_metrics"]["accuracy"],
            "anchor_macro_f1": aggregate["anchor_metrics"]["macro_f1"],
            "relation_f1": aggregate["relation_metrics"]["f1"],
            "workflow_step_f1": aggregate["workflow_step_metrics"]["f1"],
            "workflow_sequence_f1": aggregate["workflow_sequence_metrics"]["f1"],
            "workflow_grounding_f1": aggregate["workflow_grounding_metrics"]["f1"],
            "concept_f1": aggregate["concept_metrics"]["f1"],
            "concept_label_f1": aggregate["concept_label_metrics"]["f1"],
            "concept_relaxed_label_f1": _metric_lookup(
                aggregate,
                "diagnostic_metrics.concept_relaxed_label_metrics.f1",
            ),
            "relation_relaxed_f1": _metric_lookup(
                aggregate,
                "diagnostic_metrics.relation_relaxed_metrics.f1",
            ),
            "relation_family_agnostic_f1": _metric_lookup(
                aggregate,
                "diagnostic_metrics.relation_family_agnostic_metrics.f1",
            ),
        },
    }


def write_ablation_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "variant_id",
        "component",
        "mode",
        "preprocessing_source",
        "attachment_source",
        "uses_llm_preprocessing",
        "uses_llm_attachment",
        "paper_table",
        "alias_for",
        "node_coverage_relaxed_f1",
        "anchored_node_canonical_f1",
        "anchor_accuracy",
        "anchor_macro_f1",
        "relation_f1",
        "workflow_step_f1",
        "workflow_sequence_f1",
        "workflow_grounding_f1",
        "concept_f1",
        "concept_label_f1",
        "concept_relaxed_label_f1",
        "relation_relaxed_f1",
        "relation_family_agnostic_f1",
        "evaluated_gold_files",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
