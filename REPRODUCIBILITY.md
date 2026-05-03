# Reproducibility Guide

## Prerequisites

1. Python 3.10 or later
2. API keys for DeepSeek (LLM) and Tongyi/DashScope (embeddings)

## Setup

```bash
pip install -e .
```

## Configuring API Keys

Set these environment variables (or add them to `.env`):
- `DEEPSEEK_API_KEY` — for LLM calls (attachment decisions)
- `TONGYI_API_KEY` — for embedding calls (concept routing)

## Preprocessing Pipeline

Generate evidence records from raw O&M markdown documents:

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
```

This reads markdown from `data/{domain}_om_manual_en/` and writes evidence records to
`data/evidence_records/evidence_records_llm.json`.

To limit the number of documents per domain for testing:

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml --max-docs 5
```

## Knowledge Graph Construction Pipeline

Run the full pipeline on 9-document test set:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml
```

Run on a single domain:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.test3.yaml --domains battery
```

Run the full-scale experiment (400 documents):

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.full.yaml
```

## Evaluation

Evaluate a single graph:

```bash
python -m crossextend_kg.cli evaluate --gold data/ground_truth/battery_BATOM_002.json --graph artifacts/some_run/full_llm/working/battery/final_graph.json
```

Evaluate a full run against all gold files:

```bash
python -m crossextend_kg.cli evaluate --run-root results/test3/<run_id> --variant full_llm --ground-truth-dir data/ground_truth
```

## Regression Tests

Rule-based deterministic tests (no LLM/API needed):

```bash
python -m scripts.regression_test1   # Single document (battery BusbarShield)
python -m scripts.regression_test2   # Three documents (1 per domain)
python -m scripts.regression_test3   # Nine documents (3 per domain)
```

## Unit Tests

```bash
python -m pytest tests/ -v
```

## Expected Results

### Regression Test 3 (9 documents, rule-based attachment)

| Domain | Nodes | Edges | Accepted Triples |
|--------|-------|-------|-----------------|
| battery | 132 | 206 | 110 |
| cnc | 160 | 275 | 156 |
| nev | 173 | 314 | 181 |
| **Total** | **465** | **795** | **447** |

### Attachment Acceptance

- Acceptance rate: 348/349 (99.7%)
- Cross-domain hypernym consistency: 117/118 (99.2%)

## Configuration Reference

Key config files under `config/persistent/`:

| File | Purpose |
|------|---------|
| `pipeline.base.yaml` | Base pipeline config inherited by all variants |
| `pipeline.test3.yaml` | 9-document test config |
| `pipeline.full.yaml` | Full-scale (400-document) config |
| `pipeline.deepseek.yaml` | DeepSeek-specific LLM config |
| `preprocessing.base.yaml` | Base preprocessing config |
| `preprocessing.deepseek.yaml` | DeepSeek-specific preprocessing config |
| `llm_backends.yaml` | LLM backend registry |
| `embedding_backends.yaml` | Embedding backend registry |
| `relation_constraints.json` | Relation type constraints |

## Artifact Directory Structure

```
results/
  test3/<run_id>/full_llm/
    working/<domain>/
      attachment_audit.json    # Attachment decisions per concept
      final_graph.json         # Final domain graph
      final_graph.graphml      # GraphML export
    snapshots/<domain>/
      <snapshot_id>/           # Snapshot states
```

## Troubleshooting

### Missing data paths
Run preprocessing first: `python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml`

### LLM parse failures
Check raw responses in the debug log directory.
Increase `llm.max_tokens` or simplify the prompt template.

### Embedding API errors
The embedding backend retries on HTTP 429/500/502/503/504 errors.
Ensure `TONGYI_API_KEY` is set correctly.
