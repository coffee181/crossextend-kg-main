# CrossExtend-KG

[中文说明](README_CN.md)

CrossExtend-KG is an industrial knowledge graph construction project centered on O&M manuals. The active paper-facing mainline is a no-fallback pipeline built around step-aware extraction, fixed-backbone routing, explicit attachment decisions, and rule-based graph refinement.

## Current Scope

- Input type: `om_manual`
- Active domains: `battery`, `cnc`, `nev`
- Paper-facing variant: `full_llm`
- Default paper-facing ablations: `full_llm`, `no_preprocessing_llm`, `no_rule_filter`, `no_embedding_routing`, `no_attachment_llm`, `embedding_top1`
- Paper-facing baselines: `rule_pipeline`, `llm_direct_graph`
- Paper metrics: human gold only
- Highest execution principle: `no fallback`

## What Changed In This Update

- Reworked persistent configs from duplicated JSON presets into layered YAML configs.
- Added shared base configs for pipeline and preprocessing.
- Moved LLM and embedding model choices into backend registries.
- Added `extends`, `llm_backend_id`, and `embedding_backend_id` support to the shared loader.
- Kept JSON backward compatibility for generated configs, ablation materialization, and tests.
- Aligned preprocessing with the current raw O&M directory names such as `battery_om_manual_en` and `ev_om_manual_en`.
- Improved package-mode import stability by reducing hard dependence on root-only absolute imports for config, models, and file I/O helpers.

## Workflow Dual-Layer Graph

The active graph representation is now a `single graph, dual layer` runtime:

- `workflow_step` nodes are first-class graph nodes with `node_layer="workflow"`.
- semantic concepts remain normal graph nodes with `node_layer="semantic"`.
- `Task` is kept only as a legacy evaluation projection for current human gold, not as a real semantic attachment target.
- `task_dependency` is now split by graph role:
  - `workflow_step -> workflow_step` stays as workflow sequence edges
  - `workflow_step -> semantic node` is promoted as workflow grounding edges
- strict paper metrics still evaluate the legacy projection, while workflow diagnostics report how much real O&M chain visibility the graph gained.

## Active Architecture

```text
O&M markdown
  -> preprocessing extraction
  -> step-aware EvidenceRecord
  -> semantic SchemaCandidate aggregation
  -> fixed backbone retrieval / routing
  -> semantic attachment decisions
  -> rule filtering
  -> dual-layer graph assembly
  -> export + human-gold evaluation
```

## Config Layout

Human-maintained configs now live under `config/persistent/` as YAML:

- `pipeline.base.yaml`
  Stable backbone, relations, domains, and runtime defaults
- `pipeline.deepseek.yaml`
  Recommended main preset
- `pipeline.deepseek.battery_only.yaml`
  Battery-only debugging preset
- `pipeline.deepseek_full.yaml`
  Optional multi-variant stress preset
- `preprocessing.base.yaml`
  Shared preprocessing defaults
- `preprocessing.deepseek.yaml`
  Recommended preprocessing preset
- `llm_backends.yaml`
  LLM backend registry
- `embedding_backends.yaml`
  Embedding backend registry

Typical model switching now only requires changing backend ids in a thin wrapper instead of cloning a full pipeline config.

## Recommended Commands

Preprocess raw O&M markdown:

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

Run the main pipeline:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```

Run the ablation suite:

```bash
python -m crossextend_kg.experiments.ablation.runner --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\ablation --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

Run the baseline suite:

```bash
python D:\crossextend_kg\scripts\run_baselines.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\baselines --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

Run repeated experiments:

```bash
python D:\crossextend_kg\scripts\run_repeated_experiments.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\repeated --ground-truth-dir D:\crossextend_kg\data\ground_truth --repeats 5 --include-baselines --data-root D:\crossextend_kg\data
```

Current validation uses real-run artifacts, targeted `py_compile`, focused `unittest` regressions under `tests/`, and repeated-run summaries.

## Documentation

- `docs/README.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/PIPELINE_INTEGRATION.md`
- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
- `docs/GROUND_TRUTH_QUALITY_ANALYSIS.md`
- `docs/FIVE_ROUND_OPTIMIZATION_REPORT.md`
