# Config Guide

`config/` stores the active runtime configuration assets for the current
workflow-first O&M pipeline.

## Active Layout

- `prompts/`
  prompt templates used by preprocessing and attachment (v2: hypernym + phase + diagnostic extraction)
- `persistent/pipeline.base.yaml`
  stable pipeline skeleton (v2: 15-concept backbone)
- `persistent/pipeline.test3.yaml`
  default reproducible Test3 run using checked-in evidence records
- `persistent/pipeline.deepseek.yaml`
  DeepSeek-oriented preset; requires generated evidence record files
- `persistent/preprocessing.base.yaml`
  stable preprocessing skeleton
- `persistent/preprocessing.deepseek.yaml`
  recommended preprocessing preset
- `persistent/llm_backends.yaml`
  LLM backend registry
- `persistent/embedding_backends.yaml`
  embedding backend registry
- `persistent/relation_constraints.json`
  semantic type constraints used by relation validation (v2: Tier-1 hypernyms included)

## Design Rules

- keep stable structure in base configs
- keep model switching in backend registries
- avoid cloning whole configs for one-off runs
- use CLI domain filters instead of domain-specific preset files

## Switching LLM Models

Both `preprocess` and `run` resolve their LLM settings from
`config/persistent/llm_backends.yaml`. Changing the external model should be a
config-only operation.

Replace the currently used model globally by editing the backend entry that
existing presets point to:

```yaml
backends:
  deepseek:
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}
    model: deepseek-v4-pro
```

The current presets already use `llm_backend_id: deepseek`, so changing
`backends.deepseek.model` switches both preprocessing and pipeline runs.

Keep multiple models side by side by adding another backend entry and changing
the preset's `llm_backend_id`:

```yaml
backends:
  deepseek:
    model: deepseek-v4-pro
  deepseek_r1:
    model: deepseek-r1
```

```yaml
llm_backend_id: deepseek_r1
```

Changing `default_backend` alone does not affect presets that already set
`llm_backend_id`.

## Commands

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml --domains battery
```
