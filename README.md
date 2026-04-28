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
    regression_test1.py      # Single-doc test
    regression_test2.py      # Three-domain single-doc test
    regression_test3.py      # Full 9-doc test
    evaluate_attachment_gold.py  # Attachment gold evaluation
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

The recommended default LLM backend is `deepseek-v4-flash`.

To switch models, update `config/persistent/llm_backends.yaml`. Existing presets
already use `llm_backend_id: deepseek`, so changing
`backends.deepseek.model` replaces the active model for both `preprocess` and
`run`. If you want multiple selectable models, add another backend entry and
change the preset's `llm_backend_id`. Changing `default_backend` alone does not
affect presets that already set `llm_backend_id`.

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

### Attachment Gold Annotation (2026-04-26)

9 human-annotated attachment gold files (359 concepts total):

| Domain | Document | Concepts | Key Anchors |
|--------|----------|----------|-------------|
| battery | Busbar Insulator Shield Inspection | 30 | Housing:6, Component:8 |
| battery | Busbar Surface Contamination Inspection | 32 | Component:8, Media:4 |
| battery | Compression Pad Position Audit | 24 | Component:9, Fault:9 |
| cnc | Spindle Chiller Hose Leak Inspection | 42 | Component:14, Signal:7 |
| cnc | Spindle Drawbar Clamp Force Verification | 40 | Signal:17, Component:9 |
| cnc | Spindle Warm-Up Vibration Confirmation | 50 | Signal:17, Fault:11 |
| nev | Coolant Quick Connector Replacement | 40 | Signal:11, Fault:5 |
| nev | BMS Enclosure Seal Replacement | 49 | Fault:12, Signal:10 |
| nev | Drive Motor Coolant Hose Leak Confirmation | 52 | Signal:19, Fault:10 |

### v2 Regression Results (2026-04-26)

Rule-based attachment (deterministic, no LLM/embedding), all tests pass:

| Test | Docs | Domain | Nodes | Edges | Accepted Triples |
|------|------|--------|-------|-------|-----------------|
| Test 1 | 1 | battery | 59 | 69 | 32 |
| Test 2 | 3 | battery | 48 | 57 | 31 |
| Test 2 | 3 | cnc | 68 | 90 | 45 |
| Test 2 | 3 | nev | 73 | 115 | 66 |
| Test 3 | 9 | battery | 132 | 206 | 110 |
| Test 3 | 9 | cnc | 160 | 275 | 156 |
| Test 3 | 9 | nev | 173 | 314 | 181 |

Test 3 totals: **465 nodes, 795 edges, 447 accepted triples**.
Attachment acceptance: 348/349 (99.7%). Cross-domain hypernym consistency: 117/118 (99.2%).
See [docs/EXPERIMENT_REPORT.md](docs/EXPERIMENT_REPORT.md) for full details.

### 9-Doc Ablation: Embedding + LLM Variants (2026-04-26)

| Variant | Nodes | Edges | Acc Triples | Rejected Cands |
|---------|-------|-------|-------------|----------------|
| baseline_embedding_llm | 454 | 754 | 417 | 12 |
| **contextual_rerank_embedding_llm** | **461** | **776** | **432** | **5** |
| pure_llm | 459 | 772 | 430 | 7 |

- Contextual rerank achieves best performance: 432 triples, lowest rejection (5)
- NEV domain most sensitive to routing: 163 → 174 triples (+6.7%)
- CNC domain stable across all variants (148–151)

### Changes vs v2 Initial Release (2026-04-25)

- Completed 9-doc attachment gold annotation with v2 schema (15 backbone concepts, 359 concepts)
- 9-doc ablation study: baseline embedding vs contextual rerank vs pure LLM attachment
- Expanded backbone from 6 to 15 concepts with Tier-1 hypernym support
- Pipeline improvements: shared_hypernym routing, step_phase classification, workflow grounding edge fix
- Added attachment gold evaluation script (`scripts/evaluate_attachment_gold.py`)
- Regression test scripts updated for v2 architecture (test1/test2/test3)
- Rule-based attachment validated across 1/3/9 doc scales

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
