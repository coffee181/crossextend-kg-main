#!/usr/bin/env python3
"""Evaluate one exported variant run against human gold and collect audit summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.rounds import collect_variant_audit_summary, evaluate_round_variant  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an exported variant run and emit audit summaries.")
    parser.add_argument("--run-root", required=True, help="Benchmark run root")
    parser.add_argument("--variant", required=True, help="Variant id, e.g. full_llm")
    parser.add_argument("--ground-truth-dir", default=None, help="Human gold directory")
    parser.add_argument("--gold-files", nargs="*", default=None, help="Optional subset of gold file names to evaluate")
    parser.add_argument("--metrics-output", default=None, help="Optional metrics JSON output path")
    parser.add_argument("--audit-output", default=None, help="Optional audit JSON output path")
    args = parser.parse_args()

    metrics = evaluate_round_variant(
        run_root=args.run_root,
        variant_id=args.variant,
        ground_truth_dir=args.ground_truth_dir,
        gold_file_names=args.gold_files,
    )
    audit = collect_variant_audit_summary(args.run_root, args.variant)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if args.metrics_output:
        Path(args.metrics_output).write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        Path(args.audit_output).write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
