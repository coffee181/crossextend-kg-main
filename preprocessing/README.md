# Preprocessing Module

**Updated**: 2026-04-20

`preprocessing/` converts raw O&M markdown into step-aware `EvidenceRecord` files for the main CrossExtend-KG pipeline.

## Current Scope

- Only `om_manual`
- Markdown table steps such as `T1`, `T2`, `T3`
- Three active domains: `battery`, `cnc`, `nev`
- No fallback extraction path

## Supported Raw Directory Layout

The active parser now accepts the current corpus naming directly:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

It also still accepts canonical domain folders such as `data/battery/`, `data/cnc/`, and `data/nev/` when those are explicitly staged for experiments.

## Current Behavior

- infers `om_manual` from filenames like `BATOM_*`, `CNCOM_*`, `EVMAN_*`
- preserves markdown tables for step extraction
- uses the O&M-specific prompt
- emits a unified evidence bundle plus per-domain evidence files
- resolves YAML or JSON preprocessing configs through the shared config loader

## Recommended Command

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

## Current Output Shape

Each document is represented as a step-aware record:

```json
{
  "evidence_id": "BATOM_001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "om_manual",
  "timestamp": "2026-04-20T00:00:00Z",
  "raw_text": "...",
  "step_records": [
    {
      "step_id": "T1",
      "task": {
        "label": "T1",
        "surface_form": "Inspect coolant outlet connector"
      },
      "concept_mentions": [
        {
          "label": "coolant outlet connector",
          "node_worthy": true,
          "semantic_type_hint": "Component"
        }
      ],
      "relation_mentions": [
        {
          "label": "observes",
          "family": "task_dependency",
          "head": "T1",
          "tail": "coolant outlet connector"
        }
      ]
    }
  ],
  "document_concept_mentions": [],
  "document_relation_mentions": []
}
```
