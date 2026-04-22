#!/usr/bin/env python3
"""Repeated-run aggregation for experiment stability reporting."""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Any


_METRIC_KEYS: tuple[str, ...] = (
    "workflow_step_f1",
    "workflow_sequence_f1",
    "workflow_grounding_f1",
    "node_coverage_relaxed_f1",
    "anchored_node_canonical_f1",
    "anchor_accuracy",
    "anchor_macro_f1",
    "relation_f1",
    "concept_f1",
    "concept_label_f1",
    "concept_relaxed_label_f1",
    "relation_relaxed_f1",
    "relation_family_agnostic_f1",
)

_PRIMARY_METRIC_KEYS: tuple[str, ...] = (
    "workflow_step_f1",
    "workflow_sequence_f1",
    "anchor_accuracy",
    "anchor_macro_f1",
)


def _variant_metadata(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    if not payloads:
        return {}
    metadata = payloads[0].get("variant_metadata", {})
    if isinstance(metadata, dict):
        return metadata
    return {}


def _metric_series(payloads: list[dict[str, Any]], metric_name: str) -> list[float]:
    values: list[float] = []
    for payload in payloads:
        macro = payload.get("macro_average", {})
        values.append(float(macro.get(metric_name, 0.0)))
    return values


def _summary_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def aggregate_repeated_evaluations(
    repeated_evaluations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not repeated_evaluations:
        raise ValueError("aggregate_repeated_evaluations requires at least one variant")

    variant_stats: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    for variant_id, payloads in repeated_evaluations.items():
        if not payloads:
            raise ValueError(f"variant {variant_id} has no repeated evaluation payloads")
        metadata = _variant_metadata(payloads)
        metric_stats = {
            metric_name: _summary_stats(_metric_series(payloads, metric_name))
            for metric_name in _METRIC_KEYS
        }
        variant_stats[variant_id] = {
            "variant_id": variant_id,
            "variant_metadata": metadata,
            "run_count": len(payloads),
            "evaluated_gold_files": sorted(
                {
                    gold_file
                    for payload in payloads
                    for gold_file in payload.get("evaluated_gold_files", [])
                }
            ),
            "metrics": metric_stats,
        }
        summary_rows.append(
            {
                "variant_id": variant_id,
                "component": metadata.get("component", ""),
                "mode": metadata.get("mode", ""),
                "preprocessing_source": metadata.get("preprocessing_source", ""),
                "attachment_source": metadata.get("attachment_source", ""),
                "uses_llm_preprocessing": bool(metadata.get("uses_llm_preprocessing", False)),
                "uses_llm_attachment": bool(metadata.get("uses_llm_attachment", False)),
                "paper_table": bool(metadata.get("paper_table", True)),
                "run_count": len(payloads),
                **{
                    f"{metric_name}_{field}": metric_stats[metric_name][field]
                    for metric_name in _METRIC_KEYS
                    for field in ("mean", "std", "min", "max")
                },
            }
        )

    summary_rows.sort(
        key=lambda item: (
            -float(item["workflow_grounding_f1_mean"]),
            -float(item["workflow_sequence_f1_mean"]),
            -float(item["workflow_step_f1_mean"]),
            -float(item["anchor_accuracy_mean"]),
            -float(item["relation_f1_mean"]),
            -float(item["anchored_node_canonical_f1_mean"]),
            -float(item["node_coverage_relaxed_f1_mean"]),
            item["variant_id"],
        )
    )
    return {
        "metric_keys": list(_METRIC_KEYS),
        "variant_stats": variant_stats,
        "summary_rows": summary_rows,
    }


def write_repeated_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Statistical significance testing
# ---------------------------------------------------------------------------


def _paired_t_test(a: list[float], b: list[float]) -> dict[str, float]:
    """Compute a paired t-test between two matched samples.

    Returns t-statistic and two-tailed p-value.
    Falls back to a simple approximation if scipy is unavailable.
    """
    n = min(len(a), len(b))
    if n < 2:
        return {"t_statistic": 0.0, "p_value": 1.0, "n": n}

    diffs = [a[i] - b[i] for i in range(n)]
    mean_d = statistics.fmean(diffs)
    std_d = statistics.stdev(diffs) if n > 1 else 0.0

    if std_d == 0.0:
        return {"t_statistic": 0.0, "p_value": 1.0 if mean_d == 0 else 0.0, "n": n}

    t_stat = mean_d / (std_d / math.sqrt(n))

    # Try scipy for accurate p-value
    try:
        from scipy import stats as sp_stats
        p_value = float(sp_stats.t.sf(abs(t_stat), df=n - 1) * 2)
    except ImportError:
        # Rough approximation using normal distribution for large n
        p_value = 2.0 * (1.0 - _normal_cdf(abs(t_stat)))

    return {
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_value, 6),
        "n": n,
    }


def _normal_cdf(x: float) -> float:
    """Approximate normal CDF using the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bootstrap_ci(
    values: list[float],
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
) -> dict[str, float]:
    """Compute bootstrap confidence interval.

    Args:
        values: Observed sample values.
        confidence: Confidence level (default 0.95).
        n_bootstrap: Number of bootstrap resamples.

    Returns:
        Dict with mean, lower, upper bounds and CI width.
    """
    import random

    n = len(values)
    if n < 2:
        mean = values[0] if values else 0.0
        return {"mean": mean, "ci_lower": mean, "ci_upper": mean, "ci_width": 0.0}

    rng = random.Random(42)
    boot_means: list[float] = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(values) for _ in range(n)]
        boot_means.append(statistics.fmean(sample))

    boot_means.sort()
    alpha = 1.0 - confidence
    lower_idx = max(0, int(n_bootstrap * alpha / 2))
    upper_idx = min(n_bootstrap - 1, int(n_bootstrap * (1 - alpha / 2)))

    mean = statistics.fmean(values)
    ci_lower = boot_means[lower_idx]
    ci_upper = boot_means[upper_idx]

    return {
        "mean": round(mean, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "ci_width": round(ci_upper - ci_lower, 4),
    }


def compute_significance_tests(
    repeated_evaluations: dict[str, list[dict[str, Any]]],
    baseline_variant: str = "full_llm",
    confidence: float = 0.95,
    metric_keys: tuple[str, ...] = _PRIMARY_METRIC_KEYS,
) -> dict[str, Any]:
    """Compute statistical significance for all variants vs. baseline.

    For each variant and metric, computes:
      - Paired t-test (t-statistic and p-value)
      - Bootstrap confidence interval

    Args:
        repeated_evaluations: variant_id -> list of evaluation payloads.
        baseline_variant: Variant to compare against.
        confidence: Confidence level for bootstrap CI.

    Returns:
        Dict with per-variant, per-metric significance results.
    """
    if baseline_variant not in repeated_evaluations:
        raise ValueError(f"baseline variant '{baseline_variant}' not in evaluations")

    baseline_payloads = repeated_evaluations[baseline_variant]
    results: dict[str, Any] = {}

    for variant_id, payloads in repeated_evaluations.items():
        if variant_id == baseline_variant:
            continue

        metric_results: dict[str, Any] = {}
        for metric_name in metric_keys:
            baseline_values = _metric_series(baseline_payloads, metric_name)
            variant_values = _metric_series(payloads, metric_name)

            t_test = _paired_t_test(baseline_values, variant_values)
            baseline_ci = _bootstrap_ci(baseline_values, confidence)
            variant_ci = _bootstrap_ci(variant_values, confidence)

            metric_results[metric_name] = {
                "baseline_mean": baseline_ci["mean"],
                "variant_mean": variant_ci["mean"],
                "delta": round(variant_ci["mean"] - baseline_ci["mean"], 4),
                "paired_t_test": t_test,
                "baseline_ci": baseline_ci,
                "variant_ci": variant_ci,
                "significant": t_test["p_value"] < (1.0 - confidence),
            }

        results[variant_id] = {
            "variant_id": variant_id,
            "baseline_variant": baseline_variant,
            "n_runs_baseline": len(baseline_payloads),
            "n_runs_variant": len(payloads),
            "metrics": metric_results,
        }

    return {
        "baseline_variant": baseline_variant,
        "confidence_level": confidence,
        "metric_keys": list(metric_keys),
        "comparisons": results,
    }
