#!/usr/bin/env python3
"""Ablation helpers and CLI for CrossExtend-KG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ...pipeline.runner import run_pipeline
from ..comparison import compare_variant_evaluations, write_comparison_csv
from ..metrics import evaluate_variant_run, write_ablation_csv
from .specs import DEFAULT_ABLATION_SPECS, build_default_ablation_variants


def materialize_ablation_config(base_config_path: str | Path, output_dir: str | Path) -> Path:
    base_config_path = Path(base_config_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(base_config_path.read_text(encoding="utf-8-sig"))
    base_variants = payload.get("variants", [])
    if not base_variants:
        raise ValueError(f"config contains no variants: {base_config_path}")

    payload["benchmark_name"] = f"{payload.get('benchmark_name', 'run')}_ablation"
    payload["variants"] = build_default_ablation_variants(base_variants[0])

    config_path = output_dir / "ablation.config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_path


def run_ablation_experiment(
    base_config_path: str | Path,
    output_dir: str | Path,
    ground_truth_dir: str | Path | None = None,
    variant_ids: list[str] | None = None,
) -> dict[str, Any]:
    ablation_config_path = materialize_ablation_config(base_config_path, output_dir)
    benchmark_result = run_pipeline(str(ablation_config_path), variant_ids=variant_ids)

    selected_variants = set(variant_ids or [])
    evaluations: dict[str, Any] = {}
    if ground_truth_dir:
        for variant_id in benchmark_result.variant_results:
            if selected_variants and variant_id not in selected_variants:
                continue
            evaluations[variant_id] = evaluate_variant_run(
                run_root=benchmark_result.run_root,
                variant_id=variant_id,
                ground_truth_dir=ground_truth_dir,
            )

    comparison = compare_variant_evaluations(evaluations) if evaluations else {}

    output_root = Path(benchmark_result.run_root)
    report = {
        "ablation_config_path": str(ablation_config_path),
        "run_root": benchmark_result.run_root,
        "summary": benchmark_result.summary,
        "ablation_matrix": [
            spec
            for spec in DEFAULT_ABLATION_SPECS
            if not selected_variants or spec["variant_id"] in selected_variants
        ],
        "evaluations": evaluations,
        "comparison": comparison,
    }
    (output_root / "ablation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if evaluations:
        write_ablation_csv(output_root / "ablation_report.csv", comparison["variant_rows"])
        (output_root / "comparison_report.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_comparison_csv(output_root / "comparison_report.csv", comparison["deltas_vs_baseline"])

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default ablation suite for CrossExtend-KG.")
    parser.add_argument("--config", required=True, help="Base pipeline config path")
    parser.add_argument("--output-dir", required=True, help="Directory to store ablation config and outputs")
    parser.add_argument("--ground-truth-dir", default=None, help="Optional human gold directory for evaluation")
    parser.add_argument("--variants", nargs="*", default=None, help="Optional subset of ablation variant ids")
    args = parser.parse_args()

    report = run_ablation_experiment(
        base_config_path=args.config,
        output_dir=args.output_dir,
        ground_truth_dir=args.ground_truth_dir,
        variant_ids=args.variants,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
