# Config Guide

`crossextend_kg/config/` stores the active runtime configuration assets for CrossExtend-KG.

## Reference Docs

- Schema reference: `templates/pipeline.config.reference.json`
- System design: `../docs/SYSTEM_DESIGN.md`
- Integration checkpoints: `../docs/PIPELINE_INTEGRATION.md`

## Layout

```text
config/
├── README.md
├── persistent/
│   ├── README.md
│   ├── embedding_backends.json
│   ├── llm_backends.json
│   ├── preprocessing.deepseek.json
│   ├── preprocessing.deepseek_full.json
│   ├── pipeline.default.json
│   ├── pipeline.deepseek.json
│   ├── pipeline.deepseek_full.json
│   ├── pipeline.local_ollama.json
│   ├── pipeline.openai.json
│   ├── pipeline.real_data.json
│   └── relation_constraints.json
├── prompts/
│   ├── attachment_judge.txt
│   ├── preprocessing_extraction.txt
│   ├── synthetic_generator.txt
│   └── synthetic_generator_english.txt
└── templates/
    └── pipeline.config.reference.json
```

## Recommended Entry Points

| Purpose | Config Path | Notes |
|---------|-------------|-------|
| Recommended main run | `persistent/pipeline.deepseek.json` | `full_llm` only |
| Multi-variant stress run | `persistent/pipeline.deepseek_full.json` | architecture switches on the same chain |
| Recommended preprocessing | `persistent/preprocessing.deepseek.json` | LLM extraction for `EvidenceRecord` generation |
| Local-only backend | `persistent/pipeline.local_ollama.json` | local OpenAI-compatible endpoints |
| OpenAI backend | `persistent/pipeline.openai.json` | hosted API |
| Custom starting point | `persistent/pipeline.default.json` | edit backends, variants, and domains |

## Top-Level Schema

| Field | Description |
|-------|-------------|
| `project_name` | Project identifier |
| `benchmark_name` | Run label |
| `prompts` | Prompt template paths |
| `llm` | LLM backend configuration |
| `embedding` | Embedding backend configuration |
| `backbone` | Fixed shared backbone definition |
| `relations` | Relation families and concept-attachment routes |
| `data` | Synthetic generation and normalization settings |
| `runtime` | Retrieval, memory-bank, validation, and export settings |
| `variants` | Variant list to execute |
| `domains` | Per-domain data sources and keywords |

## Backend Config

### `llm`

| Field | Notes |
|-------|-------|
| `base_url` | OpenAI-compatible chat endpoint root |
| `api_key` | API key, can come from env vars |
| `model` | Chat model id |
| `timeout_sec` | Request timeout |
| `max_tokens` | Response token cap |
| `temperature` | Sampling temperature |

### `embedding`

| Field | Notes |
|-------|-------|
| `base_url` | OpenAI-compatible embedding endpoint root |
| `api_key` | Optional API key |
| `model` | Embedding model id |
| `timeout_sec` | Request timeout |
| `dimensions` | Explicit embedding dimension when supported |

## Backbone Config

The runtime backbone is fixed. It is built from:

- `backbone.seed_concepts`
- `backbone.seed_descriptions`
- optional curated additions from `domains[].ontology_seed_path`

There is no dynamic backbone extraction path in the active runtime.
Candidate schema may only:

- reuse an exact backbone label
- vertically specialize under a backbone concept
- be rejected

## Runtime Config

| Field | Description |
|-------|-------------|
| `artifact_root` | Root directory for run outputs |
| `retrieval_top_k` | Number of retrieved anchors per candidate |
| `llm_attachment_batch_size` | LLM attachment batch size |
| `enable_temporal_memory_bank` | Enable persistent memory retrieval |
| `temporal_memory_top_k` | Historical hits per candidate |
| `temporal_memory_max_entries` | Memory-bank entry cap |
| `temporal_memory_path` | Optional persistent memory-bank path |
| `save_latest_summary` | Refresh `latest_summary.json` |
| `write_jsonl_artifacts` | Write JSONL working artifacts |
| `write_graph_db_csv` | Write graph import CSVs |
| `write_property_graph_jsonl` | Write property-graph JSONL exports |
| `run_prefix` | Prefix used for run directory naming |
| `relation_constraints_path` | Optional relation validation config |
| `enable_relation_validation` | Validate relation candidates during graph assembly |

## Variant Config

Supported `VariantConfig` fields:

| Field | Description |
|-------|-------------|
| `variant_id` | Unique variant id |
| `description` | Human-readable description |
| `attachment_strategy` | `llm`, `embedding_top1`, or `deterministic` |
| `use_embedding_routing` | Enable embedding-based anchor retrieval |
| `use_rule_filter` | Enable rule validation |
| `allow_free_form_growth` | Allow unconstrained schema growth |
| `enable_snapshots` | Export snapshot states |
| `enable_memory_bank` | Enable per-variant temporal memory retrieval |
| `export_artifacts` | Export artifacts to disk |

`pipeline.deepseek.json`, `pipeline.local_ollama.json`, and `pipeline.openai.json` keep only `full_llm`. The larger presets keep a few switch-based variants for architecture stress testing.

## Domain Config

| Field | Description |
|-------|-------------|
| `domain_id` | Unique domain id |
| `domain_name` | Display name |
| `role` | Must be `target` |
| `data_path` | EvidenceRecord JSON file |
| `ontology_seed_path` | Optional curated shared-concept JSON |
| `source_types` | Included evidence source types |
| `domain_keywords` | Domain-specific keywords |

All domains are treated uniformly. There is no privileged source domain.

## Environment Variables

Config files support `${VAR}` and `${VAR:-default}` expansion.

Example:

```json
{
  "base_url": "${CROSSEXTEND_OPENAI_BASE_URL:-https://api.openai.com/v1}",
  "api_key": "${CROSSEXTEND_OPENAI_API_KEY:-}",
  "model": "${CROSSEXTEND_OPENAI_MODEL:-gpt-4o}"
}
```

## Validation Rules

The loader rejects:

- missing `llm.base_url` or `llm.model`
- missing `embedding.base_url` or `embedding.model`
- duplicate `domain_id`
- duplicate `variant_id`
- missing `seed_descriptions` for any seed concept
- non-`target` domain roles

## Regression Check

```bash
pytest -q tests/test_crossextend_kg_regressions.py
```
