# Preprocessing Module

**Updated**: 2026-04-26

`preprocessing/` converts raw O&M markdown into step-aware `EvidenceRecord`
files for the main CrossExtend-KG pipeline.

## Current Scope

- Only `om_manual`
- Markdown table steps such as `T1`, `T2`, `T3`
- Three active domains: `battery`, `cnc`, `nev`
- No fallback extraction path

## Supported Raw Directory Layout

The active parser accepts the current corpus naming directly:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

It also accepts canonical domain folders such as `data/battery/`, `data/cnc/`,
and `data/nev/` when explicitly staged for experiments.

## v2 Extraction Output

Each document is represented as a step-aware record with v2 extensions:

```json
{
  "evidence_id": "BATOM_001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "om_manual",
  "timestamp": "2026-04-26T00:00:00Z",
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
          "semantic_type_hint": "Component",
          "shared_hypernym": "Connector"
        }
      ],
      "relation_mentions": [
        {
          "label": "observes",
          "family": "task_dependency",
          "head": "T1",
          "tail": "coolant outlet connector"
        }
      ],
      "step_phase": "observe",
      "step_summary": "Inspect coolant outlet connector",
      "surface_form": "Inspect coolant outlet connector for seepage evidence",
      "step_actions": [
        {"action_type": "observes", "target_label": "coolant outlet connector"}
      ],
      "structural_edges": [],
      "diagnostic_edges": [],
      "state_transitions": [],
      "sequence_next": "T2"
    }
  ],
  "document_concept_mentions": [],
  "document_relation_mentions": [],
  "procedure_meta": {
    "asset_name": "Pack",
    "procedure_type": "diagnosis",
    "primary_fault_type": "seepage"
  },
  "cross_step_relations": []
}
```

## v2 Prompt Features

The O&M extraction prompt now instructs the LLM to:

- Classify concepts into 10 hypernym categories (`shared_hypernym`)
- Extract `state_transitions` (lifecycle state changes)
- Extract `diagnostic_edges` (communication/propagation evidence)
- Follow step phase classification guidance (observe/diagnose/repair/verify)

## Post-Processing Inference

The processor infers v2 fields when LLM output does not provide them:

- `step_phase`: from verb patterns in `surface_form` (priority: verify > observe > diagnose > repair)
- `step_summary`: first sentence of `surface_form`, truncated to 72 chars
- `sequence_next`: from step row order
- `step_actions`: from `task_dependency` relations where head=step, tail=concept
- `structural_edges`: from `structural` family relations
- `diagnostic_edges`: from `communication`/`propagation` family relations
- `state_transitions`: from `lifecycle` family relations
- `procedure_meta`: from document title and content (asset name, procedure type, fault type)
- `cross_step_relations`: from document-level communication/propagation relations with step attribution

## Recommended Command

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
```
