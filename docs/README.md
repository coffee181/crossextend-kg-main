# Documentation

Live documentation for the CrossExtend-KG v2 mainline.

## Reading Order

1. `PROJECT_INTRODUCTION_CN.md`
   Chinese full project introduction for non-specialists: business goal, architecture, modules, data formats, data flow, and final graph shape.
2. `SYSTEM_DESIGN.md`
   Active architecture rules, runtime boundaries, and v2 model extensions.
3. `PIPELINE_DATA_FLOW.md`
   End-to-end data flow from O&M markdown to exported graph artifacts.
4. `DATA_FLOW_DIAGRAM.md`
   **Real single-document example** tracing data format changes through every pipeline stage.
5. `WORKFLOW_KG_DESIGN.md`
   Dual-layer graph design, v2 innovations, and evaluation boundary.
6. `EXPERIMENT_REPORT.md`
   Complete v2 regression experiment report (3 tests, v1 vs v2 comparison, cross-domain analysis).
7. `OPEN_SOURCE_UPDATE_CN.md`
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

## Regression Experiment Results (2026-04-26)

### Rule-based Regression (deterministic, no LLM)

| Test | Docs | battery nodes/edges | cnc nodes/edges | nev nodes/edges |
|------|------|--------------------|-----------------|-----------------|
| Test 1 | 1 | 59/69 | — | — |
| Test 2 | 3 | 48/57 | 68/90 | 73/115 |
| Test 3 | 9 | 132/206 | 160/275 | 173/314 |

### 9-Doc Ablation: Embedding + LLM Variants

Three attachment strategies compared on the 9-doc benchmark:

| Variant | Nodes | Edges | Accepted Triples | Rejected Cands |
|---------|-------|-------|-----------------|----------------|
| baseline_embedding_llm | 454 | 754 | 417 | 12 |
| **contextual_rerank_embedding_llm** | **461** | **776** | **432** | **5** |
| pure_llm | 459 | 772 | 430 | 7 |

Per-domain accepted triples:

| Variant | battery | cnc | nev |
|---------|---------|-----|-----|
| baseline_embedding_llm | 106 | 148 | 163 |
| contextual_rerank_embedding_llm | 107 | 151 | **174** |
| pure_llm | 106 | 150 | **174** |

Key findings:
- Contextual rerank variant achieves highest accepted triple count (432) and lowest rejection (5)
- NEV domain shows largest variant sensitivity: 163 → 174 triples (+6.7%)
- CNC domain is stable across all variants (148–151)
- 9 attachment gold files (359 concepts) completed for evaluation

See `EXPERIMENT_REPORT.md` for full details.

## Removed Historical Material

Old round-by-round optimization logs, one-off regression notes, and temporary
experiment reports are no longer part of the live repository contract. Deleted
docs (`DOWNSTREAM_EVALUATION.md`, `GRAPH_QUALITY_DIAGNOSIS.md`) have been
absorbed into `WORKFLOW_KG_DESIGN.md` and the downstream README.
