#!/usr/bin/env python3
"""Variant-comparison helpers for experiment analysis."""

from .report import build_variant_summary_rows, compare_variant_evaluations, write_comparison_csv

__all__ = [
    "build_variant_summary_rows",
    "compare_variant_evaluations",
    "write_comparison_csv",
]
