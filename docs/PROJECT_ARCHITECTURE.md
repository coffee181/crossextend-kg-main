# CrossExtend-KG Project Architecture

**Updated**: 2026-04-17  
**Status**: Active runtime architecture

## Overview

CrossExtend-KG now keeps only the main construction architecture:

- fixed backbone from `backbone.seed_concepts`
- optional curated shared concepts from `domains[].ontology_seed_path`
- uniform domain handling with `role="target"`
- attachment, filtering, graph assembly, snapshots, and artifact export

Evaluation-only packages and downstream-task utilities are no longer part of the active tree.

## Repository Layout

```text
Auto-claude-code-research-in-sleep/
├── pyproject.toml
├── crossextend_kg/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── io.py
│   ├── exceptions.py
│   ├── logging_config.py
│   ├── validation.py
│   ├── README.md
│   ├── README_CN.md
│   ├── backends/
│   │   ├── embeddings.py
│   │   └── llm.py
│   ├── config/
│   │   ├── README.md
│   │   ├── persistent/
│   │   ├── prompts/
│   │   └── templates/
│   ├── docs/
│   │   ├── README.md
│   │   ├── SYSTEM_DESIGN.md
│   │   ├── PIPELINE_INTEGRATION.md
│   │   └── PROJECT_ARCHITECTURE.md
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── evidence.py
│   │   ├── backbone.py
│   │   ├── router.py
│   │   ├── attachment.py
│   │   ├── memory.py
│   │   ├── graph.py
│   │   ├── relation_validation.py
│   │   ├── artifacts.py
│   │   └── utils.py
│   ├── preprocessing/
│   ├── rules/
│   │   ├── __init__.py
│   │   └── filtering.py
│   ├── scripts/
│   │   └── visualize_propagation.py
│   ├── data/
│   └── artifacts/
└── tests/
    └── test_crossextend_kg_regressions.py
```

## Runtime Chain

1. `preprocessing/` converts raw documents into `EvidenceRecord` JSON.
2. `pipeline/evidence.py` loads records and aggregates concept-level `SchemaCandidate`s per domain.
3. `pipeline/backbone.py` builds the frozen shared backbone from seed concepts plus curated supplements.
4. `pipeline/router.py` retrieves candidate-to-backbone anchors with embeddings.
5. `pipeline/memory.py` retrieves historical context from the temporal memory bank.
6. `pipeline/attachment.py` produces attachment decisions for each variant.
7. `rules/filtering.py` validates or rejects illegal routing decisions.
8. `pipeline/graph.py` materializes domain schemas, triples, edges, and snapshot artifacts.
9. `pipeline/artifacts.py` exports auditable per-variant outputs and structure summaries.

## Key Interfaces

### Configuration

- `config.py`
- `PipelineConfig`, `VariantConfig`, `DomainConfig`
- active prompt fields: `attachment_judge_template_path`, `synthetic_generator_template_path`

### Backbone

- `pipeline/backbone.py`
- `build_backbone(config) -> (backbone_concepts, backbone_descriptions, curated_backbone_concepts)`

### Variants

Variants remain as switch packs on the same chain. Typical variant ids are:

- `full_llm`
- `no_memory_bank`
- `no_embedding_routing`
- `no_rule_filter`
- `embedding_only`
- `deterministic_baseline`

## Artifact Layout

Each variant exports to:

```text
<artifact_root>/<run_prefix>-<timestamp>/<variant_id>/
├── run_meta.json
├── backbone_seed.json
├── backbone_final.json
├── backbone.json
├── construction_summary.json
├── temporal_memory_entries.jsonl
└── working/<domain_id>/
    ├── evidence_units.jsonl
    ├── schema_candidates.jsonl
    ├── adapter_schema.json
    ├── adapter_candidates.json
    ├── attachment_decisions.json
    ├── retrievals.json
    ├── historical_context.json
    ├── graph_nodes.jsonl
    ├── graph_edges.jsonl
    ├── candidate_triples.jsonl
    ├── relation_edges.*.json
    ├── final_graph.json
    ├── temporal_assertions.jsonl
    ├── snapshot_manifest.jsonl
    ├── snapshots/<snapshot_id>/
    │   ├── nodes.jsonl
    │   ├── edges.jsonl
    │   └── consistency.json
    └── exports/
```

## Current Regression Coverage

`tests/test_crossextend_kg_regressions.py` checks:

- persistent pipeline configs still load
- predefined backbone loading remains fixed
- preprocessing config path/env expansion works
- minimal backend config fields remain sufficient
- legacy `host` aliases still upgrade to `base_url`
- removed evaluation-era fields do not reappear in configs
- the reference config template stays valid JSON
