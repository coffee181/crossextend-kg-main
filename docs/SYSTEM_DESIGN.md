# CrossExtend-KG System Design

**Updated**: 2026-04-26
**Scope**: Active architecture for O&M-form knowledge graph construction (v2)

## Core Rules

1. The backbone is fixed at runtime (15 concepts: 5 base + 10 Tier-1 hypernyms).
2. All active domains are treated uniformly as application cases with `role="target"`.
3. The active input source type is `om_manual`.
4. The main pipeline must fail explicitly when required stages break; no silent fallback path is allowed.
5. Runtime outputs are auditable graph-construction artifacts, not downstream product-analysis reports.
6. Preprocessing accepts only O&M-contract markdown; unsupported files must fail instead of being re-routed into legacy types.
7. v2 fields on data models are optional with defaults; v1 evidence records load without error and produce empty v2 fields.

## Problem Framing

CrossExtend-KG treats industrial KG construction as constrained schema adaptation over O&M forms:

- preprocessing converts raw markdown manuals into step-scoped `EvidenceRecord`
- a fixed backbone provides shared upper-level anchors (5 base + 10 Tier-1 hypernyms)
- only semantic candidates are attached under the backbone or rejected
- workflow steps are materialized directly as `workflow_step` nodes instead of semantic `Task` nodes
- accepted concepts and relations are assembled into a single dual-layer graph with provenance and optional temporal snapshots

The v2 restructuring adds three structural capabilities:

1. **Cross-domain generalization**: `shared_hypernym` on `ConceptMention` enables consistent cross-domain concept mapping through 10 Tier-1 categories (Seal, Connector, Sensor, Controller, Coolant, Actuator, Power, Housing, Fastener, Media).
2. **Temporal backtracking**: `step_phase` on `StepEvidenceRecord` classifies each step as observe/diagnose/repair/verify; `state_transitions` capture lifecycle state changes; `procedure_meta` captures document-level procedure metadata.
3. **Complex propagation paths**: `diagnostic_edges` separate communication/propagation evidence from task dependencies; `cross_step_relations` link concepts across steps for inter-step diagnostic reasoning.

## Active Input Contract

The repository currently uses O&M markdown documents from:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

The parser supports filename-based O&M type inference and strips optional UTF-8 BOM markers before downstream extraction. If a markdown file does not match the active O&M filename or content contract, preprocessing stops with an explicit error.

## v2 Data Model Extensions

### New Models

| Model | Fields | Purpose |
|-------|--------|---------|
| `StepAction` | `action_type`, `target_label` | Clean step-to-object action record |
| `StructuralEdge` | `label`, `family`, `head`, `tail` | Separated structural containment |
| `StateTransition` | `from_state`, `to_state`, `trigger_step`, `evidence_label` | Lifecycle state changes |
| `DiagnosticEdge` | `evidence_label`, `indicated_label`, `mechanism` | Communication/propagation evidence |
| `ProcedureMeta` | `asset_name`, `procedure_type`, `primary_fault_type` | Document-level procedure metadata |
| `CrossStepRelation` | `label`, `family`, `head`, `tail`, `head_step`, `tail_step` | Inter-step diagnostic reasoning |

### Extended Models

| Model | New Fields | Default | Purpose |
|-------|-----------|---------|---------|
| `ConceptMention` | `shared_hypernym` | `None` | Cross-domain hypernym classification |
| `StepEvidenceRecord` | `step_phase`, `step_summary`, `surface_form`, `step_actions[]`, `structural_edges[]`, `state_transitions[]`, `diagnostic_edges[]`, `sequence_next` | empty/None | v2 step metadata |
| `EvidenceRecord` | `procedure_meta`, `cross_step_relations[]` | `None`/empty | Document-level metadata and cross-step relations |
| `GraphNode` | `shared_hypernym`, `step_phase` | `None` | v2 attributes propagated to graph |

## Backbone Architecture

The fixed backbone now has 15 concepts in two tiers:

**Tier 0 (base semantic types)**:
- `Asset`, `Component`, `Signal`, `State`, `Fault`

**Tier 1 (cross-domain hypernym anchors)**:
- `Seal`, `Connector`, `Sensor`, `Controller`, `Coolant`
- `Actuator`, `Power`, `Housing`, `Fastener`, `Media`

`Task` has been removed from the backbone. Workflow steps remain `workflow_step` nodes in the graph and are projected as `Task` only during evaluation for legacy gold compatibility.

## Attachment Routing

With the expanded backbone, attachment routing now supports:

1. `reuse_backbone`: candidate label matches a backbone concept directly
2. `vertical_specialize`: candidate attaches under a backbone concept via `semantic_type_hint` or `shared_hypernym`
3. `reject`: candidate cannot be anchored to any backbone concept

The `shared_hypernym` field serves as a fallback anchor when `semantic_type_hint` is absent: a concept with `shared_hypernym="Seal"` routes to the backbone concept `Seal`.

## Regression Experiment Summary (2026-04-26)

Rule-based regression tests validated the v2 pipeline:

| Test | Docs | battery (nodes/edges) | cnc (nodes/edges) | nev (nodes/edges) |
|------|------|----------------------|--------------------|-------------------|
| 1 (single-doc) | 1 | 59/69 | — | — |
| 2 (three-domain) | 3 | 48/57 | 68/90 | 73/115 |
| 3 (nine-doc) | 9 | 132/206 | 160/275 | 173/314 |

9-doc ablation (Embedding + LLM variants):

| Variant | Nodes | Edges | Acc Triples |
|---------|-------|-------|-------------|
| baseline_embedding_llm | 454 | 754 | 417 |
| contextual_rerank_embedding_llm | 461 | 776 | 432 |
| pure_llm | 459 | 772 | 430 |

9 attachment gold files (359 concepts) completed.
See `README.md` for full experimental results.
