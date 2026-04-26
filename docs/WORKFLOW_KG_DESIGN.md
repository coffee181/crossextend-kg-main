# Workflow KG Design

## Current Design

CrossExtend-KG uses a single graph with two explicit layers:

- `workflow`
  ordered maintenance procedure steps
- `semantic`
  assets, components, signals, states, and faults

The graph is workflow-first. Semantic nodes and semantic edges are kept to
ground and explain workflow decisions, not to replace the workflow layer.

## v2 Innovations

The v2 restructuring adds three structural capabilities to the dual-layer graph:

### 1. Cross-Domain Generalization (shared_hypernym)

Each `ConceptMention` may carry a `shared_hypernym` from 10 Tier-1 categories:

| Hypernym | Battery Example | CNC Example | NEV Example |
|----------|----------------|-------------|-------------|
| Seal | EPDM O-ring | cover gasket | door seal |
| Connector | quick-connector | terminal block | charge inlet |
| Sensor | NTC thermistor | limit switch | resolver |
| Controller | BMS main board | servo drive | motor controller |
| Coolant | glycol loop | chiller fluid | battery coolant |
| Actuator | contactor | solenoid valve | lock actuator |
| Power | HV bus | 24V supply | 12V battery |
| Housing | pack case | column enclosure | junction box |
| Fastener | M6 bolt | clamp bolt | bracket bolt |
| Media | seepage | mist | refrigerant |

This enables consistent cross-domain concept mapping: "O-ring" in battery,
"cover gasket" in CNC, and "door seal" in NEV all map to `Seal` in the
backbone, enabling LOODO (leave-one-domain-out) transfer evaluation.

### 2. Temporal Backtracking (step_phase + state_transitions)

Each `StepEvidenceRecord` has a `step_phase` classified by verb patterns:

| Phase | Priority | Example Verbs |
|-------|----------|---------------|
| verify | 1 (highest) | verify, validate, confirm, test, monitor, pressurize |
| observe | 2 | inspect, check, record, measure, examine, trace |
| diagnose | 3 | diagnose, analyze, compare, evaluate, assess, determine |
| repair | 4 (lowest) | repair, replace, reseat, correct, install, torque, adjust |

Priority ordering ensures "Verify no leak after repair" is classified as
`verify` (not `repair`), reflecting the step's intent.

`state_transitions` capture lifecycle state changes (e.g., leak detected ->
leak confirmed -> leak repaired) with `from_state`, `to_state`, `trigger_step`,
and optional `evidence_label`.

`procedure_meta` captures document-level metadata: `asset_name`, `procedure_type`
(diagnosis/inspection/replacement/repair/verification), and `primary_fault_type`.

### 3. Complex Propagation Paths (diagnostic_edges + cross_step_relations)

`diagnostic_edges` separate communication/propagation evidence from task
dependencies, each with `evidence_label`, `indicated_label`, and `mechanism`
(communication or propagation).

`cross_step_relations` link concepts across steps for inter-step diagnostic
reasoning, carrying both concept labels and their step attribution
(`head_step`, `tail_step`). This enables tracing how an observation in T1
connects to a diagnosis in T3 or a root cause in T5.

## Node Design

### Workflow Nodes

Workflow steps are materialized as `workflow_step` nodes with:

- `label` (e.g., "BATOM_001:T1")
- `display_label` (canonical action + object, e.g., "Inspect O-ring (T1)")
- `step_id` (e.g., "T1")
- `order_index`
- `surface_form` (full step text)
- `node_layer="workflow"`
- `step_phase` (observe/diagnose/repair/verify) -- **v2**

They are no longer treated as ordinary semantic `Task` concepts in the runtime
graph. `Task` only remains in the evaluator as a legacy projection for current
human gold compatibility.

### Semantic Nodes

Semantic nodes are attached under the fixed backbone:

**Tier 0**: `Asset`, `Component`, `Signal`, `State`, `Fault`

**Tier 1**: `Seal`, `Connector`, `Sensor`, `Controller`, `Coolant`, `Actuator`, `Power`, `Housing`, `Fastener`, `Media`

Each semantic node may carry `shared_hypernym` -- **v2** (the Tier-1 category it
maps to, enabling cross-domain consistency checks).

## Edge Design

### Workflow Edges

- `workflow_step -> workflow_step`
  procedure sequence edges with `workflow_kind="sequence"`
- `workflow_step -> semantic node`
  step grounding edges with `workflow_kind="action_object"`

Authoritative v2 field consumption:

| Edge Kind | Source |
|-----------|--------|
| sequence | `step.sequence_next` |
| action_object | `step.step_actions` |
| structural | `document_relation_mentions` structural family |
| communication / propagation | `document_relation_mentions` with `cross_step_relations` metadata when present |
| lifecycle | `document_relation_mentions` lifecycle family |

Display labels are derived from `step_phase`: observe->"inspect", diagnose->"analyze", repair->"repair", verify->"verify".

### Semantic Edges

- `structural` (contains)
- `communication` (indicates, provides, emits, monitors)
- `propagation` (causes, comprises)
- `lifecycle` (hasState, transitionsTo)

These stay in the semantic layer and do not replace workflow edges.

### Cross-Step Relations

Document-level communication/propagation relations that span steps are
represented as `cross_step_relations` with step attribution. In the graph,
these become semantic edges that connect concepts across different workflow
steps (e.g., "body off header plate --indicates--> hose-induced preload" where
head is in T1 and tail is in T2).

## Graph Filtering Rules

The graph assembler applies these filtering rules:

1. **Structural self-loops** rejected (head == tail)
2. **Structural contextual heads** rejected (heads matching "branch/path/condition/state")
3. **Structural low-value tails** rejected (tails matching "hose/clip/rib/panel/overmold")
4. **Single-step diagnostic hypotheses** rejected (both head and tail in same step)
5. **Multi-target diagnostic hypotheses** rejected (one head with multiple tail targets)
6. **Workflow asset context** edges hidden (action_object edges to Asset-anchored nodes)
7. **Task parent for semantic attachment** rejected by rule filtering

## Evaluation Boundary

Current graph-facing paper metrics:

- `workflow_step_f1`
- `workflow_sequence_f1`
- `workflow_grounding_precision / recall / f1`
- `anchor_accuracy`
- `anchor_macro_f1`

v2 diagnostic metrics (reported in graph summary):

- `hypernym_coverage`: fraction of semantic nodes with a shared_hypernym
- `phase_distribution`: distribution of step_phase across workflow nodes

Diagnostics retained but not paper-front:

- `anchored_node_canonical_f1`
- `relation_f1`
- concept and relaxed matching metrics

## Downstream Tasks

This graph shape supports downstream O&M enhancement tasks:

- **evidence-grounded workflow retrieval**: given a complaint/symptom, retrieve the most relevant ordered workflow with grounded objects
- **repair suffix ranking**: given an observed workflow prefix, rank candidate repair suffixes

See `experiments/downstream/` for the protocol design and benchmark schema.
