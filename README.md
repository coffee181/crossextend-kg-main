# CrossExtend-KG

CrossExtend-KG currently constructs industrial knowledge graphs from O&M manuals with a fixed shared backbone and an auditable attachment pipeline.

## 本次相对上次的主要修改

- 将实验代码从扁平脚本重构为 `experiments/metrics/`、`experiments/ablation/`、`experiments/comparison/` 三个子模块，区分主指标计算、诊断指标、消融运行与结果对比。
- 补齐三领域 O&M 数据与人工冻结 gold 标注，当前 `battery`、`cnc`、`nev` 均已有可直接进入评测链路的文档与 `data/ground_truth/*.json` 标注文件。
- 收紧预处理、attachment、filtering、graph assembly 的主线逻辑，继续坚持 `no fallback`，避免用旁路逻辑掩盖真实问题。
- 预处理侧强化了证据抽取约束，减少低价值碎片 concept、过度 structural relation 和错误 task 归类带来的后续噪声。
- 评测侧保留严格主指标，同时新增 relaxed diagnostic metrics，用于区分“严格不匹配”和“接近正确”的误差类型，方便论文分析与调参。
- 新增五轮优化执行与汇总文档、单轮运行脚本、实验报表脚本，以及图谱导出与可视化辅助工具，方便复现实验与论文展示。
- 补充了覆盖 preprocessing、attachment、graph、router、experiments、reporting 等关键模块的测试，当前仓库测试可稳定通过。

The active paper-facing setup is:

- O&M manuals only
- three current domains: `battery`, `cnc`, `nev`
- fixed backbone
- `full_llm` as the recommended runtime variant
- manual gold planned for final paper metrics

## Documentation

- `docs/SYSTEM_DESIGN.md`
  Current architecture rules and runtime phases
- `docs/PIPELINE_INTEGRATION.md`
  Commands, verification checkpoints, and validation notes
- `docs/PROJECT_ARCHITECTURE.md`
  Repository layout and module ownership
- `docs/EXECUTION_MEMORY.md`
  Latest fixes, validated runs, and next priorities
- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
  Human gold protocol for publication-grade evaluation
- `docs/REAL_RUN_DATA_FLOW_OM_3DOMAIN_20260418.md`
  Main real-run document for the current three-domain O&M setup

## Pipeline Flow

```text
markdown O&M -> EvidenceRecord -> fixed backbone -> retrieval -> attachment -> filtering -> graph assembly -> validation -> snapshots -> export
```

## Recommended Commands

Preprocess raw O&M markdown:

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.json
```

Run the main pipeline:

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.json
```

## Current Status

Verified on 2026-04-18:

- preprocessing succeeded on all three current O&M documents
- BOM-contaminated markdown input was cleaned correctly
- MemoryBank retrieval no longer duplicates historical hits
- the adapted three-domain O&M pipeline completed repeated real runs successfully

Best dense verified run:

- `artifacts/deepseek-20260418T095937Z`

Latest confirmation run:

- `artifacts/deepseek-20260418T105526Z`

## Current Evaluation Position

- auto-generated references should be treated as silver
- main paper metrics should come from a human-adjudicated gold subset

See:

- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
