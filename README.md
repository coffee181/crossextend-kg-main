# CrossExtend-KG

[中文说明](README_CN.md)

CrossExtend-KG is a workflow-first industrial knowledge graph construction
project for O&M manuals. The active mainline is a no-fallback pipeline built
around step-aware extraction, fixed-backbone semantic routing with cross-domain
hypernym support, explicit attachment decisions, dual-layer graph assembly,
and human-gold evaluation.

## Current Scope

- Input type: `om_manual`
- Active domains: `battery`, `cnc`, `nev`
- Core graph shape: `single graph, dual layer`
- Highest execution principle: `no fallback`
- Data model version: `v2` (backward compatible with v1)

## Active Graph Design

### Workflow Layer
- `workflow_step` nodes are first-class workflow nodes
- `workflow_step -> workflow_step` captures ordered procedure flow (sequence edges)
- `workflow_step -> semantic node` captures step grounding (action_object edges)
- Each step carries `step_phase`: observe / diagnose / repair / verify

### Semantic Layer
- Fixed backbone: 5 base types + 10 Tier-1 hypernym anchors
  - Base: `Asset`, `Component`, `Signal`, `State`, `Fault`
  - Tier-1: `Seal`, `Connector`, `Sensor`, `Controller`, `Coolant`, `Actuator`, `Power`, `Housing`, `Fastener`, `Media`
- `Task` is retained only as a legacy evaluation projection for step nodes
- Each semantic node may carry `shared_hypernym` for cross-domain mapping
- Semantic concept-to-concept edges provide structural, communication, propagation, and lifecycle support

### v2 Innovation Points
1. **Cross-domain generalization**: `shared_hypernym` enables consistent concept mapping across domains (e.g., "O-ring" / "cover gasket" / "door seal" all map to `Seal`)
2. **Temporal backtracking**: `step_phase` classifies step intent; `state_transitions` capture lifecycle changes; `procedure_meta` records document-level metadata
3. **Complex propagation paths**: `diagnostic_edges` separate communication/propagation evidence; `cross_step_relations` link concepts across steps for inter-step reasoning

## Repository Mainline

```text
O&M markdown
  -> preprocess (v2: hypernym + phase + diagnostic extraction)
  -> step-scoped evidence records (v2 fields with v1 fallback)
  -> semantic candidate aggregation (hypernym -> routing_features)
  -> 15-concept fixed backbone routing
  -> attachment decisions
  -> rule filtering (hypernym as anchor fallback)
  -> dual-layer graph assembly (v2 field consumption with fallback)
  -> GraphML / JSON export (v2 attributes)
  -> human-gold evaluation
```

## Project Structure

```
crossextend_kg/
  cli.py                     # CLI entry point
  config.py                  # Config loader
  models.py                  # Data models (v1 + v2)
  file_io.py                 # JSON/CSV I/O helpers
  pipeline/
    evidence.py              # Evidence loading, normalization, candidate aggregation
    backbone.py              # Backbone construction
    graph.py                 # Dual-layer graph assembly
    artifacts.py             # Artifact export
    exports/graphml.py       # GraphML export
    utils.py                 # Runtime utilities
  preprocessing/
    processor.py             # Main preprocessing processor
    extractor.py             # LLM extraction wrapper
    parser.py                # Markdown parser
    models.py                # Preprocessing data models
  rules/
    filtering.py             # Attachment filtering (v2: hypernym fallback)
  backends/
    llm.py                   # LLM backend
    embeddings.py            # Embedding backend
    faiss_cache.py           # FAISS cache
  temporal/                  # Optional lifecycle / temporal support
  experiments/
    metrics/                 # Graph evaluation metrics
    downstream/              # Workflow-centric downstream tasks
  data/
    battery_om_manual_en/    # Battery O&M source markdown
    cnc_om_manual_en/        # CNC O&M source markdown
    ev_om_manual_en/         # NEV O&M source markdown
    evidence_records/        # Per-domain evidence record JSONs
    ground_truth/            # Human gold annotations (9 files)
  config/
    persistent/              # Stable runtime configs
    prompts/                 # LLM extraction and attachment prompts
  docs/                      # Architecture and design documentation
  tests/                     # Unit tests (19 tests: 12 v1 + 7 v2)
  scripts/                   # Regression test scripts
```

## Current Config Layout

Human-maintained configs live under `config/persistent/`:

- `pipeline.base.yaml` -- v2: 15-concept backbone
- `pipeline.deepseek.yaml` -- deepseek preset
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json` -- v2: Tier-1 hypernyms in allowed types

The recommended default LLM backend is `deepseek-chat`.

## Commands

Preprocess:

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
```

Run all active domains:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml
```

Run only selected domains:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml --domains battery
```

Evaluate one graph:

```bash
python -m crossextend_kg.cli evaluate --gold data/ground_truth/battery_BATOM_002.json --graph artifacts/some_run/full_llm/working/battery/final_graph.json
```

Evaluate one benchmark run:

```bash
python -m crossextend_kg.cli evaluate --run-root artifacts/some_run --variant full_llm --ground-truth-dir data/ground_truth
```

## Experiments

`experiments/` keeps two active areas:

- `experiments/metrics/`
  strict graph-construction evaluation and graph-quality diagnostics
- `experiments/downstream/`
  workflow-centric downstream task design and benchmark schema

Primary paper metrics:

- `workflow_step_f1`, `workflow_sequence_f1`, `workflow_grounding_f1`
- `anchor_accuracy`, `anchor_macro_f1`

v2 diagnostic metrics:

- `hypernym_coverage` -- fraction of semantic nodes with shared_hypernym
- `phase_distribution` -- observe/diagnose/repair/verify distribution

## Documentation

- [docs/README.md](docs/README.md)
- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) -- Architecture rules and v2 model extensions
- [docs/PIPELINE_DATA_FLOW.md](docs/PIPELINE_DATA_FLOW.md) -- End-to-end data flow
- [docs/WORKFLOW_KG_DESIGN.md](docs/WORKFLOW_KG_DESIGN.md) -- Dual-layer design and v2 innovations
- [docs/OPEN_SOURCE_UPDATE_CN.md](docs/OPEN_SOURCE_UPDATE_CN.md) -- Chinese summary of v2 restructuring
