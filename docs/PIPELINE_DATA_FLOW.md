# Pipeline Data Flow

This document describes the active end-to-end data flow of the
CrossExtend-KG v2 mainline.

## Stage 1: Input Parsing

Input source:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

The parser reads O&M markdown files, validates the filename/content contract,
and converts them into `DocumentInput`.

## Stage 2: Preprocessing Extraction

The preprocessing prompt extracts:

- step-scoped concepts (with optional `shared_hypernym`)
- step-scoped relations
- optional document-level semantic concepts
- optional document-level semantic relations
- optional `state_transitions` (lifecycle state changes)
- optional `diagnostic_edges` (communication/propagation evidence)

The result is converted into `EvidenceRecord`, where each `step_record` carries:

**v1 fields (preserved for backward compatibility)**:
- `task`: step concept mention with `label` and `surface_form`
- `concept_mentions[]`: concepts mentioned in this step
- `relation_mentions[]`: all relations involving this step

**v2 fields (optional, with defaults)**:
- `step_phase`: observe / diagnose / repair / verify (inferred from surface_form verbs)
- `step_summary`: first-sentence summary of the step
- `surface_form`: full step text (independent from `task.surface_form`)
- `step_actions[]`: clean `StepAction` records extracted from task_dependency relations
- `structural_edges[]`: separated structural containment edges
- `diagnostic_edges[]`: communication/propagation edges from this step
- `state_transitions[]`: lifecycle state changes observed in this step
- `sequence_next`: next step ID (replaces synthetic triggers relation)

At the document level:
- `procedure_meta`: inferred asset name, procedure type, and primary fault type
- `cross_step_relations[]`: document-level communication/propagation relations with step attribution

## Stage 3: Evidence Loading

The pipeline loads evidence records by domain and normalizes:

- labels (including v2 field labels: step_actions, structural_edges, diagnostic_edges, state_transitions, cross_step_relations)
- semantic type hints
- shared_hypernym (propagated to `routing_features`)
- document provenance

Only semantic candidates are aggregated for attachment. Workflow steps are
materialized directly later and do not go through semantic attachment.

## Stage 4: Backbone Routing And Attachment

The fixed backbone is 15 concepts:

**Tier 0**: `Asset`, `Component`, `Signal`, `State`, `Fault`

**Tier 1**: `Seal`, `Connector`, `Sensor`, `Controller`, `Coolant`, `Actuator`, `Power`, `Housing`, `Fastener`, `Media`

Each semantic candidate receives:

- embedding retrieval priors
- prompt priors
- attachment decision (route + parent_anchor)
- optional rule filtering

The `shared_hypernym` from `routing_features` serves as anchor fallback:
if `semantic_type_hint` is absent but `shared_hypernym` is present, the
candidate routes to the matching Tier-1 backbone concept.

## Stage 5: Graph Assembly

The graph assembler builds a dual-layer graph with v2 field consumption:

**Workflow layer**:
- workflow nodes from `step_records` (with `step_phase` propagated to `GraphNode`)
- workflow sequence edges (prefers `sequence_next`, falls back to triggers relations)
- workflow grounding edges (prefers `step_actions`, falls back to task_dependency relations)

**Semantic layer**:
- semantic nodes from admitted attachment decisions (with `shared_hypernym` propagated to `GraphNode`)
- semantic structural edges (prefers `structural_edges`, falls back to structural relations)
- semantic diagnostic edges (from communication/propagation relations)
- cross-step diagnostic relations (from `cross_step_relations`)

**Display logic**:
- `step_summary` / `surface_form` preferred for `display_label`; falls back to `task.surface_form`
- `step_phase` used for canonical action derivation (observe->inspect, diagnose->analyze, repair->repair, verify->verify)

Accepted edges are exported into:

- `final_graph.json` (with v2 summary: `hypernym_coverage`, `phase_distribution`)
- GraphML (with `shared_hypernym` and `step_phase` node attributes)

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
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
```

Run:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml
```

Run selected domains only:

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml --domains battery cnc
```
