#!/usr/bin/env python3
"""Wrapper for running the CrossExtend-KG ablation suite."""

from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.ablation import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
