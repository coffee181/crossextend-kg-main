#!/usr/bin/env python3
"""Compute graph metrics against a human gold file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.metrics import compute_metrics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute graph metrics against a human gold file.")
    parser.add_argument("--gold", required=True, help="Path to human gold JSON")
    parser.add_argument("--graph", required=True, help="Path to final_graph.json")
    parser.add_argument("--output", default=None, help="Optional output JSON path")
    args = parser.parse_args()

    metrics = compute_metrics(args.gold, args.graph)
    payload = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
