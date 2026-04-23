# CrossExtend-KG

[中文说明](README_CN.md)

CrossExtend-KG is a workflow-first industrial knowledge graph construction
project for O&M manuals. The active mainline is a no-fallback pipeline built
around step-aware extraction, fixed-backbone semantic routing, explicit
attachment decisions, dual-layer graph assembly, and human-gold evaluation.

## Current Scope

- Input type: `om_manual`
- Active domains: `battery`, `cnc`, `nev`
- Core graph shape: `single graph, dual layer`
- Highest execution principle: `no fallback`

## Active Graph Design

- `workflow_step` nodes are first-class workflow nodes.
- Semantic nodes remain `Asset`, `Component`, `Signal`, `State`, and `Fault`.
- `Task` is retained only as a legacy evaluation projection for step nodes.
- `workflow_step -> workflow_step` captures ordered procedure flow.
- `workflow_step -> semantic node` captures step grounding.
- Semantic concept-to-concept edges provide structural and diagnostic support.

## Repository Mainline

```text
O&M markdown
  -> preprocess
  -> step-scoped evidence records
  -> semantic candidate aggregation
  -> fixed backbone routing
  -> attachment decisions
  -> rule filtering
  -> dual-layer graph assembly
  -> GraphML / JSON export
  -> human-gold evaluation
```

## Current Config Layout

Human-maintained configs live under `config/persistent/`:

- `pipeline.base.yaml`
- `pipeline.deepseek.yaml`
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json`

The recommended default LLM backend is `deepseek-reasoner`.

## Commands

Preprocess:

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

Run all active domains:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```

Run only selected domains:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --domains battery
```

Evaluate one graph:

```bash
python -m crossextend_kg.cli evaluate --gold D:\crossextend_kg\data\ground_truth\battery_BATOM_002.json --graph D:\crossextend_kg\artifacts\some_run\full_llm\working\battery\final_graph.json
```

Evaluate one benchmark run:

```bash
python -m crossextend_kg.cli evaluate --run-root D:\crossextend_kg\artifacts\some_run --variant full_llm --ground-truth-dir D:\crossextend_kg\data\ground_truth
```

## Experiments

`experiments/` now keeps only two active areas:

- `experiments/metrics/`
  strict graph-construction evaluation and graph-quality diagnostics
- `experiments/downstream/`
  workflow-centric downstream task design and benchmark schema

The downstream evaluation emphasis is now:

- evidence-grounded workflow retrieval
- repair suffix ranking

## Documentation

- `docs/README.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/PIPELINE_DATA_FLOW.md`
- `docs/WORKFLOW_KG_DESIGN.md`
- `docs/DOWNSTREAM_EVALUATION.md`
- `docs/GRAPH_QUALITY_DIAGNOSIS.md`
