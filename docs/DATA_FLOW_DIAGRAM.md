# CrossExtend-KG v2: Complete Data Flow Diagram

This document traces a **real single-document example** through every pipeline stage,
showing the exact input/output data format at each step. The example document is
`Battery_Module_Busbar_Insulator_Shield_Inspection.md` from the battery domain.

---

## Overview: Pipeline Stages

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Stage 0    │────▶│  Stage 1         │────▶│  Stage 2        │
│  Source Text │     │  Preprocessing   │     │  Evidence Load  │
│  (.md)       │     │  (LLM API)       │     │  & Normalize    │
└─────────────┘     └──────────────────┘     └─────────────────┘
                                                     │
┌─────────────┐     ┌──────────────────┐     ┌───────▼─────────┐
│  Stage 5    │◀────│  Stage 4         │◀────│  Stage 3        │
│  Export      │     │  Graph Assembly  │     │  Attachment     │
│  (JSON/ML)  │     │  (Dual-Layer)    │     │  (Embed+LLM)    │
└─────────────┘     └──────────────────┘     └─────────────────┘
```

| Stage | Input | Output | External API |
|-------|-------|--------|-------------|
| 0 | Raw O&M manual | Markdown table | None |
| 1 | Markdown text | EvidenceRecord (v2 JSON) | DeepSeek LLM |
| 2 | EvidenceRecord | SchemaCandidate[] | None |
| 3 | SchemaCandidate[] + Backbone | AttachmentDecision[] | DashScope Embedding + DeepSeek LLM |
| 4 | AttachmentDecision[] + EvidenceRecord | Dual-layer Graph | None |
| 5 | Graph | final_graph.json + .graphml | None |

---

## Stage 0: Source Text

**File**: `data/battery_om_manual_en/Battery_Module_Busbar_Insulator_Shield_Inspection.md`

**Format**: A Markdown table with two columns (`Time step` and `O&M sample text`),
containing 7 operational steps (T1–T7).

**Input content** (verbatim):

```markdown
| Time step | O&M sample text |
|---|---|
| T1 | For Velorian ModuleShield-584, record whether the busbar-insulator review follows an electrical event, dropped-tool incident, or routine service access, and identify the exact module section carrying the suspect shield. Photograph the shield edge and the exposed busbar geometry before anything is shifted. |
| T2 | Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam barriers, and cover ribs without moving the shield from its as-found seat. The shield edge and the underlying busbar have to be judged together because an intact shield can still be unsafe if it is mis-seated. |
| T3 | Inspect the shield for cracks, heat spots, missing tabs, rub marks, trimmed openings, or loss of stand-off at the busbar edge and stud shoulder. Record which retaining feature or edge actually lost coverage. |
| T4 | Compare the suspect shield position with the neighboring shield or with the untouched side of the same module so tab engagement, stand-off, and busbar coverage are judged against a real reference. This prevents a cosmetic acceptance of a misaligned but unbroken part. |
| T5 | Inspect the neighboring foam barriers and cover ribs for contact witness that could push the shield sideways during closure, then restore only the failed tab, shield panel, or interfering support feature. The coverage path from retaining tab to busbar edge has to remain explicit. |
| T6 | Refit surrounding parts and confirm that the shield still maintains the required stand-off to the busbar edges and stud exits after final loading. A shield that sits correctly only before the cover rib is installed is not acceptable. |
| T7 | End the insulator review only when the note names the exact concern, such as cracked shield panel, missing retaining tab, mis-seated shield edge, or cover-rib interference, and ties it to the final coverage result. The release boundary is a shield that fully covers the intended busbar edges and holds position after the neighboring foam and cover features are restored. |
```

**Data contract**: The filename (`Battery_Module_Busbar_Insulator_Shield_Inspection.md`)
determines the `evidence_id` used throughout the pipeline. The `T<n>` labels in the
first column define the workflow step ordering.

---

## Stage 1: Preprocessing Extraction (LLM API)

**API**: DeepSeek v4 Flash (`deepseek-v4-flash`)
**Prompt**: `config/prompts/preprocessing_extraction_om.txt`

The LLM is called once per document. It receives:
- The raw markdown text from Stage 0
- The 15-concept backbone with descriptions
- Extraction instructions (concept extraction, relation extraction, hypernym classification, step-phase classification)

### Stage 1 Output: EvidenceRecord v2

**File**: `data/evidence_records/test1_battery.json`

**Format**: A JSON object with the following top-level structure:

```json
{
  "project_name": "crossextend_kg_preprocessing",
  "generated_at": "2026-04-25T19:10:12Z",
  "domains": ["battery"],
  "role": "target",
  "document_count": 1,
  "domain_stats": { "battery": { "om_manual": 1 } },
  "evidence_records": [ /* EvidenceRecord[] */ ]
}
```

Each `EvidenceRecord` has this structure (v2 fields marked with **[v2]**):

```json
{
  "evidence_id": "Battery_Module_Busbar_Insulator_Shield_Inspection",
  "domain_id": "battery",
  "role": "target",
  "source_type": "om_manual",
  "timestamp": "2026-04-25T19:09:32Z",
  "raw_text": "<verbatim markdown from Stage 0>",
  "step_records": [ /* StepEvidenceRecord[] */ ],
  "document_concept_mentions": [],
  "document_relation_mentions": [ /* RelationMention[] */ ],
  "procedure_meta": {                    /** [v2] **/
    "asset_name": null,
    "procedure_type": "inspection",
    "primary_fault_type": null
  },
  "cross_step_relations": [              /** [v2] **/
    { "label", "family", "head", "tail", "head_step", "tail_step" }
  ]
}
```

### StepEvidenceRecord: v1 vs v2 Comparison

**v1 fields** (preserved for backward compatibility):

```json
{
  "step_id": "T1",
  "task": {
    "label": "T1",
    "kind": "concept",
    "surface_form": "For Velorian ModuleShield-584, record whether..."
  },
  "concept_mentions": [
    {
      "label": "Velorian ModuleShield-584",
      "kind": "concept",
      "description": "the specific module shield assembly under review",
      "node_worthy": true,
      "surface_form": "Velorian ModuleShield-584",
      "semantic_type_hint": "Asset"
    }
  ],
  "relation_mentions": [
    { "label": "records", "family": "task_dependency", "head": "T1", "tail": "shield edge" },
    { "label": "triggers", "family": "task_dependency", "head": "T1", "tail": "T2" }
  ]
}
```

**v2 fields added** (all optional with defaults):

```json
{
  "step_phase": "observe",             /** [v2] observe/diagnose/repair/verify */
  "step_summary": "For Velorian ModuleShield-584, record whether...", /** [v2] */
  "surface_form": "For Velorian ModuleShield-584, record whether...", /** [v2] independent copy */
  "step_actions": [                    /** [v2] replaces relation_mentions for grounding */
    { "action_type": "records", "target_label": "shield edge" },
    { "action_type": "records", "target_label": "module section" },
    { "action_type": "records", "target_label": "exposed busbar geometry" }
  ],
  "structural_edges": [],              /** [v2] separated structural edges */
  "state_transitions": [],             /** [v2] lifecycle state changes */
  "diagnostic_edges": [],              /** [v2] communication/propagation edges */
  "sequence_next": "T2"               /** [v2] replaces synthetic triggers */
}
```

### Real Step T2 Example (v2 full output)

```json
{
  "step_id": "T2",
  "task": { "label": "T2", "kind": "concept", "node_worthy": true,
    "surface_form": "Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam barriers, and cover ribs without moving the shield from its as-found seat..." },
  "concept_mentions": [
    { "label": "as-found seat", "semantic_type_hint": "State", "shared_hypernym": null },
    { "label": "busbar edges", "semantic_type_hint": "Component", "shared_hypernym": null },
    { "label": "busbar shield", "semantic_type_hint": "Component", "shared_hypernym": "Housing" },
    { "label": "cover ribs", "semantic_type_hint": "Component", "shared_hypernym": "Housing" },
    { "label": "foam barriers", "semantic_type_hint": "Component", "shared_hypernym": "Seal" },
    { "label": "retaining tabs", "semantic_type_hint": "Component", "shared_hypernym": "Fastener" },
    { "label": "stud exits", "semantic_type_hint": "Component", "shared_hypernym": null }
  ],
  "relation_mentions": [
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "busbar shield" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "retaining tabs" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "busbar edges" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "stud exits" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "foam barriers" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "cover ribs" },
    { "label": "triggers", "family": "task_dependency", "head": "T2", "tail": "T3" }
  ],
  "step_phase": null,
  "step_summary": "Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam",
  "step_actions": [
    { "action_type": "exposes", "target_label": "busbar shield" },
    { "action_type": "exposes", "target_label": "retaining tabs" },
    { "action_type": "exposes", "target_label": "busbar edges" },
    { "action_type": "exposes", "target_label": "stud exits" },
    { "action_type": "exposes", "target_label": "foam barriers" },
    { "action_type": "exposes", "target_label": "cover ribs" }
  ],
  "structural_edges": [],
  "state_transitions": [],
  "diagnostic_edges": [],
  "sequence_next": "T3"
}
```

### Key v1→v2 Differences in StepEvidenceRecord

| Aspect | v1 | v2 |
|--------|----|----|
| Step phase | Not captured | `step_phase`: observe/diagnose/repair/verify |
| Step-concept grounding | Via `relation_mentions` with `family="task_dependency"` | Via `step_actions[]` (clean `StepAction` records) |
| Step sequence | Via synthetic `triggers` relation | Via `sequence_next` (direct next-step pointer) |
| Structural edges | Mixed into `relation_mentions` | Separated into `structural_edges[]` |
| Diagnostic edges | Mixed into `relation_mentions` | Separated into `diagnostic_edges[]` |
| State transitions | Not captured | `state_transitions[]` |
| Hypernym | Not captured on concepts | `shared_hypernym` on `ConceptMention` |

### Document-Level v2 Additions

**`procedure_meta`**: Inferred from document content:
```json
{
  "asset_name": null,
  "procedure_type": "inspection",
  "primary_fault_type": null
}
```

**`cross_step_relations`**: 5 cross-step diagnostic relations (T3→T7):
```json
[
  { "label": "indicates", "family": "communication", "head": "contact witness", "tail": "interfering support feature", "head_step": "T5", "tail_step": "T5" },
  { "label": "indicates", "family": "communication", "head": "loss of stand-off", "tail": "mis-seated shield edge", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "missing tabs", "tail": "missing retaining tab", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "cracks", "tail": "cracked shield panel", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "rub marks", "tail": "cover-rib interference", "head_step": "T3", "tail_step": "T7" }
]
```

These cross-step relations capture that fault signals observed in T3 (cracks, rub marks, missing tabs, loss of stand-off) are resolved into specific fault diagnoses in T7 (cracked shield panel, cover-rib interference, missing retaining tab, mis-seated shield edge).

### Document-Level Relations (v1 field, still present)

6 structural `contains` relations + 5 communication `indicates` relations:
```json
[
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "busbar shield" },
  { "label": "contains", "family": "structural", "head": "busbar shield", "tail": "retaining tabs" },
  { "label": "contains", "family": "structural", "head": "busbar shield", "tail": "shield edge" },
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "foam barriers" },
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "cover ribs" },
  { "label": "indicates", "family": "communication", "head": "contact witness", "tail": "interfering support feature" },
  { "label": "indicates", "family": "communication", "head": "loss of stand-off", "tail": "mis-seated shield edge" },
  { "label": "indicates", "family": "communication", "head": "missing tabs", "tail": "missing retaining tab" },
  { "label": "indicates", "family": "communication", "head": "cracks", "tail": "cracked shield panel" },
  { "label": "indicates", "family": "communication", "head": "rub marks", "tail": "cover-rib interference" }
]
```

---

## Stage 2: Evidence Loading & Normalization

**No API calls.** Pure Python transformation.

The pipeline loads the EvidenceRecord and aggregates semantic candidates:

- Each `concept_mentions` entry where `node_worthy=true` becomes a `SchemaCandidate`
- Labels are normalized (trailing punctuation stripped, whitespace normalized)
- `shared_hypernym` is propagated to `routing_features["shared_hypernym"]`
- `semantic_type_hint` is propagated to `routing_features["semantic_type_hint"]`
- Document-level relation statistics (`relation_participation_count`, `relation_head_count`, `relation_tail_count`, `relation_families`) are computed per candidate

**Output**: 37 `SchemaCandidate` objects (from 37 `node_worthy=true` concept mentions across all 7 steps)

Example candidate for "Velorian ModuleShield-584":
```json
{
  "candidate_id": "battery::Velorian ModuleShield-584",
  "domain_id": "battery",
  "label": "Velorian ModuleShield-584",
  "description": "the specific module shield assembly under review",
  "evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "routing_features": {
    "evidence_count": 1,
    "relation_participation_count": 3,
    "relation_head_count": 3,
    "relation_tail_count": 0,
    "relation_families": ["structural"],
    "step_ids": ["T1"],
    "semantic_type_hint": "Asset",
    "semantic_type_hint_candidates": ["Asset"],
    "support_count": 1,
    "shared_hypernym": "Housing"
  }
}
```

Note that `shared_hypernym: "Housing"` is propagated from the `ConceptMention` to
`routing_features`, enabling anchor-assisted routing in the attachment stage.

---

## Stage 3: Backbone Routing & Attachment (Embedding + LLM)

**APIs**: DashScope text-embedding-v4 (embedding) + DeepSeek Chat (LLM judge)

### Step 3a: Embedding Retrieval

Each candidate's label is embedded via DashScope text-embedding-v4. The embedding
is compared (cosine similarity) against pre-computed backbone concept embeddings.

Batching: DashScope API accepts max 10 texts per request. The pipeline automatically
batches: 37 candidates split into 4 batches (10+10+10+7).

Real retrieval result for "Velorian ModuleShield-584":
```
Anchor: Component  → score: 0.4249  (rank 1)
Anchor: Sensor     → score: 0.3825  (rank 2)
Anchor: Housing    → score: 0.3688  (rank 3)
```

### Step 3b: LLM Attachment Judge

The LLM receives the candidate's description, embedding priors, routing features
(including `shared_hypernym`), and makes an attachment decision.

Real LLM decision for "Velorian ModuleShield-584":
```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Component",
  "accept": true,
  "admit_as_node": true,
  "confidence": 0.85,
  "justification": "type=Component; anchor=Component; priors=conflict; reason=Specific named shield assembly, structural relations, semantic type Asset but better grounded as Component under Housing."
}
```

### Step 3c: Attachment Audit Summary

| Metric | Count |
|--------|-------|
| Total candidates | 37 |
| Accepted as adapter | 34 |
| Accepted as backbone reuse | 0 |
| Rejected | 3 |

**Rejected candidates** (with reasons):

| Label | Reject Reason |
|-------|--------------|
| `busbar-insulator review` | `observation_like_not_grounded` |
| `untouched side` | `low_graph_value` |
| `release boundary` | `low_graph_value` |

### Step 3d: Parent Anchor Assignment

The 34 accepted candidates are assigned to backbone anchors:

| parent_anchor | Count | Example Concepts |
|---------------|-------|-----------------|
| Fault | 9 | cracks, heat spots, missing tabs, rub marks, loss of stand-off, ... |
| Component | 7 | exposed busbar geometry, busbar edges, module section, stud exits, ... |
| Housing | 4 | busbar shield, cover ribs, shield edge, neighboring shield, shield panel |
| State | 3 | as-found seat, busbar coverage, tab engagement, final coverage result |
| Signal | 3 | contact witness, coverage path, required stand-off |
| Fastener | 2 | retaining tabs, stud shoulder |
| Asset | 1 | Velorian ModuleShield-584 |
| Seal | 1 | foam barriers |
| ... | ... | (remaining Tier-1 anchors have 0 adapter concepts) |

---

## Stage 4: Graph Assembly (Dual-Layer)

**No API calls.** Pure Python graph construction.

The graph assembler consumes AttachmentDecisions + EvidenceRecord to build a
dual-layer graph.

### Workflow Layer Construction

**Workflow step nodes** (7 total): One node per `step_records` entry.

Each workflow node gets:
- `node_id`: runtime node ID such as `"battery::node::Battery_Module_Busbar_Insulator_Shield_Inspection:T1"`
- `label`: scoped workflow label such as `"Battery_Module_Busbar_Insulator_Shield_Inspection:T1"`
- `step_id`: original step token (`"T1"` through `"T7"`)
- `node_type`: "workflow_step"
- `step_phase`: from `StepEvidenceRecord.step_phase`
- `display_label`: canonical short title derived from grounded workflow action + object when possible, otherwise a truncated step-text fallback
- `surface_form` / `provenance_evidence_ids`: full step text plus source-document provenance

| Step | Phase | Display Label |
|------|-------|---------------|
| T1 | observe | "Record busbar-insulator review (T1)" |
| T2 | (null) | "Expose local assembly (T2)" |
| T3 | observe | "Inspect fault boundary (T3)" |
| T4 | diagnose | "Compare reference dimensions (T4)" |
| T5 | observe | "Inspect contact witness (T5)" |
| T6 | verify | "Verify required stand-off (T6)" |
| T7 | observe | "Inspect fault boundary (T7)" |

**Workflow sequence edges** (6 total): T1→T2→T3→T4→T5→T6→T7
- Source: `sequence_next` field (v2 authoritative source)
- Stored `family`: `task_dependency`
- Stored `workflow_kind`: `sequence`
- Stored relation label: `triggers`

**Workflow grounding edges** (action_object, 24 total):

Source: `step_actions[]` (v2 authoritative source; no runtime fallback to `relation_mentions`).

| Step | Action Type | Target Concept | Display-Admitted |
|------|------------|----------------|-----------------|
| T2 | exposes | busbar shield | Yes |
| T2 | exposes | busbar edges | Yes |
| T2 | exposes | stud exits | Yes |
| T2 | exposes | foam barriers | Yes |
| T2 | exposes | cover ribs | Yes |
| T3 | inspects | cracks | Yes |
| T3 | inspects | heat spots | Yes |
| T3 | inspects | missing tabs | Yes |
| T3 | inspects | rub marks | Yes |
| T3 | inspects | trimmed openings | Yes |
| T3 | inspects | loss of stand-off | Yes |
| T5 | inspects | contact witness | Yes |
| T5 | repairs | failed tab | Yes |
| T5 | repairs | interfering support feature | Yes |
| T6 | verifies | required stand-off | Yes |
| T7 | verifies | final coverage result | Yes |
| T1 | records | module section | No (`record_requires_signal_like_target`) |
| T1 | records | shield edge | No (`record_requires_signal_like_target`) |
| T1 | records | exposed busbar geometry | No (`record_requires_signal_like_target`) |
| T2 | exposes | retaining tabs | No (`expose_requires_component_target`) |
| T4 | compares | neighboring shield | No (`compare_requires_grounded_target`) |
| T5 | repairs | shield panel | No (`repair_requires_component_target`) |

### Semantic Layer Construction

**Semantic concept nodes** (34 total): From accepted attachment decisions.

Each semantic node gets:
- `label`: from the candidate label
- `node_type`: "adapter_concept"
- `parent_anchor`: from attachment decision
- `shared_hypernym`: from routing_features (v2)

**Semantic edges** (2 accepted):

Both are structural `contains` edges accepted by the relation validator:

| Head | Relation | Tail | Family |
|------|----------|------|--------|
| Velorian ModuleShield-584 | contains | foam barriers | structural |
| Velorian ModuleShield-584 | contains | cover ribs | structural |

The other structural edges were rejected by relation rules:
- `busbar shield` → `retaining tabs`: rejected (`structural_requires_stable_components`)
- `busbar shield` → `shield edge`: rejected (`structural_low_value_tail`)

Communication edges were rejected by type constraints (Fault head not allowed in
communication family):
- `loss of stand-off` → `mis-seated shield edge`: rejected (`type_constraint`)
- `missing tabs` → `missing retaining tab`: rejected (`type_constraint`)
- `cracks` → `cracked shield panel`: rejected (`type_constraint`)
- `rub marks` → `cover-rib interference`: rejected (`type_constraint`)

### Relation Validation Summary

| Category | Count | Detail |
|----------|-------|--------|
| Total candidate triples | 40 | |
| Accepted | 30 | |
| Rejected (family rules) | 6 | structural_low_value_tail:1, structural_requires_stable_components:2, single_step_diagnostic_hypothesis:1, tail:not_in_graph:1, tail:low_graph_value:1 |
| Rejected (type constraints) | 4 | Fault head in communication family |

---

## Stage 5: Export

**No API calls.** Pure Python serialization.

### Output: final_graph.json

**File**: `results/test1/test1-20260425T191442Z/full_llm/working/battery/final_graph.json`

Structure:
```json
{
  "domain_id": "battery",
  "summary": {
    "node_count": 41,
    "edge_count": 30,
    "workflow_step_node_count": 7,
    "semantic_node_count": 34,
    "workflow_edge_count": 28,
    "semantic_edge_count": 2,
    "readable_node_count": 24,
    "readable_edge_count": 24,
    "candidate_triple_count": 40,
    "accepted_triple_count": 30,
    "rejected_triple_count": 6,
    "type_rejected_triple_count": 4,
    "hypernym_coverage": 0.1471,
    "hypernym_distribution": { "Housing": 3, "Seal": 1, "Fastener": 1 },
    "phase_distribution": { "observe": 4, "diagnose": 1, "verify": 1 }
  },
  "nodes": [ ... ],
  "edges": [ ... ],
  "relation_validation": { ... }
}
```

### Node Format (GraphNode)

`step_summary` remains on `StepEvidenceRecord`. In the final graph, workflow nodes
materialize `display_label`, `surface_form`, and provenance instead.

**Workflow step node example**:
```json
{
  "node_id": "battery::node::Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "label": "Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "display_label": "Record busbar-insulator review (T1)",
  "domain_id": "battery",
  "node_type": "workflow_step",
  "node_layer": "workflow",
  "parent_anchor": null,
  "surface_form": "For Velorian ModuleShield-584, record whether the busbar-insulator review follows an electrical event...",
  "step_id": "T1",
  "order_index": 1,
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null,
  "lifecycle_stage": null,
  "shared_hypernym": null,
  "step_phase": "observe"
}
```

**Semantic adapter concept node example**:
```json
{
  "node_id": "battery::node::Velorian ModuleShield-584",
  "label": "Velorian ModuleShield-584",
  "display_label": "Velorian ModuleShield-584",
  "domain_id": "battery",
  "node_type": "adapter_concept",
  "node_layer": "semantic",
  "parent_anchor": "Component",
  "surface_form": "Velorian ModuleShield-584",
  "step_id": null,
  "order_index": null,
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null,
  "lifecycle_stage": null,
  "shared_hypernym": "Housing",
  "step_phase": null
}
```

### Edge Format (GraphEdge)

**Workflow sequence edge example**:
```json
{
  "edge_id": "battery::edge::Battery_Module_Busbar_Insulator_Shield_Inspection:T1::triggers::Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "domain_id": "battery",
  "label": "triggers",
  "raw_label": "triggers",
  "display_label": "triggers",
  "family": "task_dependency",
  "edge_layer": "workflow",
  "workflow_kind": "sequence",
  "edge_salience": "high",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "tail": "Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

**Workflow grounding edge example**:
```json
{
  "edge_id": "battery::edge::Battery_Module_Busbar_Insulator_Shield_Inspection:T2::exposes::busbar shield",
  "domain_id": "battery",
  "label": "exposes",
  "raw_label": "exposes",
  "display_label": "expose",
  "family": "action_object",
  "edge_layer": "workflow",
  "workflow_kind": "action_object",
  "edge_salience": "high",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "tail": "busbar shield",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

**Semantic structural edge example**:
```json
{
  "edge_id": "battery::edge::Velorian ModuleShield-584::contains::foam barriers",
  "domain_id": "battery",
  "label": "contains",
  "raw_label": "contains",
  "display_label": "contains",
  "family": "structural",
  "edge_layer": "semantic",
  "workflow_kind": null,
  "edge_salience": "medium",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Velorian ModuleShield-584",
  "tail": "foam barriers",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

### GraphML Export

Same graph is also exported as `.graphml` with node attributes:
- `shared_hypernym` (on adapter_concept nodes)
- `step_phase` (on workflow_step nodes)
- `parent_anchor` (on adapter_concept nodes)

---

## Complete Data Flow Summary Table

| Stage | Input | Key Transform | Output | v2 Fields Involved |
|-------|-------|---------------|--------|-------------------|
| 0 | O&M markdown table | File read | Raw text string | None |
| 1 | Raw text + prompt | LLM extraction → JSON conversion | EvidenceRecord with 7 step_records | `shared_hypernym`, `step_phase`, `step_actions`, `sequence_next`, `structural_edges`, `diagnostic_edges`, `state_transitions`, `procedure_meta`, `cross_step_relations` |
| 2 | EvidenceRecord | Aggregate `node_worthy` concepts | 37 SchemaCandidate objects | `shared_hypernym` → `routing_features` |
| 3a | Candidate labels | Embed → cosine similarity | Retrieval priors per candidate | None (just label text) |
| 3b | Candidate + priors + backbone | LLM judge -> accept/reject + anchor | 34 AttachmentDecisions | `shared_hypernym` used for anchor-assisted routing |
| 4 | Decisions + EvidenceRecord | Build dual-layer graph | 41 nodes, 30 edges | `step_phase` → node attribute; `sequence_next` → sequence edges; `step_actions` → grounding edges; `shared_hypernym` → node attribute |
| 5 | Graph | Serialize | final_graph.json + .graphml | `hypernym_coverage`, `phase_distribution` in summary |

---

## Visual: Final Graph Topology (Simplified)

```
WORKFLOW LAYER                    SEMANTIC LAYER
=============                    ==============

  T1 ─triggers→ T2 ─triggers→ T3 ─triggers→ T4 ─triggers→ T5 ─triggers→ T6 ─triggers→ T7
  (observe)      (null)      (observe)    (diagnose)   (observe)     (verify)     (observe)
  │              │           │            │            │             │            │
  │              ├─exposes→  ├─inspects→  ├─compares→  ├─inspects→   ├─verifies→  ├─verifies→
  │              │ busbar    │ cracks     │ neighbor   │ contact     │ required   │ final
  │              │ shield    │ heat spots │ shield     │ witness     │ stand-off  │ coverage
  │              │ busbar    │ missing    └            │             └            └
  │              │ edges     │ tabs                    ├─repairs→
  │              │ stud      │ rub marks              │ failed tab
  │              │ exits     │ trimmed                ├─repairs→
  │              │ foam      │ openings               │ interfering
  │              │ barriers  │ loss of                └
  │              │ cover     │ stand-off
  │              │ ribs      └
  │              └
  │              └─── Also: Velorian ModuleShield-584 ─contains→ foam barriers
  │                                           └─contains→ cover ribs
  │
  └ (T1 grounding edges hidden: records→module section, shield edge, exposed busbar geometry)
```

---

## What v2 Adds: Three Innovation Points

### 1. Cross-Domain Generalization via shared_hypernym

In v1, "busbar shield" and a hypothetical CNC "spindle housing" would be
unrelated nodes. In v2, both carry `shared_hypernym: "Housing"`, enabling
cross-domain alignment through the Tier-1 backbone.

In this example:
- `Velorian ModuleShield-584` → hypernym: **Housing**
- `busbar shield` → hypernym: **Housing**
- `cover ribs` → hypernym: **Housing**
- `foam barriers` → hypernym: **Seal**
- `retaining tabs` → hypernym: **Fastener**

### 2. Temporal Backtracking via step_phase

The phase distribution shows a clear O&M procedure pattern:
- **observe** (T1, T3, T5, T7): Data-gathering steps
- **diagnose** (T4): Analytical comparison step
- **verify** (T6): Confirmation step

This enables downstream tasks like "which step diagnosed the fault?" or
"trace the observation→diagnosis→verification path."

### 3. Complex Propagation Paths via cross_step_relations

The 5 cross-step relations trace fault signal propagation:
```
T3:cracks ─indicates→ T7:cracked shield panel
T3:rub marks ─indicates→ T7:cover-rib interference
T3:missing tabs ─indicates→ T7:missing retaining tab
T3:loss of stand-off ─indicates→ T7:mis-seated shield edge
T5:contact witness ─indicates→ T5:interfering support feature
```

This captures that fault observations in T3 are resolved to specific diagnoses
in T7 — a 4-step diagnostic propagation chain that v1's flat `relation_mentions`
could not express.
