# CrossExtend-KG Documentation

**Updated**: 2026-04-22
**Scope**: Current paper-facing O&M runtime and evaluation contract

## Reading Order

1. `SYSTEM_DESIGN.md`
   Active architecture rules, runtime assumptions, and paper-facing story.
2. `PIPELINE_DATA_FLOW.md`
   **Complete pipeline data flow with real examples**: 7-stage architecture, format transformations, LLM call details, and workflow layer structure.
3. `WORKFLOW_KG_DESIGN.md`
   Workflow layer architecture: three-layer structure (semantic/workflow/grounding), downstream task design, and paper experiment planning.
4. `EXPERIMENT_RESULTS.md`
   **9-document experiment results**: Workflow metrics (step_f1=0.94, sequence_f1=0.94), baseline comparison, ablation analysis, and identified issues.
5. `PIPELINE_INTEGRATION.md`
   End-to-end execution checkpoints, commands, and current validation reality.
6. `PROJECT_ARCHITECTURE.md`
   Repository layout and responsibility of each active module.
7. `MANUAL_ANNOTATION_PROTOCOL.md`
   Human-gold annotation policy for publication-grade evaluation.
8. `GROUND_TRUTH_QUALITY_ANALYSIS.md`
   Current blind-reannotated gold status, remaining credibility risk, and the lightweight review plan.
9. `MINIMAL_PAPER_EXECUTION_PLAN.md`
   Narrow execution plan for the current submission line: direct alignment, fixed metric boundary, and gold credibility reinforcement.
10. `REVIEW_ADOPTION_PLAN.md`
   Adoption map for external review feedback and which ideas are accepted, scoped, or deferred.
11. `EVIDENCE_FORMAT_IMPROVEMENT.md`
   Design notes for richer evidence records and diagnostics.
12. `FIVE_ROUND_OPTIMIZATION_REPORT.md`
   Frozen historical optimization log. Treat it as background, not the live execution contract.
13. `FIVE_ROUND_OPTIMIZATION_REPORT_CN.md`
   Chinese version of the frozen five-round report.

## Current Truth

- The active input type is `om_manual` only.
- The current repository data covers three domains: `battery`, `cnc`, and `nev`.
- The main paper-facing variant is `full_llm`.
- The current paper-facing ablation suite includes:
  `full_llm`, `no_preprocessing_llm`, `no_rule_filter`, `no_embedding_routing`, `no_attachment_llm`, `embedding_top1`.
- Paper-facing baselines are `rule_pipeline` and `llm_direct_graph`.
- Evaluation credibility comes from manually reviewed gold files.
- Paper-facing workflow metrics are:
  - `workflow_step_f1`: Workflow step node detection (**actual: 0.94**)
  - `workflow_sequence_f1`: Workflow sequence edge detection (**actual: 0.94**)
  - `workflow_grounding_f1`: Step-object grounding edge detection (**actual: 0.00** — needs fix)
  - Supporting metrics: `anchor_accuracy` (**actual: 0.99**), `anchor_macro_f1` (**actual: 0.97**)
- **Key findings from 9-doc experiment**:
  - LLM preprocessing contributes +19% improvement vs rule-based
  - Rule filter improves anchored node quality by 4%
  - Workflow grounding edges not generated (action_object edges missing)
- Semantic metrics (`anchored_node_canonical_f1`, `relation_f1`, `node_coverage_relaxed_f1`) are auxiliary evidence.
- Diagnostic metrics should not drive the main paper claim.
- The active 9-file O&M gold package was blindly annotated from source text.
- Workflow annotations (`workflow_relation_ground_truth`) are now available for all 9 documents.

## Related Directories

- `../config/` -- Runtime configs, prompts, and backend registries.
- `../preprocessing/` -- O&M markdown to `EvidenceRecord` conversion.
- `../pipeline/` -- Backbone retrieval, attachment, graph assembly, export.
- `../rules/` -- Final attachment filtering and node-admission logic.
- `../experiments/` -- Metrics, ablation, baselines, repeated-run aggregation.
- `../data/ground_truth/` -- Human-annotated gold files.
- `../data/evidence_records/` -- LLM-extracted evidence records.