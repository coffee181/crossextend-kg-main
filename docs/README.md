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
6. `OPEN_SOURCE_UPDATE_CN.md`
   Chinese summary of the repository scope, v2 restructuring, and open-source maintenance principles.

## 中文文档

- `DATA_FLOW_DIAGRAM_CN.md` — 数据流图中文版（真实单文档示例，各阶段格式变化）
- `OPEN_SOURCE_UPDATE_CN.md` — v2 重构中文说明

## v2 Restructuring Summary

The v2 update restructured the evidence data model to support three paper-facing
innovation points:

1. **Cross-domain generalization** via `shared_hypernym` (10 Tier-1 categories)
2. **Temporal backtracking** via `step_phase` + `state_transitions`
3. **Complex propagation paths** via `diagnostic_edges` + `cross_step_relations`

The backbone was expanded from 6 to 15 concepts. All v1 data remains compatible
through optional fields with defaults.

## Full-Scale Preprocessing (400 Docs, May 2026)

**Model**: deepseek-v4-pro | **Backend**: DeepSeek API

| Domain | Documents | Status |
|--------|-----------|--------|
| battery | 100 | Complete |
| cnc | 100 | Complete |
| ev (nev) | 200 | Complete |
| **Total** | **400** | **Complete** |

- **Total time**: 59.4 hours (~2.5 days)
- **Average rate**: 535s/doc (8.9 min/doc)
- **Output**: `data/evidence_records/evidence_records_llm.json` (20.6 MB)
- **Per-domain files**: battery (5.0 MB), cnc (5.2 MB), ev (10.6 MB)
- **API retries**: 2-3 transient JSON parse failures, auto-recovered

### Run Command

```bash
python -m scripts.run_full_preprocess
```

Configuration: `config/persistent/preprocessing.deepseek.yaml` (extends `preprocessing.base.yaml`)
LLM backend: `config/persistent/llm_backends.yaml` → `deepseek-v4-pro`

## Removed Historical Material

Old round-by-round optimization logs, one-off regression notes, and temporary
experiment reports are no longer part of the live repository contract. Deleted
docs (`DOWNSTREAM_EVALUATION.md`, `GRAPH_QUALITY_DIAGNOSIS.md`) have been
absorbed into `WORKFLOW_KG_DESIGN.md` and the downstream README.
