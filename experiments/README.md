# Experiments Package

This package now keeps experiment logic in explicit subpackages instead of a flat file layout.

## Layout

- `metrics/`
  - strict paper-facing metrics
  - relaxed diagnostic metrics
  - per-file and per-variant evaluation helpers
- `ablation/`
  - default ablation matrix
  - ablation config materialization
  - ablation runner and report export
- `comparison/`
  - pairwise variant comparison
  - ranking rows and deltas versus the baseline variant
- `rounds.py`
  - round workspace staging and aligned corpus preparation
- `reporting.py`
  - round report templates and five-round report compilation

## Metric Philosophy

- `concept_metrics` and `relation_metrics` remain strict exact-match metrics for paper tables.
- `diagnostic_metrics` are supplementary and help explain alias mismatches, family confusions, and other near misses.
- The main pipeline should optimize the strict metrics first. Relaxed diagnostics are used to understand where the gap comes from, not to replace the official benchmark.

## Current Outputs

- `ablation_report.json`
- `ablation_report.csv`
- `comparison_report.json`
- `comparison_report.csv`
- per-variant evaluation payloads with strict metrics plus relaxed diagnostics
