# Documentation

Live documentation for the CrossExtend-KG v2 mainline.

## Reading Order

1. `SYSTEM_DESIGN.md`
   Active architecture rules, runtime boundaries, and v2 model extensions.
2. `PIPELINE_DATA_FLOW.md`
   End-to-end data flow from O&M markdown to exported graph artifacts.
3. `DATA_FLOW_DIAGRAM.md`
   **Real single-document example** tracing data format changes through every pipeline stage.
4. `WORKFLOW_KG_DESIGN.md`
   Dual-layer graph design, v2 innovations, and evaluation boundary.
5. `EXPERIMENT_REPORT.md`
   Complete v2 regression experiment report (3 tests, v1 vs v2 comparison, cross-domain analysis).
6. `OPEN_SOURCE_UPDATE_CN.md`
   Chinese summary of the repository scope, v2 restructuring, and open-source maintenance principles.

## 中文文档

- `DATA_FLOW_DIAGRAM_CN.md` — 数据流图中文版（真实单文档示例，各阶段格式变化）
- `EXPERIMENT_REPORT_CN.md` — 回归实验报告中文版（3 次测试、v1 与 v2 对比、跨域分析）
- `OPEN_SOURCE_UPDATE_CN.md` — v2 重构中文说明

## v2 Restructuring Summary

The v2 update restructured the evidence data model to support three paper-facing
innovation points:

1. **Cross-domain generalization** via `shared_hypernym` (10 Tier-1 categories)
2. **Temporal backtracking** via `step_phase` + `state_transitions`
3. **Complex propagation paths** via `diagnostic_edges` + `cross_step_relations`

The backbone was expanded from 6 to 15 concepts. All v1 data remains compatible
through optional fields with defaults.

## Regression Experiment Results (2026-04-25)

Three regression tests were run with real API calls (DeepSeek LLM + DashScope Embedding):

| Test | Docs | battery nodes/edges | cnc nodes/edges | nev nodes/edges | Avg hypernym_cov |
|------|------|--------------------|-----------------|-----------------|-----------------|
| Test 1 | 1 | 41/30 | — | — | 14.7% |
| Test 2 | 3 | 33/31 | 54/44 | 56/62 | 41.5% |
| Test 3 | 9 | 114/103 | 142/140 | 153/164 | 36.8% |

Key findings:
- 7/10 Tier-1 hypernyms appear in all 3 domains at 9-doc scale
- Hypernym coverage increases with document count (14.7% → 49.5% for battery)
- Pipeline scales linearly (~3x nodes/edges for 3x docs)
- Triple acceptance rates stable at 78–92%

See `EXPERIMENT_REPORT.md` for full details.

## Removed Historical Material

Old round-by-round optimization logs, one-off regression notes, and temporary
experiment reports are no longer part of the live repository contract. Deleted
docs (`DOWNSTREAM_EVALUATION.md`, `GRAPH_QUALITY_DIAGNOSIS.md`) have been
absorbed into `WORKFLOW_KG_DESIGN.md` and the downstream README.
