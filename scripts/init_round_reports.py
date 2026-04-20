#!/usr/bin/env python3
"""Initialize one or more optimization-round report directories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.reporting import initialize_round_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize optimization round report directories.")
    parser.add_argument("--base-dir", required=True, help="Root directory for round artifacts")
    parser.add_argument("--round-id", required=True, help="Round id, for example round_01")
    parser.add_argument("--title", required=True, help="Human-readable round title")
    parser.add_argument("--scope", nargs="*", default=None, help="Scope labels/doc ids")
    parser.add_argument("--config", default=None, help="Optional config path")
    parser.add_argument("--commands", nargs="*", default=None, help="Optional planned commands")
    args = parser.parse_args()

    round_dir = initialize_round_directory(
        base_dir=args.base_dir,
        round_id=args.round_id,
        title=args.title,
        scope=args.scope or [],
        config_path=args.config,
        run_commands=args.commands or [],
    )
    print(str(round_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
