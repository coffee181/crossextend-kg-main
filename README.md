# CrossExtend-KG

`CrossExtend-KG` constructs industrial knowledge graphs with a fixed shared backbone and a controlled attachment pipeline. The active runtime keeps the backbone predefined, treats every domain as a uniform application case, and exports structure-oriented artifacts instead of evaluation metrics.

## Documentation

- `docs/SYSTEM_DESIGN.md`: architecture rules, pipeline phases, and artifact model
- `docs/PIPELINE_INTEGRATION.md`: module interfaces and regression checkpoints
- `docs/PROJECT_ARCHITECTURE.md`: repository layout and module ownership
- `docs/EXECUTION_MEMORY.md`: resume-oriented execution memory for future sessions
- `docs/REAL_RUN_DATA_FLOW_BATTERY_20260417.md`: detailed real battery run data flow from raw document to final graph
- `config/README.md`: config schema and preset usage

## Pipeline Flow

```text
data -> evidence -> fixed backbone -> retrieve -> attach -> filter -> assemble -> snapshot -> export
```

## Quick Start

Recommended single-variant run:

```bash
export DEEPSEEK_API_KEY="your-api-key"

python3 -m crossextend_kg.cli run \
  --config crossextend_kg/config/persistent/pipeline.deepseek.json
```

Optional multi-variant stress run:

```bash
export DEEPSEEK_API_KEY="your-api-key"

python3 -m crossextend_kg.cli run \
  --config crossextend_kg/config/persistent/pipeline.deepseek_full.json
```

Preprocess raw documents:

```bash
python3 -m crossextend_kg.cli preprocess \
  --config crossextend_kg/config/persistent/preprocessing.deepseek.json
```

## Layout

```text
crossextend_kg/
  __init__.py
  cli.py
  config.py
  models.py
  io.py
  exceptions.py
  logging_config.py
  validation.py
  backends/
    embeddings.py
    llm.py
  config/
    README.md
    persistent/
    prompts/
    templates/
  docs/
    README.md
    SYSTEM_DESIGN.md
    PIPELINE_INTEGRATION.md
    PROJECT_ARCHITECTURE.md
  pipeline/
    runner.py
    evidence.py
    backbone.py
    router.py
    attachment.py
    memory.py
    graph.py
    artifacts.py
    utils.py
  preprocessing/
  rules/
    filtering.py
  scripts/
    visualize_propagation.py
  data/
  artifacts/
```

## Core API

```python
from crossextend_kg import run_pipeline

result = run_pipeline("crossextend_kg/config/persistent/pipeline.deepseek.json")
summary = result.variant_results["full_llm"].construction_summary

print(summary["backbone_size"])
print(summary["per_domain"]["battery"]["adapter_concept_count"])
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Execute the pipeline |
| `preprocess` | Convert raw documents to `EvidenceRecord`s |
| `replay` | Load one exported snapshot state |
| `rollback` | Load the rollback target snapshot state |

## Outputs

Each variant exports under `<artifact_root>/<run_id>/<variant_id>/`:

```text
run_meta.json
backbone_seed.json
backbone_final.json
backbone.json
construction_summary.json
temporal_memory_entries.jsonl
working/<domain_id>/
  evidence_units.jsonl
  schema_candidates.jsonl
  adapter_schema.json
  adapter_candidates.json
  adapter_candidates.accepted.json
  adapter_candidates.rejected.json
  backbone_reuse_candidates.json
  retrievals.json
  attachment_decisions.json
  historical_context.json
  graph_nodes.jsonl
  graph_edges.jsonl
  candidate_triples.jsonl
  relation_edges.*.json
  final_graph.json
  temporal_assertions.jsonl
  snapshot_manifest.jsonl
  snapshots/<snapshot_id>/
    nodes.jsonl
    edges.jsonl
    consistency.json
  exports/
```

## Architecture Rules

1. The backbone is predefined at runtime.
2. There is no privileged source domain and no dynamic backbone aggregation.
3. Variants differ only by explicit switches such as retrieval, filtering, memory, or attachment strategy.
4. No fallback or silent degradation is allowed in the main chain. Required stages must run correctly or fail explicitly.
5. The exported summary is structural and count-based.

## Recent Changes

- Removed experiment-only and downstream-task paths from the active runtime.
- Kept only the main route set: `reuse_backbone`, `vertical_specialize`, `reject`.
- Hardened final node admission with explicit reject reasons and exported rejection audit files.
- Added relation validation and data-flow trace export.
- Validated the main chain with a real battery single-document run using DeepSeek + local `bge-m3:latest`.

## Testing

```bash
python -m py_compile $(rg --files crossextend_kg tests | rg '\.py$')
pytest -q tests/test_crossextend_kg_regressions.py
```
