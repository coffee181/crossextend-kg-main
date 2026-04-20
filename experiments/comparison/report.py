#!/usr/bin/env python3
"""Comparison helpers for ablation and variant studies."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


_COMPARISON_METRICS: tuple[tuple[str, str], ...] = (
    ("macro_average", "concept_f1"),
    ("macro_average", "concept_label_f1"),
    ("macro_average", "anchor_accuracy"),
    ("macro_average", "anchor_macro_f1"),
    ("macro_average", "relation_f1"),
    ("macro_average", "concept_relaxed_label_f1"),
    ("macro_average", "relation_relaxed_f1"),
    ("macro_average", "relation_family_agnostic_f1"),
)


def _metric_value(payload: dict[str, Any], section: str, key: str) -> float:
    return float(payload.get(section, {}).get(key, 0.0))


def build_variant_summary_rows(evaluations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, evaluation in evaluations.items():
        macro = evaluation.get("macro_average", {})
        rows.append(
            {
                "variant_id": variant_id,
                "concept_f1": float(macro.get("concept_f1", 0.0)),
                "concept_label_f1": float(macro.get("concept_label_f1", 0.0)),
                "anchor_accuracy": float(macro.get("anchor_accuracy", 0.0)),
                "anchor_macro_f1": float(macro.get("anchor_macro_f1", 0.0)),
                "relation_f1": float(macro.get("relation_f1", 0.0)),
                "concept_relaxed_label_f1": float(macro.get("concept_relaxed_label_f1", 0.0)),
                "relation_relaxed_f1": float(macro.get("relation_relaxed_f1", 0.0)),
                "relation_family_agnostic_f1": float(macro.get("relation_family_agnostic_f1", 0.0)),
                "evaluated_gold_files": len(evaluation.get("evaluated_gold_files", [])),
            }
        )
    rows.sort(key=lambda item: (-item["relation_f1"], -item["concept_f1"], item["variant_id"]))
    return rows


def compare_variant_evaluations(
    evaluations: dict[str, dict[str, Any]],
    *,
    baseline_variant: str = "full_llm",
) -> dict[str, Any]:
    if not evaluations:
        raise ValueError("compare_variant_evaluations requires at least one evaluation payload")
    if baseline_variant not in evaluations:
        raise ValueError(f"baseline variant not present in evaluations: {baseline_variant}")

    rows = build_variant_summary_rows(evaluations)
    baseline = evaluations[baseline_variant]

    deltas_vs_baseline: list[dict[str, Any]] = []
    for row in rows:
        variant_payload = evaluations[row["variant_id"]]
        delta_row = {"variant_id": row["variant_id"]}
        for section, key in _COMPARISON_METRICS:
            metric_name = key
            delta_row[f"{metric_name}_delta"] = round(
                _metric_value(variant_payload, section, key) - _metric_value(baseline, section, key),
                4,
            )
        deltas_vs_baseline.append(delta_row)

    best_variant_by_metric: dict[str, str] = {}
    for section, key in _COMPARISON_METRICS:
        metric_name = key
        best_variant_by_metric[metric_name] = max(
            evaluations,
            key=lambda variant_id: _metric_value(evaluations[variant_id], section, key),
        )

    return {
        "baseline_variant": baseline_variant,
        "variant_rows": rows,
        "deltas_vs_baseline": deltas_vs_baseline,
        "best_variant_by_metric": best_variant_by_metric,
    }


def write_comparison_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
