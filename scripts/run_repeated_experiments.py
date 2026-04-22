#!/usr/bin/env python3
"""Run repeated ablation/baseline experiments and aggregate stability metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.ablation import run_ablation_experiment  # noqa: E402
from crossextend_kg.experiments.baselines import run_baseline_suite  # noqa: E402
from crossextend_kg.experiments.comparison import aggregate_repeated_evaluations, compute_significance_tests, write_repeated_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated CrossExtend-KG experiments and aggregate mean/std metrics.")
    parser.add_argument("--config", required=True, help="Base pipeline config path")
    parser.add_argument("--output-dir", required=True, help="Directory to store repeated-run outputs")
    parser.add_argument("--ground-truth-dir", required=True, help="Human gold directory for evaluation")
    parser.add_argument("--repeats", type=int, default=5, help="Number of repeats per selected experiment path")
    parser.add_argument("--variants", nargs="*", default=None, help="Optional ablation variant subset")
    parser.add_argument("--include-baselines", action="store_true", help="Also run the baseline suite each repeat")
    parser.add_argument("--baselines", nargs="*", default=None, help="Optional baseline subset")
    parser.add_argument("--data-root", default=None, help="Raw markdown root required when include-baselines includes rule_pipeline")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    repeated_evaluations: dict[str, list[dict[str, object]]] = {}
    iteration_reports: list[dict[str, object]] = []

    for repeat_index in range(1, args.repeats + 1):
        repeat_root = output_dir / f"repeat_{repeat_index:02d}"
        ablation_report = run_ablation_experiment(
            base_config_path=args.config,
            output_dir=repeat_root / "ablation",
            ground_truth_dir=args.ground_truth_dir,
            variant_ids=args.variants,
            data_root=args.data_root,
        )
        iteration_reports.append(
            {
                "repeat_index": repeat_index,
                "ablation_run_root": ablation_report["run_root"],
            }
        )
        for variant_id, payload in ablation_report.get("evaluations", {}).items():
            repeated_evaluations.setdefault(variant_id, []).append(payload)

        if args.include_baselines:
            baseline_report = run_baseline_suite(
                base_config_path=args.config,
                output_dir=repeat_root / "baselines",
                ground_truth_dir=args.ground_truth_dir,
                baseline_ids=args.baselines,
                data_root=args.data_root,
            )
            iteration_reports[-1]["baseline_run_root"] = baseline_report["run_root"]
            for baseline_id, payload in baseline_report.get("evaluations", {}).items():
                repeated_evaluations.setdefault(baseline_id, []).append(payload)

    aggregate = aggregate_repeated_evaluations(repeated_evaluations)
    significance = compute_significance_tests(repeated_evaluations) if "full_llm" in repeated_evaluations else {}
    report = {
        "config_path": str(Path(args.config).resolve()),
        "ground_truth_dir": str(Path(args.ground_truth_dir).resolve()),
        "repeats": args.repeats,
        "iteration_reports": iteration_reports,
        **aggregate,
        "significance_tests": significance,
    }

    report_path = output_dir / "repeated_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_repeated_csv(output_dir / "repeated_report.csv", aggregate["summary_rows"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
