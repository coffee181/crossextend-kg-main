# CrossExtend-KG

[English](README.md)

CrossExtend-KG 是一个面向工业运维手册的知识图谱构建项目。当前主线已经收敛为面向论文与开源交付的 workflow-first 双层图方案，v2 重构增加了跨域泛化、时序回溯和复杂传播路径三个创新支撑。

## 当前范围

- 输入类型：`om_manual`
- 有效领域：`battery`、`cnc`、`nev`
- 图谱形态：`单图双层`
- 最高原则：`no fallback`
- 数据模型版本：`v2`（向后兼容 v1）

## 当前图谱设计

### Workflow 层
- `workflow_step` 是真实流程节点
- `workflow_step -> workflow_step` 表示流程顺序（sequence 边）
- `workflow_step -> semantic node` 表示步骤触达对象（action_object 边）
- 每个步骤携带 `step_phase`：observe / diagnose / repair / verify

### 语义层
- 固定 backbone：5 个基础类型 + 10 个 Tier-1 上位词锚点
  - 基础：`Asset`、`Component`、`Signal`、`State`、`Fault`
  - Tier-1：`Seal`、`Connector`、`Sensor`、`Controller`、`Coolant`、`Actuator`、`Power`、`Housing`、`Fastener`、`Media`
- `Task` 只保留为旧版评测兼容投影，不再作为真实语义挂靠目标
- 语义节点可携带 `shared_hypernym` 用于跨域映射
- 语义层边负责结构、通信、传播和生命周期支撑

### v2 创新支撑点
1. **跨域泛化**：`shared_hypernym` 实现跨域概念一致性映射（如 "O-ring"/"cover gasket"/"door seal" 都映射到 `Seal`）
2. **时序回溯**：`step_phase` 分类步骤意图；`state_transitions` 捕获生命周期状态变更；`procedure_meta` 记录文档级元数据
3. **复杂传播路径**：`diagnostic_edges` 分离通信/传播证据；`cross_step_relations` 跨步骤链接概念用于推理

## 主线链路

```text
O&M markdown
  -> 预处理（v2：上位词 + 阶段 + 诊断提取）
  -> 按 step 切分的 evidence records（v2 字段 + v1 回退）
  -> 语义候选聚合（hypernym -> routing_features）
  -> 15 概念固定 backbone 路由
  -> attachment 决策
  -> 规则过滤（hypernym 作为 anchor 回退）
  -> 双层图组装（v2 字段消费 + 回退）
  -> GraphML / JSON 导出（v2 属性）
  -> human gold 评测
```

## 项目结构

```
crossextend_kg/
  cli.py                     # CLI 入口
  config.py                  # 配置加载
  models.py                  # 数据模型（v1 + v2）
  file_io.py                 # JSON/CSV I/O 工具
  pipeline/
    evidence.py              # 证据加载、规范化、候选聚合
    backbone.py              # Backbone 构建
    graph.py                 # 双层图组装
    artifacts.py             # 产物导出
    exports/graphml.py       # GraphML 导出
    utils.py                 # 运行时工具
    router.py                # Embedding backbone 路由
    attachment.py            # Attachment 决策（规则/LLM）
    relation_validation.py   # 关系类型校验
    runner.py                # Pipeline 编排
  preprocessing/
    processor.py             # 预处理主处理器
    extractor.py             # LLM 提取包装
    parser.py                # Markdown 解析器
    models.py                # 预处理数据模型
  rules/
    filtering.py             # Attachment 过滤（v2：hypernym 回退）
    relation_filtering.py    # 关系过滤规则
  backends/
    llm.py                   # LLM 后端
    embeddings.py            # Embedding 后端
    faiss_cache.py           # FAISS 缓存
  temporal/                  # 可选 lifecycle / temporal 支持
    versioning.py
    lifecycle.py
    consistency.py
  data/
    battery_om_manual_en/    # Battery O&M 源文档（100 篇）
    cnc_om_manual_en/        # CNC O&M 源文档（100 篇）
    ev_om_manual_en/         # NEV O&M 源文档（200 篇）
    evidence_records/        # Evidence record JSON（全量 + 按域）
    ground_truth/            # 人工标注 gold（9 个文件）
  config/
    persistent/              # 稳定运行时配置（12 个 YAML/JSON）
    prompts/                 # LLM 提取和 attachment 提示词
  docs/                      # 架构与设计文档（8 个文档）
  tests/                     # 单元测试（19 个：12 v1 + 7 v2）
  scripts/                   # 测试、评估和全量运行脚本
    regression_test1.py      # 单文档测试
    regression_test2.py      # 三文档测试
    regression_test3.py      # 九文档测试
    evaluate_attachment_gold.py  # Attachment gold 评估
    run_full_preprocess.py   # 全量 400 文档预处理入口
    run_cnc_preprocess.py    # CNC+battery 200 文档预处理入口
```

## 当前配置结构

人工维护配置统一放在 `config/persistent/`：

- `pipeline.base.yaml` -- v2：15 概念 backbone
- `pipeline.full.yaml` -- 全量（400 文档）实验配置
- `pipeline.test3.yaml` -- 九文档测试（每域 3 个）
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json` -- v2：Tier-1 上位词纳入允许类型

默认推荐大模型后端：全量实验用 `deepseek-v4-pro`，轻量测试用 `deepseek-v4-flash`。

如需切换模型，直接修改 `config/persistent/llm_backends.yaml` 即可。现有
preset 已经统一使用 `llm_backend_id: deepseek`，所以只要修改
`backends.deepseek.model`，`preprocess` 和 `run` 都会一起切换。如果要同
时保留多个可选模型，就在 `llm_backends.yaml` 里新增一个 backend 条目，
再把对应 preset 的 `llm_backend_id` 改过去。只修改 `default_backend` 本
身，不会影响那些已经显式设置了 `llm_backend_id` 的 preset。

## 常用命令

预处理：

```bash
python -m crossextend_kg.cli preprocess --config config/persistent/preprocessing.deepseek.yaml
```

运行全领域主线：

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml
```

只运行指定领域：

```bash
python -m crossextend_kg.cli run --config config/persistent/pipeline.deepseek.yaml --domains battery
```

评估单个图：

```bash
python -m crossextend_kg.cli evaluate --gold data/ground_truth/battery_BATOM_002.json --graph artifacts/some_run/full_llm/working/battery/final_graph.json
```

评估整次运行：

```bash
python -m crossextend_kg.cli evaluate --run-root artifacts/some_run --variant full_llm --ground-truth-dir data/ground_truth
```

## 实验与结果

### 核心评测指标

- `workflow_step_f1`、`workflow_sequence_f1`、`workflow_grounding_f1`
- `anchor_accuracy`、`anchor_macro_f1`

v2 诊断指标：

- `hypernym_coverage` -- 语义节点中拥有 shared_hypernym 的比例
- `phase_distribution` -- observe/diagnose/repair/verify 分布

### 全量预处理（2026-05-02）：400 篇文档

| 领域 | 文档数 | 状态 |
|------|--------|------|
| battery | 100 | 完成 |
| cnc | 100 | 完成 |
| ev (nev) | 200 | 完成 |
| **合计** | **400** | **完成** |

- **模型**：`deepseek-v4-pro`（DeepSeek API）
- **总耗时**：59.4 小时（约 2.5 天）
- **平均速率**：535s/篇（8.9 分钟/篇）
- **合并输出**：`data/evidence_records/evidence_records_llm.json`（20.6 MB）
- **按域输出**：battery (5.0 MB), cnc (5.2 MB), ev (10.6 MB)
- **API 可靠性**：2-3 次临时 JSON 解析失败，均自动恢复

```bash
python -m scripts.run_full_preprocess
```

配置：`preprocessing.deepseek.yaml` → `llm_backends.yaml` (`deepseek-v4-pro`)

### 人工标注 Attachment Gold（2026-04-26）

9 个人工标注的 attachment gold 文件（共 359 个概念）：

| 领域 | 文档 | 概念数 | 主要锚点 |
|------|------|--------|----------|
| battery | Busbar 绝缘护罩检查 | 30 | Housing:6, Component:8 |
| battery | Busbar 表面污染检查 | 32 | Component:8, Media:4 |
| battery | 压缩垫位置审计 | 24 | Component:9, Fault:9 |
| cnc | 主轴冷却软管泄漏检查 | 42 | Component:14, Signal:7 |
| cnc | 主轴拉杆夹紧力验证 | 40 | Signal:17, Component:9 |
| cnc | 主轴热机振动确认 | 50 | Signal:17, Fault:11 |
| nev | 冷却液快换接头更换 | 40 | Signal:11, Fault:5 |
| nev | BMS 外壳密封更换 | 49 | Fault:12, Signal:10 |
| nev | 驱动电机冷却软管泄漏确认 | 52 | Signal:19, Fault:10 |

### v2 回归实验结果（2026-04-26）

基于规则的 attachment（确定性，无需 LLM/Embedding），全部通过：

| 测试 | 文档数 | 领域 | 节点 | 边 | 接受三元组 |
|------|--------|------|------|-----|-----------|
| Test 1 | 1 | battery | 59 | 69 | 32 |
| Test 2 | 3 | battery | 48 | 57 | 31 |
| Test 2 | 3 | cnc | 68 | 90 | 45 |
| Test 2 | 3 | nev | 73 | 115 | 66 |
| Test 3 | 9 | battery | 132 | 206 | 110 |
| Test 3 | 9 | cnc | 160 | 275 | 156 |
| Test 3 | 9 | nev | 173 | 314 | 181 |

Test 3 汇总：**465 节点, 795 边, 447 接受三元组**。
Attachment 接受率: 348/349 (99.7%)。跨域 Hypernym 一致性: 117/118 (99.2%)。

### 9文档消融实验：Embedding + LLM 变体（2026-04-26）

| 变体 | 节点 | 边 | 接受三元组 | 拒绝候选 |
|------|------|-----|-----------|---------|
| baseline_embedding_llm | 454 | 754 | 417 | 12 |
| **contextual_rerank_embedding_llm** | **461** | **776** | **432** | **5** |
| pure_llm | 459 | 772 | 430 | 7 |

- Contextual rerank 表现最佳：432 三元组，拒绝最少(5)
- NEV 域对路由策略最敏感：163 → 174 三元组 (+6.7%)
- CNC 域在所有变体下稳定 (148–151)

### 相比 v2 初始版本（2026-04-25）的改进

- 完成 9 文档 attachment gold 标注（v2 schema，15 backbone 概念，359 概念）
- 9 文档消融实验：baseline embedding vs contextual rerank vs pure LLM
- Backbone 从 6 扩展到 15 概念，支持 Tier-1 上位词
- Pipeline 改进：shared_hypernym 路由、step_phase 分类、workflow grounding 边修复
- 新增 attachment gold 评估脚本 (`scripts/evaluate_attachment_gold.py`)
- 回归测试脚本适配 v2 架构（test1/test2/test3）
- 基于规则的 attachment 在 1/3/9 文档规模上均验证通过

## 文档入口

- [docs/README.md](docs/README.md)
- [docs/PROJECT_INTRODUCTION_CN.md](docs/PROJECT_INTRODUCTION_CN.md) -- 完整项目介绍（中文）
- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) -- 架构规则与 v2 模型扩展
- [docs/PIPELINE_DATA_FLOW.md](docs/PIPELINE_DATA_FLOW.md) -- 端到端数据流
- [docs/DATA_FLOW_DIAGRAM.md](docs/DATA_FLOW_DIAGRAM.md) -- 真实单文档数据流示例（含各阶段格式变化）
- [docs/WORKFLOW_KG_DESIGN.md](docs/WORKFLOW_KG_DESIGN.md) -- 双层图设计与 v2 创新
- [docs/OPEN_SOURCE_UPDATE_CN.md](docs/OPEN_SOURCE_UPDATE_CN.md) -- v2 重构中文说明
- [docs/DATA_FLOW_DIAGRAM_CN.md](docs/DATA_FLOW_DIAGRAM_CN.md) -- 数据流图中文版
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) -- 可复现指南（含命令与预期结果）
