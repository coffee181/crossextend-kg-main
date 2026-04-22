# Persistent Configs

**Updated**: 2026-04-20

`config/persistent/` now uses a layered YAML layout for human-maintained runtime presets.

## Design

- Keep stable pipeline structure in shared base files.
- Keep model switching in backend registries.
- Keep daily run presets as thin wrappers that mainly choose backend ids and a small number of runtime overrides.
- Keep generated experiment configs as materialized JSON when needed.

## Recommended Files

- `pipeline.base.yaml`
  Fixed backbone, relations, runtime defaults, and three-domain dataset wiring.
- `pipeline.deepseek.yaml`
  Recommended main preset.
- `pipeline.deepseek.battery_only.yaml`
  Battery-only wrapper for focused debugging.
- `pipeline.deepseek_full.yaml`
  Optional multi-variant stress preset.
- `preprocessing.base.yaml`
  Shared preprocessing defaults.
- `preprocessing.deepseek.yaml`
  Recommended preprocessing preset.
- `llm_backends.yaml`
  LLM backend registry.
- `embedding_backends.yaml`
  Embedding backend registry.

## Current LLM Default

- `deepseek` now points to `deepseek-reasoner`.
- `deepseek_chat` is kept as the explicit legacy chat-model entry.
- Existing presets such as `pipeline.deepseek.yaml` and `preprocessing.deepseek.yaml`
  will therefore use `deepseek-reasoner` by default.

## How To Switch Models

Edit only the thin wrapper in most cases:

```yaml
extends: ./pipeline.base.yaml
llm_backend_id: deepseek
embedding_backend_id: dashscope_text_embedding_v4
runtime:
  run_prefix: deepseek
```

To switch to another LLM or embedding model, change the backend id instead of copying the whole pipeline config.

Current embedding default:

- `dashscope_text_embedding_v4`
- base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- API key source: `${TONGYI_API_KEY}`
- model: `text-embedding-v4`

## Loader Features

- Supports `.yaml`, `.yml`, and `.json`
- Supports `extends`
- Supports `llm_backend_id`
- Supports `embedding_backend_id`
- Keeps JSON backward compatibility for generated configs and tests

## Quick Run

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```
