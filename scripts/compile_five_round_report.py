#!/usr/bin/env python3
"""Compile the final five-round optimization report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.reporting import compile_five_round_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile the final five-round optimization report.")
    parser.add_argument("--rounds-root", required=True, help="Directory containing round_01 ... round_05")
    parser.add_argument("--output", required=True, help="Output markdown report path")
    parser.add_argument("--title", default="Five-Round Optimization Report", help="Report title")
    args = parser.parse_args()

    output_path = compile_five_round_report(
        rounds_root=args.rounds_root,
        output_path=args.output,
        title=args.title,
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
