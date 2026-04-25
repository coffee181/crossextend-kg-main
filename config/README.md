# Config Guide

`config/` stores the active runtime configuration assets for the current
workflow-first O&M pipeline.

## Active Layout

- `prompts/`
  prompt templates used by preprocessing and attachment (v2: hypernym + phase + diagnostic extraction)
- `persistent/pipeline.base.yaml`
  stable pipeline skeleton (v2: 15-concept backbone)
- `persistent/pipeline.deepseek.yaml`
  recommended runtime preset
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

## Commands

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml --domains battery
```
