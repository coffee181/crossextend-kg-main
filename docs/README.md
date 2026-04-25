# Documentation

Live documentation for the CrossExtend-KG v2 mainline.

## Reading Order

1. `SYSTEM_DESIGN.md`
   Active architecture rules, runtime boundaries, and v2 model extensions.
2. `PIPELINE_DATA_FLOW.md`
   End-to-end data flow from O&M markdown to exported graph artifacts.
3. `WORKFLOW_KG_DESIGN.md`
   Dual-layer graph design, v2 innovations, and evaluation boundary.
4. `OPEN_SOURCE_UPDATE_CN.md`
   Chinese summary of the repository scope, v2 restructuring, and open-source maintenance principles.

## v2 Restructuring Summary

The v2 update restructured the evidence data model to support three paper-facing
innovation points:

1. **Cross-domain generalization** via `shared_hypernym` (10 Tier-1 categories)
2. **Temporal backtracking** via `step_phase` + `state_transitions`
3. **Complex propagation paths** via `diagnostic_edges` + `cross_step_relations`

The backbone was expanded from 6 to 15 concepts. All v1 data remains compatible
through optional fields with defaults.

## Removed Historical Material

Old round-by-round optimization logs, one-off regression notes, and temporary
experiment reports are no longer part of the live repository contract. Deleted
docs (`DOWNSTREAM_EVALUATION.md`, `GRAPH_QUALITY_DIAGNOSIS.md`) have been
absorbed into `WORKFLOW_KG_DESIGN.md` and the downstream README.
