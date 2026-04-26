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
  -> step-scoped evidence records (v2 fields as authoritative workflow sources)
  -> semantic candidate aggregation (hypernym -> routing_features)
  -> 15-concept fixed backbone routing
  -> attachment decisions
  -> rule filtering (hypernym-assisted anchoring)
  -> dual-layer graph assembly (v2 workflow fields + semantic relation fields)
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
- `pipeline.test3.yaml` -- default reproducible Test3 evidence-record run
- `pipeline.deepseek.yaml` -- deepseek preset; requires generated evidence record files
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
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml
```

Run only selected domains:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml --domains battery
```

Replay latest exported snapshot from a variant directory:

```bash
python -m crossextend_kg.cli replay --run-dir results/test3/<run_id>/full_llm
```

Gold evaluation is supported when a local gold directory is present:

```bash
python -m crossextend_kg.cli evaluate --gold <gold.json> --graph <final_graph.json>
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

### v2 Regression Results (2026-04-25)

Three tests with real API calls (DeepSeek + DashScope), no fallback:

| Test | Docs | Domain | Nodes | Edges | Hypernym Cov | Top Hypernyms |
|------|------|--------|-------|-------|-------------|---------------|
| Test 1 | 1 | battery | 41 | 30 | 14.7% | Housing:3, Seal:1, Fastener:1 |
| Test 2 | 3 | battery | 33 | 31 | 23.1% | Housing:4, Seal:1, Fastener:1 |
| Test 2 | 3 | cnc | 54 | 44 | **71.7%** | Coolant:15, Fastener:9, Connector:4 |
| Test 2 | 3 | nev | 56 | 62 | 29.8% | Seal:8, Connector:2, Coolant:2 |
| Test 3 | 9 | battery | 114 | 103 | **49.5%** | Housing:13, Media:11, Power:9 |
| Test 3 | 9 | cnc | 142 | 140 | 32.8% | Coolant:15, Fastener:9, Connector:4 |
| Test 3 | 9 | nev | 153 | 164 | 28.1% | Seal:11, Connector:9, Coolant:5 |

7/10 Tier-1 hypernyms appear in all 3 domains at 9-doc scale. See
[docs/EXPERIMENT_REPORT.md](docs/EXPERIMENT_REPORT.md) for full details.

## Documentation

- [docs/README.md](docs/README.md)
- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) -- Architecture rules and v2 model extensions
- [docs/PIPELINE_DATA_FLOW.md](docs/PIPELINE_DATA_FLOW.md) -- End-to-end data flow
- [docs/DATA_FLOW_DIAGRAM.md](docs/DATA_FLOW_DIAGRAM.md) -- Real single-doc data flow example with format changes at each stage
- [docs/WORKFLOW_KG_DESIGN.md](docs/WORKFLOW_KG_DESIGN.md) -- Dual-layer design and v2 innovations
- [docs/EXPERIMENT_REPORT.md](docs/EXPERIMENT_REPORT.md) -- v2 regression experiment report
- [docs/OPEN_SOURCE_UPDATE_CN.md](docs/OPEN_SOURCE_UPDATE_CN.md) -- Chinese summary of v2 restructuring
- [docs/DATA_FLOW_DIAGRAM_CN.md](docs/DATA_FLOW_DIAGRAM_CN.md) -- 数据流图中文版
- [docs/EXPERIMENT_REPORT_CN.md](docs/EXPERIMENT_REPORT_CN.md) -- 回归实验报告中文版
