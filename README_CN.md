# CrossExtend-KG 中文说明

[English](README.md) | 中文

## 当前项目定位

`CrossExtend-KG` 当前聚焦于面向论文主线的 O&M 表单知识图谱构建链路，核心约束如下：

- 输入类型只保留 `om_manual`
- 当前数据域包含 `battery`、`cnc`、`nev`
- 运行时使用固定 backbone，不做动态扩展
- 推荐主方法变体为 `full_llm`
- 论文主指标以人工冻结 gold 子集为准
- 最高原则是 `no fallback`：不允许用兜底分支掩盖真实错误

## 本次相对上次的主要修改

- 将实验相关代码重构到 `experiments/metrics/`、`experiments/ablation/`、`experiments/comparison/` 目录下，主指标、诊断指标、消融实验和结果对比的职责边界更清楚。
- 新增并整理三领域 O&M 文档与人工冻结 gold 标注，`data/ground_truth/` 下的 9 份标注可直接被评测器发现并用于正式实验。
- 继续收紧预处理、attachment、filtering、graph assembly 的主线逻辑，重点减少低价值 concept、错误 structural relation 和不合理 lifecycle relation。
- 在预处理侧保留 `semantic_type_hint` 作为软先验，用于提升后续挂靠准确率，但不把它当成硬标签。
- 评测侧明确区分严格论文指标与诊断指标：严格指标用于论文结论，relaxed diagnostics 用于解释“接近正确但未严格匹配”的误差。
- 增加五轮优化执行框架、轮次报告生成脚本、图谱导出与可视化脚本，方便做单文档到多文档的可复现实验。
- 补充了覆盖 preprocessing、attachment、graph、router、experiments、reporting 等模块的测试，当前测试可稳定通过。

## 文档入口

- `docs/SYSTEM_DESIGN.md`
  当前系统设计、阶段划分和强约束
- `docs/PIPELINE_INTEGRATION.md`
  端到端命令、检查点和验证方式
- `docs/PROJECT_ARCHITECTURE.md`
  仓库结构与模块职责
- `docs/EXECUTION_MEMORY.md`
  最近修复、有效运行和后续优先级
- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
  论文用人工 gold 标注规范
- `docs/REAL_RUN_DATA_FLOW_OM_3DOMAIN_20260418.md`
  当前三域 O&M 真实运行链路说明
- `docs/FIVE_ROUND_OPTIMIZATION_REPORT.md`
  五轮自动优化的完整英文报告
- `docs/FIVE_ROUND_OPTIMIZATION_REPORT_CN.md`
  五轮自动优化的中文整理版报告

## 当前链路

```text
O&M markdown -> EvidenceRecord -> fixed backbone -> retrieval -> attachment -> filtering -> graph assembly -> validation -> snapshots -> export
```

## 推荐命令

预处理：

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.json
```

主流程：

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.json
```

多变体实验：

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek_full.json
```

## 当前状态

当前已经确认：

- 三个领域的 O&M 文档都能进入统一主线
- UTF-8 BOM 清理有效
- MemoryBank 检索已按 `memory_id` 去重
- O&M 步骤节点能稳定保留在 `Task`
- 历史上的 `product_intro` / `fault_case` 主链路已经移除
- 实验、评测、报告和测试结构已经与当前论文主线对齐

## 评测原则

- 自动生成参考只能视为 `silver`
- 论文主指标应基于人工标注并冻结后的 `gold` 子集
- 严格指标用于论文结论，诊断指标用于误差分析和调试

详见：

- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
