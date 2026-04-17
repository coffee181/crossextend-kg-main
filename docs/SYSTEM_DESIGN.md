# CrossExtend-KG System Design

**Updated**: 2026-04-17  
**Scope**: Main architecture only

## Core Rules

1. **Fixed backbone**. Runtime backbone comes from `backbone.seed_concepts` plus optional curated additions from `domains[].ontology_seed_path`.
2. **Uniform domains**. Every domain is an application case with `role="target"`. There is no privileged domain and no source-first path.
3. **No fallback**. Invalid configuration or backend failures should raise directly instead of silently degrading behavior.
4. **Explicit switches only**. Variants may disable retrieval, filtering, memory, or snapshots, but they still run the same core chain.
5. **Structure-first export**. The runtime exports graph artifacts and count-based construction summaries.

## Problem Framing

CrossExtend-KG treats industrial KG construction as constrained schema adaptation:

- the shared backbone captures stable pan-industrial concepts
- each domain contributes evidence and domain-specific candidates
- attachment decides whether a candidate reuses the backbone, specializes it under the backbone, or is rejected
- graph assembly materializes a domain graph with provenance and snapshots

## Runtime Phases

### Phase 0: Preprocessing

`preprocessing/` converts raw domain documents into `EvidenceRecord` JSON. The active preprocessing output contains:

- `concept_mentions`
- `relation_mentions`
- document metadata such as `evidence_id`, `domain_id`, `timestamp`, and `source_type`

Preprocessing no longer emits pseudo-gold or downstream-query fields as part of the runtime contract.

### Phase 1: Evidence Loading

`pipeline/evidence.py`:

- loads records from each configured domain
- normalizes evidence into `EvidenceUnit`
- aggregates concept-level `SchemaCandidate` objects by domain and label

### Phase 2: Backbone Build

`pipeline/backbone.py` builds the shared backbone once per run:

- all `seed_concepts` are always included
- `seed_descriptions` drive retrieval and prompt grounding
- curated shared concepts may be appended from `ontology_seed_path`

There is no dynamic backbone extraction in the active runtime.

### Phase 3: Retrieval and Historical Context

Two retrieval layers can guide attachment:

- `pipeline/router.py`: embedding-based anchor retrieval against backbone descriptions
- `pipeline/memory.py`: temporal memory-bank retrieval from previous runs

Memory retrieval is optional per variant, but the runtime-level memory-bank infrastructure stays the same.

### Phase 4: Attachment and Filtering

`pipeline/attachment.py` decides how each candidate attaches:

- `reuse_backbone`
- `vertical_specialize`
- `reject`

Supported attachment strategies:

- `llm`
- `embedding_top1`
- `deterministic`

`rules/filtering.py` enforces route legality and blocks structurally invalid decisions.

### Phase 5: Graph Assembly and Snapshots

`pipeline/graph.py`:

- materializes adapter concepts into per-domain schemas
- converts accepted relation mentions into graph edges
- creates `TemporalAssertion`, `SnapshotManifest`, and `SnapshotState` artifacts
- applies relation validation when enabled by runtime config

### Phase 6: Export

`pipeline/artifacts.py` exports:

- run-level backbone files
- per-domain working artifacts
- snapshot states
- graph DB / property graph exports
- `construction_summary.json`

The construction summary is structural and count-based. It reports sizes and acceptance counts rather than downstream metrics.

## Variant Model

Variants change switches on the same architecture rather than introducing different pipelines.

Important switches:

- `attachment_strategy`
- `use_embedding_routing`
- `use_rule_filter`
- `enable_memory_bank`
- `enable_snapshots`

The recommended main variant is `full_llm`.

## Artifact Shape

Each variant exports:

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
    ├── final_graph.json
    ├── snapshot_manifest.jsonl
    ├── snapshots/<snapshot_id>/
    │   ├── nodes.jsonl
    │   ├── edges.jsonl
    │   └── consistency.json
    └── exports/
```

## Active Architectural Gaps

- Candidate aggregation is currently concept-centric by design.
- Variant support remains in code, but the default entry points now emphasize the main architecture rather than experiments.
