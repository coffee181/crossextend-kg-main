# Pipeline Data Flow

This document describes the active end-to-end data flow of the cleaned
CrossExtend-KG mainline.

## Stage 1: Input Parsing

Input source:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

The parser reads O&M markdown files, validates the filename/content contract,
and converts them into `DocumentInput`.

## Stage 2: Preprocessing Extraction

The preprocessing prompt extracts:

- step-scoped concepts
- step-scoped relations
- optional document-level semantic concepts
- optional document-level semantic relations

The result is converted into `EvidenceRecord`, where each `step_record` carries
its own concepts and relations.

## Stage 3: Evidence Loading

The pipeline loads evidence records by domain and normalizes:

- labels
- semantic type hints
- document provenance

Only semantic candidates are aggregated for attachment. Workflow steps are
materialized directly later and do not go through semantic attachment.

## Stage 4: Backbone Routing And Attachment

The fixed backbone is currently:

- `Asset`
- `Component`
- `Task`
- `Signal`
- `State`
- `Fault`

`Task` is retained only for legacy evaluation projection. Runtime semantic
attachment is effectively centered on:

- `Asset`
- `Component`
- `Signal`
- `State`
- `Fault`

Each semantic candidate receives:

- embedding retrieval priors
- prompt priors
- attachment decision
- optional rule filtering

## Stage 5: Graph Assembly

The graph assembler builds a dual-layer graph:

- workflow nodes from `step_records`
- semantic nodes from admitted attachment decisions
- workflow sequence edges
- workflow grounding edges
- semantic structural / diagnostic edges

Accepted edges are exported into:

- `final_graph.json`
- GraphML

## Stage 6: Evaluation

Use the unified CLI entry:

```bash
python -m crossextend_kg.cli evaluate --gold <gold.json> --graph <final_graph.json>
```

or:

```bash
python -m crossextend_kg.cli evaluate --run-root <run_dir> --variant full_llm --ground-truth-dir <gold_dir>
```

## Main Runtime Commands

Preprocess:

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

Run:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```

Run selected domains only:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --domains battery cnc
```
