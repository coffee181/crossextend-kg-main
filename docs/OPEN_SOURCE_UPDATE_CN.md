# 开源更新说明（v2）

本文档说明 CrossExtend-KG v2 的更新内容、仓库边界和维护原则。

## v2 重构目标

v2 对证据数据模型和管线进行了结构性重构，解决三个问题：

1. `StepEvidenceRecord.relation_mentions` 把序列/操作/语义关系混在一个数组里
2. 无跨域泛化能力（缺少 `shared_hypernym`）
3. 无时序回溯和复杂传播路径建模能力（缺少 `step_phase`、`state_transitions`、`diagnostic_edges`）

## v2 核心变更

### 数据模型扩展

| 新增模型 | 用途 |
|---------|------|
| `StepAction` | 清晰的步骤-对象操作记录 |
| `StructuralEdge` | 独立的结构包含边 |
| `StateTransition` | 生命周期状态变更 |
| `DiagnosticEdge` | 通信/传播证据边 |
| `ProcedureMeta` | 文档级过程元数据 |
| `CrossStepRelation` | 跨步骤诊断推理关系 |

| 扩展模型 | 新增字段 | 作用 |
|---------|---------|------|
| `ConceptMention` | `shared_hypernym` | 跨域上位词分类（10个Tier-1类别） |
| `StepEvidenceRecord` | `step_phase`, `step_summary`, `step_actions[]`, `structural_edges[]`, `diagnostic_edges[]`, `state_transitions[]`, `sequence_next` | v2 步骤元数据 |
| `EvidenceRecord` | `procedure_meta`, `cross_step_relations[]` | 文档级元数据与跨步关系 |
| `GraphNode` | `shared_hypernym`, `step_phase` | v2 属性传播到图节点 |

### Backbone 扩展

从 6 个概念扩展到 15 个：

- **Tier 0**（基础语义类型）：`Asset`, `Component`, `Signal`, `State`, `Fault`
- **Tier 1**（跨域上位词锚点）：`Seal`, `Connector`, `Sensor`, `Controller`, `Coolant`, `Actuator`, `Power`, `Housing`, `Fastener`, `Media`

`Task` 已从 backbone 中移除。Workflow step 节点在图中保持为 `workflow_step`，仅在评测时投影为 `Task` 以兼容现有 gold truth。

### 管线更新

- **预处理**：LLM 提取 prompt 增加上位词分类表、step_phase 分类指导、state_transition 和 diagnostic_edge 提取规则
- **处理器**：`extraction_to_evidence_record` 填充所有 v2 字段，保留 v1 字段向后兼容
- **证据加载**：`aggregate_schema_candidates` 传播 `shared_hypernym` 到 `routing_features`
- **图组装**：优先消费 v2 字段，v2 为空时回退到 v1 字段
- **导出**：GraphML 新增 `shared_hypernym` 和 `step_phase` 属性；`final_graph.json` 新增 `hypernym_coverage` 和 `phase_distribution`
- **过滤**：`shared_hypernym` 作为 anchor fallback；Tier-1 hypernym 作为合法 parent anchor

### 向后兼容

所有 v2 字段都有默认值（None/空列表），v1 格式的 evidence records 可以无错加载，v2 字段自动为空。现有的 19 个单元测试（12 个 v1 + 7 个 v2）全部通过。

## 保留的开源主线

### 核心构图链路

- 预处理生成按步骤切分的 `EvidenceRecord`（v2 扩展字段）
- 15 概念固定 backbone 的语义路由与 attachment 决策
- workflow / semantic 双层图组装
- `final_graph.json` 与 GraphML 导出

### 仍属于主线的目录

- `backends/` -- 预处理、attachment 与 embedding 路由依然依赖
- `data/` -- 源文档、human gold 与 evidence records 依然依赖
- `temporal/` -- 可选 lifecycle / temporal 能力依然依赖
- `preprocessing/` -- v2 提取逻辑与 prompt

### 有效实验面

- `experiments/metrics/` -- 工作流优先评测主线
- `experiments/downstream/` -- workflow_retrieval + repair_suffix_ranking

### 开源必备文档

- `README.md` / `README_CN.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/PIPELINE_DATA_FLOW.md`
- `docs/WORKFLOW_KG_DESIGN.md`
- `docs/OPEN_SOURCE_UPDATE_CN.md`

### 回归测试

- `tests/test_workflow_dual_layer.py`（19 个测试：12 个 v1 + 7 个 v2）
- `scripts/regression_test1.py` / `test2.py` / `test3.py`

## 不推送到 GitHub 的内容

- `artifacts/`, `graphml/` 下的运行结果
- `data/faiss-data/`
- `results/` 下的回归测试结果
- 临时 evidence record 中间文件

## 仓库定位

- 一个以 workflow-first O&M KG 为核心的开源代码仓库
- 一个支持跨域泛化、时序回溯、复杂传播路径的知识图谱构建系统
- 一个强调 `no fallback`、主线清晰、v1/v2 向后兼容的可维护项目

## 协作原则

- 新功能优先进入主线代码，而不是新增一次性脚本
- 新实验优先复用 `cli.py` 与 `experiments/` 现有入口
- 新文档优先更新现有主文档，而不是再建历史性流水账
- 运行产物和缓存继续留在本地，不进入 Git 仓库
- v1 字段在验证全部通过后再清理，不在 v2 重构中删除
