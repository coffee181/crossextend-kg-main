# CrossExtend-KG System Design

**Updated**: 2026-04-22  
**Scope**: Active architecture for O&M-form knowledge graph construction

## Core Rules

1. The backbone is fixed at runtime.
2. All active domains are treated uniformly as application cases with `role="target"`.
3. The active input source type is `om_manual`.
4. The main pipeline must fail explicitly when required stages break; no silent fallback path is allowed.
5. Runtime outputs are auditable graph-construction artifacts, not downstream product-analysis reports.
6. Preprocessing accepts only O&M-contract markdown; unsupported files must fail instead of being re-routed into legacy types.

## Problem Framing

CrossExtend-KG currently treats industrial KG construction as constrained schema adaptation over O&M forms:

- preprocessing converts raw markdown manuals into step-scoped `EvidenceRecord`
- a fixed backbone provides shared upper-level anchors
- only semantic candidates are attached under the backbone or rejected
- workflow steps are materialized directly as `workflow_step` nodes instead of semantic `Task` nodes
- accepted concepts and relations are assembled into a single dual-layer graph with provenance and optional temporal snapshots

The current paper-facing objective is:

- make `LLM extraction + backbone-guided attachment + rule-based refinement` reliable on O&M manuals
- preserve task sequence and step-to-object grounding in the final graph
- keep node admission auditable
- evaluate with human gold rather than auto-generated pseudo-gold

## Active Input Contract

The repository currently uses O&M markdown documents from:

- `data/battery_om_manual_en/`
- `data/cnc_om_manual_en/`
- `data/ev_om_manual_en/`

The parser supports filename-based O&M type inference and strips optional UTF-8 BOM markers before downstream extraction. If a markdown file does not match the active O&M filename or content contract, preprocessing stops with an explicit error.
