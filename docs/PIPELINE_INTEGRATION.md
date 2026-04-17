# Pipeline Integration Verification

**Updated**: 2026-04-17  
**Status**: Main runtime only

## Overview

This document tracks the active integration points after removing dynamic-backbone, evaluation, and downstream-task wiring.

## End-to-End Flow

### Phase 1: Evidence Loading

```python
from crossextend_kg.pipeline import load_records_by_domain, aggregate_schema_candidates

records_by_domain = load_records_by_domain(config)
candidates_by_domain = aggregate_schema_candidates(records_by_domain)
```

Verification points:

- records are filtered by `domain_id` and `source_types`
- all domains use `role="target"`
- candidate aggregation is per-domain and per-label
- empty domains are preserved in the result map

### Phase 2: Frozen Backbone Build

```python
from crossextend_kg.pipeline import build_backbone

backbone_concepts, backbone_descriptions, curated_backbone_concepts = build_backbone(config)
```

Verification points:

- every `seed_concept` is included
- `seed_descriptions` are preserved
- optional curated supplements are loaded from `domains[].ontology_seed_path`
- no runtime LLM backbone extraction is performed

### Phase 3: MemoryBank Retrieval

```python
from crossextend_kg.pipeline import load_persistent_memory_bank, retrieve_historical_context

persistent_entries = load_persistent_memory_bank(config)
historical_context = retrieve_historical_context(
    config=config,
    embedding_backend=embedding_backend,
    records_by_domain=records_by_domain,
    candidates_by_domain=candidates_by_domain,
    persistent_entries=persistent_entries,
)
```

Verification points:

- self-retrieval is filtered by shared evidence ids
- future memory entries are filtered by timestamp
- same-domain hits score highest, while cross-domain hits can still contribute
- top-k historical context is returned per candidate

### Phase 4: Retrieval and Attachment

```python
from crossextend_kg.pipeline import decide_attachments_for_domain, retrieve_anchor_rankings

retrievals = retrieve_anchor_rankings(
    embedding_backend=embedding_backend,
    backbone_descriptions=backbone_descriptions,
    candidates=candidates,
    top_k=config.runtime.retrieval_top_k,
)

decisions = decide_attachments_for_domain(
    config=config,
    variant=variant,
    llm_backend=llm_backend,
    domain_id=domain_id,
    candidates=candidates,
    retrievals=retrievals,
    historical_context=historical_context.get(domain_id, {}),
    backbone_descriptions=backbone_descriptions,
    backbone_concepts=set(backbone_concepts),
)
```

Verification points:

- seed labels reuse the backbone directly
- embedding retrieval feeds anchor proposals
- MemoryBank context is injected only when the variant enables it
- LLM failures raise instead of silently falling back

### Phase 5: Rule Filtering

```python
from crossextend_kg.rules import filter_attachment_decision
```

Verification points:

- illegal routes are rejected
- `vertical_specialize` requires a backbone parent unless free-form growth is allowed
- backbone labels must use `reuse_backbone`

### Phase 6: Schema and Graph Assembly

```python
from crossextend_kg.pipeline import build_domain_schemas, assemble_domain_graphs

schemas = build_domain_schemas(
    config=config,
    candidates_by_domain=candidates_by_domain,
    decisions_by_domain=decisions_by_domain,
    backbone_concepts=backbone_concepts,
)

domain_graphs = assemble_domain_graphs(
    config=config,
    variant=variant,
    records_by_domain=records_by_domain,
    schemas=schemas,
    decisions_by_domain=decisions_by_domain,
    backbone_concepts=backbone_concepts,
)
```

Verification points:

- accepted adapter concepts are materialized into domain schema
- graph nodes and edges are exported per domain
- snapshots are created when `enable_snapshots=true`
- relation validation runs when enabled in runtime config

### Phase 7: Export

```python
from crossextend_kg.pipeline import export_variant_run, export_benchmark_summary
```

Verification points:

- variant roots export `backbone_seed.json`, `backbone_final.json`, and `construction_summary.json`
- per-domain working directories export schema, retrieval, decision, graph, and snapshot files
- replayable snapshots always include `nodes.jsonl`, `edges.jsonl`, and `consistency.json` even when generic JSONL export is disabled
- latest benchmark summary is optionally refreshed

## Current Regression Coverage

`tests/test_crossextend_kg_regressions.py` covers:

- loading persistent pipeline configs
- frozen backbone loading without dynamic expansion
- preprocessing config path and env resolution
- minimal backend field sufficiency
- legacy `host` field upgrade to `base_url`
- reference-template JSON validity
- absence of removed evaluation-era config fields

## Validation Commands

```bash
python -m py_compile $(rg --files crossextend_kg tests | rg '\.py$')
pytest -q tests/test_crossextend_kg_regressions.py
```

## Known Limitation

`aggregate_schema_candidates()` intentionally emits concept candidates only in the active main architecture.
