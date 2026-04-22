#!/usr/bin/env python3
"""Variant-comparison helpers for experiment analysis."""

from experiments.comparison.repeated import aggregate_repeated_evaluations, compute_significance_tests, write_repeated_csv
from experiments.comparison.report import build_variant_summary_rows, build_variant_table_groups, compare_variant_evaluations, write_comparison_csv

__all__ = [
    "aggregate_repeated_evaluations",
    "build_variant_summary_rows",
    "build_variant_table_groups",
    "compare_variant_evaluations",
    "compute_significance_tests",
    "write_comparison_csv",
    "write_repeated_csv",
]
