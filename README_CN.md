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
  preprocessing/
    processor.py             # 预处理主处理器
    extractor.py             # LLM 提取包装
    parser.py                # Markdown 解析器
    models.py                # 预处理数据模型
  rules/
    filtering.py             # Attachment 过滤（v2：hypernym 回退）
  backends/
    llm.py                   # LLM 后端
    embeddings.py            # Embedding 后端
    faiss_cache.py           # FAISS 缓存
  temporal/                  # 可选 lifecycle / temporal 支持
  experiments/
    metrics/                 # 图谱评测指标
    downstream/              # 面向下游任务设计
  data/
    battery_om_manual_en/    # Battery O&M 源文档
    cnc_om_manual_en/        # CNC O&M 源文档
    ev_om_manual_en/         # NEV O&M 源文档
    evidence_records/        # 按域 evidence record JSON
    ground_truth/            # 人工标注（9 个文件）
  config/
    persistent/              # 稳定运行时配置
    prompts/                 # LLM 提取和 attachment 提示词
  docs/                      # 架构与设计文档
  tests/                     # 单元测试（19 个：12 v1 + 7 v2）
  scripts/                   # 回归测试脚本
```

## 当前配置结构

人工维护配置统一放在 `config/persistent/`：

- `pipeline.base.yaml` -- v2：15 概念 backbone
- `pipeline.deepseek.yaml` -- deepseek 预设
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json` -- v2：Tier-1 上位词纳入允许类型

默认推荐的外部大模型后端是 `deepseek-chat`。

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

## 实验目录

`experiments/` 保留两个活跃方向：

- `experiments/metrics/`
  当前主线图谱评测与图质量诊断
- `experiments/downstream/`
  面向下游任务的协议设计、样本格式和 benchmark 模板

论文主要指标：

- `workflow_step_f1`、`workflow_sequence_f1`、`workflow_grounding_f1`
- `anchor_accuracy`、`anchor_macro_f1`

v2 诊断指标：

- `hypernym_coverage` -- 语义节点中拥有 shared_hypernym 的比例
- `phase_distribution` -- observe/diagnose/repair/verify 分布

### v2 回归实验结果（2026-04-25）

三次测试均使用真实 API 调用（DeepSeek + DashScope），无 fallback：

| 测试 | 文档数 | 领域 | 节点 | 边 | Hypernym 覆盖率 | 主要上位词 |
|------|--------|------|------|-----|-----------------|-----------|
| Test 1 | 1 | battery | 41 | 30 | 14.7% | Housing:3, Seal:1, Fastener:1 |
| Test 2 | 3 | battery | 33 | 31 | 23.1% | Housing:4, Seal:1, Fastener:1 |
| Test 2 | 3 | cnc | 54 | 44 | **71.7%** | Coolant:15, Fastener:9, Connector:4 |
| Test 2 | 3 | nev | 56 | 62 | 29.8% | Seal:8, Connector:2, Coolant:2 |
| Test 3 | 9 | battery | 114 | 103 | **49.5%** | Housing:13, Media:11, Power:9 |
| Test 3 | 9 | cnc | 142 | 140 | 32.8% | Coolant:15, Fastener:9, Connector:4 |
| Test 3 | 9 | nev | 153 | 164 | 28.1% | Seal:11, Connector:9, Coolant:5 |

9 文档规模下，10 个 Tier-1 上位词中有 7 个在三个领域全部出现，证实了跨域泛化能力。详见 [docs/EXPERIMENT_REPORT.md](docs/EXPERIMENT_REPORT.md)。

## 文档入口

- [docs/README.md](docs/README.md)
- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) -- 架构规则与 v2 模型扩展
- [docs/PIPELINE_DATA_FLOW.md](docs/PIPELINE_DATA_FLOW.md) -- 端到端数据流
- [docs/DATA_FLOW_DIAGRAM.md](docs/DATA_FLOW_DIAGRAM.md) -- 真实单文档数据流示例（含各阶段格式变化）
- [docs/WORKFLOW_KG_DESIGN.md](docs/WORKFLOW_KG_DESIGN.md) -- 双层图设计与 v2 创新
- [docs/EXPERIMENT_REPORT.md](docs/EXPERIMENT_REPORT.md) -- v2 回归实验报告
- [docs/OPEN_SOURCE_UPDATE_CN.md](docs/OPEN_SOURCE_UPDATE_CN.md) -- v2 重构中文说明
- [docs/DATA_FLOW_DIAGRAM_CN.md](docs/DATA_FLOW_DIAGRAM_CN.md) -- 数据流图中文版
- [docs/EXPERIMENT_REPORT_CN.md](docs/EXPERIMENT_REPORT_CN.md) -- 回归实验报告中文版
