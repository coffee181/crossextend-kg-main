# Experiments Guide

`experiments/` now keeps only the active paper-facing experiment surface.

## Active Areas

- `metrics/`
  strict graph-construction evaluation and graph-quality diagnostics
- `downstream/`
  workflow-centric downstream task design and typed benchmark schema

## Metric Boundary

Primary graph-facing metrics:

- `workflow_step_f1`
- `workflow_sequence_f1`
- `workflow_grounding_precision / recall / f1`
- `anchor_accuracy`
- `anchor_macro_f1`

Diagnostics remain available under `metrics/`, but they are nested and should
not replace the workflow-facing paper claim:

- `anchored_node_canonical_f1`
- `relation_f1`
- concept-level and relaxed matching metrics

## Downstream Boundary

The current downstream plan emphasizes:

- `workflow_retrieval`
- `repair_suffix_ranking`

See `downstream/README.md` and `docs/DOWNSTREAM_EVALUATION.md`.
