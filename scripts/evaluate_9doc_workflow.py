#!/usr/bin/env python3
"""Evaluate 9-document experiment with workflow metrics."""

import json
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from experiments.metrics.evaluate import evaluate_variant_run
from experiments.metrics.core import compute_metrics

def main():
    # Paths
    run_root = Path("artifacts/full_9doc_experiments/output/full9docs-20260420T134236Z")
    ground_truth_dir = Path("data/ground_truth")
    variant_id = "full_llm"

    # Evaluate
    print(f"Evaluating variant: {variant_id}")
    print(f"Run root: {run_root}")
    print(f"Ground truth: {ground_truth_dir}")

    report = evaluate_variant_run(
        run_root=str(run_root),
        variant_id=variant_id,
        ground_truth_dir=str(ground_truth_dir),
    )

    # Print results
    print("\n=== Evaluation Results ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Save report
    output_path = Path("artifacts/full_9doc_experiments/workflow_metrics_report.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to: {output_path}")

    return report

if __name__ == "__main__":
    main()