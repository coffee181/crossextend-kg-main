# Persistent Configs

`config/persistent/` now keeps only the live presets required by the current
mainline.

## Files To Keep

- `pipeline.base.yaml`
- `pipeline.deepseek.yaml`
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json`

## Current Defaults

- `deepseek` resolves to `deepseek-reasoner`
- `dashscope_text_embedding_v4` is the default embedding backend

## Usage Pattern

Use the thin wrapper preset for normal runs:

```yaml
extends: ./pipeline.base.yaml
llm_backend_id: deepseek
embedding_backend_id: dashscope_text_embedding_v4
runtime:
  run_prefix: deepseek
```

Use CLI domain filters instead of adding special one-off config files.
