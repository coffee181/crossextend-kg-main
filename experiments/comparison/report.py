#!/usr/bin/env python3
"""Comparison helpers for ablation, baselines, and repeated studies."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


_COMPARISON_METRICS: tuple[tuple[str, str], ...] = (
    ("macro_average", "workflow_step_f1"),
    ("macro_average", "workflow_sequence_f1"),
    ("macro_average", "workflow_grounding_f1"),
    ("macro_average", "node_coverage_relaxed_f1"),
    ("macro_average", "anchored_node_canonical_f1"),
    ("macro_average", "anchor_accuracy"),
    ("macro_average", "anchor_macro_f1"),
    ("macro_average", "relation_f1"),
    ("macro_average", "concept_f1"),
    ("macro_average", "concept_label_f1"),
    ("macro_average", "concept_relaxed_label_f1"),
    ("macro_average", "relation_relaxed_f1"),
    ("macro_average", "relation_family_agnostic_f1"),
)


def _metric_value(payload: dict[str, Any], section: str, key: str) -> float:
    return float(payload.get(section, {}).get(key, 0.0))


def _variant_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("variant_metadata", {})
    if isinstance(metadata, dict):
        return metadata
    return {}


def build_variant_summary_rows(evaluations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, evaluation in evaluations.items():
        macro = evaluation.get("macro_average", {})
        metadata = _variant_metadata(evaluation)
        rows.append(
            {
                "variant_id": variant_id,
                "component": metadata.get("component", ""),
                "mode": metadata.get("mode", ""),
                "preprocessing_source": metadata.get("preprocessing_source", ""),
                "attachment_source": metadata.get("attachment_source", ""),
                "uses_llm_preprocessing": bool(metadata.get("uses_llm_preprocessing", False)),
                "uses_llm_attachment": bool(metadata.get("uses_llm_attachment", False)),
                "paper_table": bool(metadata.get("paper_table", True)),
                "alias_for": metadata.get("alias_for", ""),
                "workflow_step_f1": float(macro.get("workflow_step_f1", 0.0)),
                "workflow_sequence_f1": float(macro.get("workflow_sequence_f1", 0.0)),
                "workflow_grounding_f1": float(macro.get("workflow_grounding_f1", 0.0)),
                "node_coverage_relaxed_f1": float(macro.get("node_coverage_relaxed_f1", 0.0)),
                "anchored_node_canonical_f1": float(macro.get("anchored_node_canonical_f1", 0.0)),
                "anchor_accuracy": float(macro.get("anchor_accuracy", 0.0)),
                "anchor_macro_f1": float(macro.get("anchor_macro_f1", 0.0)),
                "relation_f1": float(macro.get("relation_f1", 0.0)),
                "concept_f1": float(macro.get("concept_f1", 0.0)),
                "concept_label_f1": float(macro.get("concept_label_f1", 0.0)),
                "concept_relaxed_label_f1": float(macro.get("concept_relaxed_label_f1", 0.0)),
                "relation_relaxed_f1": float(macro.get("relation_relaxed_f1", 0.0)),
                "relation_family_agnostic_f1": float(macro.get("relation_family_agnostic_f1", 0.0)),
                "evaluated_gold_files": len(evaluation.get("evaluated_gold_files", [])),
            }
        )
    rows.sort(
        key=lambda item: (
            -item["workflow_grounding_f1"],
            -item["workflow_sequence_f1"],
            -item["workflow_step_f1"],
            -item["anchor_accuracy"],
            -item["relation_f1"],
            -item["anchored_node_canonical_f1"],
            -item["node_coverage_relaxed_f1"],
            item["variant_id"],
        )
    )
    return rows


def _ordered_rows(rows: list[dict[str, Any]], variant_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    lookup = {row["variant_id"]: row for row in rows}
    return [lookup[variant_id] for variant_id in variant_ids if variant_id in lookup]


def build_variant_table_groups(rows: list[dict[str, Any]]) -> dict[str, Any]:
    component_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        component = str(row.get("component", "")).strip() or "unspecified"
        component_groups.setdefault(component, []).append(row)

    return {
        "preprocessing_isolation_rows": _ordered_rows(rows, ("full_llm", "no_preprocessing_llm")),
        "attachment_isolation_rows": _ordered_rows(rows, ("full_llm", "no_attachment_llm", "embedding_top1", "deterministic")),
        "quality_control_rows": _ordered_rows(rows, ("full_llm", "no_rule_filter", "no_embedding_routing")),
        "component_variant_rows": component_groups,
    }


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
        metadata = _variant_metadata(variant_payload)
        delta_row = {
            "variant_id": row["variant_id"],
            "component": metadata.get("component", ""),
            "mode": metadata.get("mode", ""),
            "preprocessing_source": metadata.get("preprocessing_source", ""),
            "attachment_source": metadata.get("attachment_source", ""),
            "paper_table": bool(metadata.get("paper_table", True)),
        }
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

    paper_table_rows = [row for row in rows if row["paper_table"]]
    table_groups = build_variant_table_groups(rows)
    return {
        "baseline_variant": baseline_variant,
        "variant_rows": rows,
        "paper_table_variant_rows": paper_table_rows,
        "table_groups": table_groups,
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
