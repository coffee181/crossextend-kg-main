# Workflow KG Design

## Current Design

CrossExtend-KG now uses a single graph with two explicit layers:

- `workflow`
  ordered maintenance procedure steps
- `semantic`
  assets, components, signals, states, and faults

The graph is workflow-first. Semantic nodes and semantic edges are kept to
ground and explain workflow decisions, not to replace the workflow layer.

## Node Design

### Workflow Nodes

Workflow steps are materialized as `workflow_step` nodes with:

- `label`
- `display_label`
- `step_id`
- `order_index`
- `surface_form`
- `node_layer="workflow"`

They are no longer treated as ordinary semantic `Task` concepts in the runtime
graph. `Task` only remains in the evaluator as a legacy projection for current
human gold compatibility.

### Semantic Nodes

Semantic nodes are attached under the fixed backbone:

- `Asset`
- `Component`
- `Signal`
- `State`
- `Fault`

## Edge Design

### Workflow Edges

- `workflow_step -> workflow_step`
  procedure sequence edges with `workflow_kind="sequence"`
- `workflow_step -> semantic node`
  step grounding edges with `workflow_kind="action_object"`

### Semantic Edges

- `structural`
- `communication`
- `propagation`
- `lifecycle`

These stay in the semantic layer and do not replace workflow edges.

## Evaluation Boundary

Current graph-facing paper metrics:

- `workflow_step_f1`
- `workflow_sequence_f1`
- `workflow_grounding_precision / recall / f1`
- `anchor_accuracy`
- `anchor_macro_f1`

Diagnostics retained but not paper-front:

- `anchored_node_canonical_f1`
- `relation_f1`
- concept and relaxed matching metrics

## Why This Shape

This graph shape is intended to support downstream O&M enhancement tasks:

- evidence-grounded workflow retrieval
- repair suffix ranking

See `DOWNSTREAM_EVALUATION.md` for the downstream protocol.
