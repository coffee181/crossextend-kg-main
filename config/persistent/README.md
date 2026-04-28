# Persistent Configs

`config/persistent/` keeps the live presets required by the current mainline.

## Files To Keep

- `pipeline.base.yaml` -- v2: 15-concept backbone (5 base + 10 Tier-1 hypernyms)
- `pipeline.deepseek.yaml` -- deepseek runtime preset
- `preprocessing.base.yaml` -- stable preprocessing skeleton
- `preprocessing.deepseek.yaml` -- deepseek preprocessing preset
- `llm_backends.yaml` -- LLM backend registry
- `embedding_backends.yaml` -- embedding backend registry
- `relation_constraints.json` -- v2: includes Tier-1 hypernyms in allowed types

## Current Defaults

- `deepseek` resolves to `deepseek-v4-flash`
- `dashscope_text_embedding_v4` is the default embedding backend

## v2 Config Changes

- `pipeline.base.yaml`: backbone `seed_concepts` expanded from 6 to 15; `Task` removed; 10 Tier-1 hypernyms added with descriptions
- `relation_constraints.json`: all 10 Tier-1 hypernyms added to `task_dependency.allowed_head_types` and `allowed_tail_types`
- `preprocessing_extraction_om.txt`: added hypernym classification table, step phase guidance, state_transition and diagnostic_edge extraction rules

## Usage Pattern

Use the thin wrapper preset for normal runs:

```yaml
extends: ./pipeline.base.yaml
llm_backend_id: deepseek
embedding_backend_id: dashscope_text_embedding_v4
runtime:
  run_prefix: deepseek
```

## Switching Models

To replace the current external LLM globally, edit
`llm_backends.yaml -> backends.deepseek.model`.

To keep multiple model options, add another backend entry in
`llm_backends.yaml` and point the preset's `llm_backend_id` at that backend.

Changing `default_backend` alone does not override presets that already specify
`llm_backend_id`.

Use CLI domain filters instead of adding special one-off config files.
