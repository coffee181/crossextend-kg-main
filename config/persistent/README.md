# Persistent Configs

`crossextend_kg/config/persistent/` contains the presets intended for daily editing and execution.

## Files

```text
persistent/
├── embedding_backends.json
├── llm_backends.json
├── preprocessing.deepseek.json
├── preprocessing.deepseek_full.json
├── pipeline.default.json
├── pipeline.deepseek.json
├── pipeline.deepseek_full.json
├── pipeline.local_ollama.json
├── pipeline.openai.json
├── pipeline.real_data.json
└── relation_constraints.json
```

## Which Preset To Use

| Preset | Purpose |
|--------|---------|
| `pipeline.deepseek.json` | Recommended main run with `full_llm` |
| `pipeline.deepseek_full.json` | Multi-variant stress run on the same architecture |
| `preprocessing.deepseek.json` | Recommended preprocessing preset |
| `preprocessing.deepseek_full.json` | Multi-domain preprocessing preset |
| `pipeline.local_ollama.json` | Local hosted chat + embedding endpoints |
| `pipeline.openai.json` | Hosted OpenAI-compatible run |
| `pipeline.default.json` | Generic starting point you can copy and edit |
| `pipeline.real_data.json` | Real-data preset skeleton |

## What You Usually Edit

1. `llm.base_url`, `llm.api_key`, `llm.model`
2. `embedding.base_url`, `embedding.api_key`, `embedding.model`
3. `domains[].data_path` and `domains[].source_types`
4. `runtime.artifact_root` or `runtime.run_prefix`
5. `variants` if you want to disable memory, routing, or filtering

The backbone is fixed by:

- `backbone.seed_concepts`
- `backbone.seed_descriptions`
- optional `domains[].ontology_seed_path`

## Quick Run

```bash
python -m crossextend_kg.cli run \
  --config crossextend_kg/config/persistent/pipeline.deepseek.json
```
