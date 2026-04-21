# Config Guide

**Updated**: 2026-04-20

`config/` stores the active runtime configuration assets for the current O&M-form pipeline.

## Active Layout

- `prompts/`
  Prompt templates used by preprocessing and attachment.
- `persistent/pipeline.base.yaml`
  Stable pipeline skeleton.
- `persistent/preprocessing.base.yaml`
  Stable preprocessing skeleton.
- `persistent/llm_backends.yaml`
  LLM backend registry.
- `persistent/embedding_backends.yaml`
  Embedding backend registry.
- `persistent/*.yaml`
  Thin human-edited wrappers for concrete runs.

## Why YAML Now

- The old persistent JSON presets duplicated backbone, relations, domains, and runtime blocks.
- The new layout keeps those stable parts in base configs.
- Backend switching now happens by `llm_backend_id` and `embedding_backend_id` instead of cloning full configs.
- JSON is still supported for generated experiment configs and backward-compatible tests.

## Key Loader Features

- `.json`, `.yaml`, `.yml`
- `extends`
- environment variable expansion like `${DEEPSEEK_API_KEY}`
- backend registry injection
- path resolution relative to the config file itself

## Recommended Presets

- `persistent/preprocessing.deepseek.yaml`
  Recommended O&M preprocessing preset.
- `persistent/pipeline.deepseek.yaml`
  Recommended main run.
- `persistent/pipeline.deepseek.battery_only.yaml`
  Focused battery-only debugging preset.
- `persistent/pipeline.deepseek_full.yaml`
  Optional multi-variant stress preset.

## What Usually Changes

Most daily changes should stay in thin wrappers:

- `llm_backend_id`
- `embedding_backend_id`
- `runtime.run_prefix`
- `runtime.artifact_root`
- `benchmark_name`

Base files should only change when the mainline architecture itself changes.

## Commands

Preprocess:

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

Main run:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```
