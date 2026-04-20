#!/usr/bin/env python3
"""Aggregate evaluation payloads across files and variants."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .core import compute_metrics, list_gold_files, read_json


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
            "concept_f1": aggregate["concept_metrics"]["f1"],
            "concept_label_f1": aggregate["concept_label_metrics"]["f1"],
            "anchor_accuracy": aggregate["anchor_metrics"]["accuracy"],
            "anchor_macro_f1": aggregate["anchor_metrics"]["macro_f1"],
            "relation_f1": aggregate["relation_metrics"]["f1"],
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
        "concept_f1",
        "concept_label_f1",
        "anchor_accuracy",
        "anchor_macro_f1",
        "relation_f1",
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
