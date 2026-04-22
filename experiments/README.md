# Experiments Guide

`experiments/` contains the evaluation, ablation, baseline, comparison, and reporting logic for the current paper-facing CrossExtend-KG mainline.

## Directory Layout

- `metrics/`
  Strict paper metrics plus relaxed diagnostics
- `ablation/`
  Variant specs, config materialization, and ablation runner
- `baselines/`
  Current paper-facing baselines
- `comparison/`
  Variant comparison, repeated-run aggregation, and significance helpers
- `rounds.py`
  Round-workspace staging and audit helpers

## Evaluation Contract

- Each gold JSON is evaluated against the corresponding domain graph after filtering
  predicted nodes and edges by `provenance_evidence_ids` that match the gold
  document ids.
- The active 9-file O&M gold package is source-aligned by same document id.
  Historical content-aligned alias mappings are no longer part of the paper-facing
  evaluation contract.
- If a paper claim depends on a metric that is not listed below, that metric
  should stay in diagnostics or the appendix unless explicitly promoted and justified.

## Metric Boundary

Primary paper metrics:

- `workflow_step_f1`
- `workflow_sequence_f1`

Supporting paper metrics:

- `anchor_accuracy`
- `anchor_macro_f1`

Conditional paper metric:

- `workflow_grounding_f1`
  Only promote this into the main table after `workflow_relation_ground_truth`
  is manually annotated for the evaluated files.

Auxiliary semantic metrics:

- `anchored_node_canonical_f1`
- `relation_f1`
- `node_coverage_relaxed_f1`

Diagnostic-only metrics:

- `concept_f1`
- `concept_label_f1`
- `concept_relaxed_label_f1`
- `relation_relaxed_f1`
- `relation_family_agnostic_f1`

Only the primary and supporting paper metrics should drive paper claims.
Do not let concept-only or relaxed semantic metrics replace the workflow-facing
main claim.

## Ablation Boundary

Current paper-facing ablation suite:

- `full_llm`
- `no_preprocessing_llm`
- `no_rule_filter`
- `no_embedding_routing`
- `no_attachment_llm`
- `embedding_top1`

Implemented but diagnostic-only ablations:

- `no_snapshots`
- `no_temporal_metadata`
- `no_lifecycle_events`
- `no_relation_constraints`
- `no_propagation_family`
- `no_communication_family`
- `no_structural_family`

## Baselines

Current paper-facing suite:

- `rule_pipeline`
- `llm_direct_graph`

Draft-only helper modules exist for SpaCy and direct single-prompt LLM extraction, but they are not wired into `run_baseline_suite` and should not be listed as active paper baselines.

## Repeated Runs And Significance

Repeated-run aggregation reports:

- per-run metrics
- `mean`
- `std`
- `min`
- `max`

Significance testing is limited to the primary paper metrics:

- `workflow_step_f1`
- `workflow_sequence_f1`
- `anchor_accuracy`
- `anchor_macro_f1`

The repeated-run wrapper now defaults to `--repeats 5` for paper-facing stability summaries.

## Recommended Commands

Run ablation:

```bash
python -m crossextend_kg.experiments.ablation.runner --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\ablation --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

Run baselines:

```bash
python D:\crossextend_kg\scripts\run_baselines.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\baselines --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

Run repeated experiments:

```bash
python D:\crossextend_kg\scripts\run_repeated_experiments.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\repeated --ground-truth-dir D:\crossextend_kg\data\ground_truth --repeats 5 --include-baselines --data-root D:\crossextend_kg\data
```
