# CrossExtend-KG

[English](README.md) | 中文

## 2026-04-22 更新要点

- 当前主图已经改为“单图双层”结构。
- `workflow_step` 是真实的运维流程节点，使用 `node_layer="workflow"`。
- `Asset`、`Component`、`Signal`、`State`、`Fault` 等仍然属于语义层，使用 `node_layer="semantic"`。
- `Task` 只保留为旧版 human gold 的评测兼容投影，不再作为语义 attachment 的真实挂靠目标。
- `workflow_step -> workflow_step` 表示流程顺序，`workflow_step -> semantic node` 表示步骤触达的部件、状态、信号或故障对象。
- strict paper metrics 继续兼容现有 gold，新增 workflow diagnostics 用来展示流程链路可见性提升。

**面向工业运维表单的知识图谱构建系统**

---

## 目录

- [项目简介](#项目简介)
- [核心设计理念](#核心设计理念)
- [系统架构](#系统架构)
- [环境配置](#环境配置)
- [快速开始](#快速开始)
- [命令使用说明](#命令使用说明)
- [配置文件详解](#配置文件详解)
- [实验与评估](#实验与评估)
- [目录结构](#目录结构)
- [常见问题](#常见问题)

---

## 项目简介

CrossExtend-KG 是一个用于从工业运维（O&M）手册中自动构建知识图谱的研究项目。

### 解决的问题

工业运维手册（如电池维护手册、CNC机床操作手册、新能源汽车维修指南）包含大量结构化的故障诊断知识：

- **故障现象与原因的关联**（如"冷却液渗漏指示O-ring损坏"）
- **组件间的依赖关系**（如"电池包 → 冷却板 → 快接头 → O-ring"）
- **诊断步骤的执行顺序**（如"T1检查 → T2确认 → T3定位 → T4维修）

传统方法难以有效提取这些知识，CrossExtend-KG 通过以下方式解决：

1. **固定骨架 + 垂直扩展**：共享的顶层概念骨架确保跨领域一致性
2. **步骤感知提取**：识别运维表单中的步骤结构（T1, T2, T3...）
3. **可审计的节点准入**：明确记录每个概念的接受/拒绝决策及其理由

### 应用场景

- 故障诊断知识库构建
- 维修流程知识管理
- 跨领域知识迁移研究

---

## 核心设计理念

### 1. 固定骨架（Fixed Backbone）

系统预设11个顶层概念，所有新概念必须挂载到这些骨架节点下：

```
Asset（资产）      → 设备、生产线、机器人、电池包
Component（组件）  → 轴承、传感器、冷却模块、O-ring
Process（过程）    → 充电流程、诊断流程、维护工作流
Task（任务）       → 检查任务、校准任务、维修任务
Signal（信号）     → 警告、传感器读数、振动信号
State（状态）      → 正常状态、异常状态、停机状态
Fault（故障）      → 故障、缺陷、损坏、偏差
MaintenanceAction（维修动作） → 更换、复位、校准
Incident（事件）   → 故障事件、停机事件、安全事件
Actor（角色）      → 技术员、操作员、工程师
Document（文档）   → 报告、工单、手册、日志
```

### 2. 垂直扩展（Vertical Specialization）

新概念通过以下三种路径之一处理：

| 路径 | 说明 | 示例 |
|------|------|------|
| `reuse_backbone` | 直接复用骨架概念 | "设备" → Asset |
| `vertical_specialize` | 在骨架下创建子概念 | "快接头" → Component 的子概念 |
| `reject` | 拒绝入图 | 文档标题、人名角色等低价值概念 |

### 3. 无回退原则（No Fallback）

系统在关键阶段失败时**显式报错**，而非静默降级：

- 预处理失败 → 停止并报错
- LLM提取失败 → 停止并报错
- 配置缺失 → 停止并报错

这确保输出可审计，避免"看起来跑了但结果不可靠"的情况。

---

## 系统架构

### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        输入层                                    │
│  O&M Markdown 文档（电池/CNC/新能源汽车运维手册）                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     预处理阶段                                    │
│  1. 文档解析（识别步骤 T1, T2, T3...）                           │
│  2. LLM 提取候选概念和关系                                        │
│  3. 输出 EvidenceRecord（步骤级证据记录）                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     图谱构建阶段                                  │
│  1. 加载 EvidenceRecord → 按领域聚合 SchemaCandidate             │
│  2. 构建固定 Backbone（11个顶层概念 + 描述向量）                  │
│ 3. 向量检索 → 找到最相似的骨架节点                                │
│  4. Attachment 决策 → reuse/vertical_specialize/reject          │
│  5. 规则过滤 → 拒绝低价值节点，保留诊断相关概念                    │
│  6. 图组装 → 生成 GraphNode + GraphEdge                         │
│  7. 关系验证 → 检查关系是否符合约束规则                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     输出层                                       │
│  DomainGraph（领域图谱） + Snapshots（时序快照）                  │
│  + Artifacts（审计日志、接受/拒绝清单）                           │
└─────────────────────────────────────────────────────────────────┘
```

### 关系约束

系统定义了5类关系族，每类有特定的语义约束：

| 关系族 | 说明 | 允许的边类型 |
|--------|------|-------------|
| `task_dependency` | 任务依赖关系 | Task→Task, Task→Signal, Task→Component |
| `communication` | 诊断信号关系 | Signal→Fault, Signal→State, Signal→Component |
| `propagation` | 故障传播关系 | Fault→Fault, Component→Fault |
| `lifecycle` | 生命周期关系 | State→State, Incident→MaintenanceAction |
| `structural` | 结构组成关系 | Asset→Component, Component→Component |

---

## 环境配置

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 配置 API 密钥

在环境变量中设置 LLM API 密钥：

```bash
# DeepSeek（推荐）
export DEEPSEEK_API_KEY="your-api-key"

# 或其他兼容 OpenAI 格式的 API
export OPENAI_API_KEY="your-api-key"
```

### 3. 配置向量模型

默认使用本地 Ollama 运行的 `bge-m3` 模型：

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取 bge-m3 模型
ollama pull bge-m3:latest

# 启动 Ollama 服务（默认端口 11434）
ollama serve
```

如果使用其他向量服务，修改 `config/persistent/embedding_backends.yaml`。

---

## 快速开始

### 一键运行

```bash
# 1. 预处理（将 Markdown 转为 EvidenceRecord）
python -m crossextend_kg.cli preprocess

# 2. 构建图谱
python -m crossextend_kg.cli run

# 3. 查看输出
ls artifacts/
```

### 输出文件

运行后会在 `artifacts/` 目录生成：

```
artifacts/
  deepseek_YYYYMMDD_HHMMSS/
    battery/
      graph.json           # 电池领域图谱
      accepted_candidates.json  # 接受的概念
      rejected_candidates.json  # 拒绝的概念
      snapshot_T1.json     # 步骤快照
    cnc/
      ...
    nev/
      ...
    latest_summary.json    # 运行摘要
    data_flow_trace.json   # 数据流追踪
```

---

## 命令使用说明

### CLI 主命令

```bash
python -m crossextend_kg.cli <command> [options]
```

#### `preprocess` - 预处理命令

将原始 Markdown 文档转换为 EvidenceRecord。

```bash
python -m crossextend_kg.cli preprocess \
  --config config/persistent/preprocessing.deepseek.yaml \
  --data-root ./data \
  --domain-ids battery cnc nev \
  --output-path ./data/evidence_records
```

参数说明：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--config` | `preprocessing.deepseek.yaml` | 预处理配置文件路径 |
| `--data-root` | 配置文件中的值 | 数据根目录 |
| `--domain-ids` | 配置文件中的值 | 要处理的领域 ID |
| `--output-path` | 配置文件中的值 | EvidenceRecord 输出目录 |
| `--role` | `target` | 领域角色（当前统一为 target） |

#### `run` - 构建图谱

运行完整的知识图谱构建流程。

```bash
python -m crossextend_kg.cli run \
  --config config/persistent/pipeline.deepseek.yaml \
  --variants full_llm \
  --regenerate
```

参数说明：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--config` | `pipeline.deepseek.yaml` | Pipeline 配置文件路径 |
| `--variants` | 配置文件中的所有变体 | 要运行的变体 ID 列表 |
| `--regenerate` | False | 强制重新生成（忽略缓存） |
| `--no-export` | False | 不导出 artifacts |

#### `replay` - 加载快照状态

查看特定快照的图谱状态。

```bash
python -m crossextend_kg.cli replay \
  --run-dir artifacts/deepseek_20260421_120000 \
  --domain battery \
  --snapshot snapshot_T1.json
```

#### `rollback` - 回滚到快照

恢复到特定快照的图谱状态（用于调试或修正）。

```bash
python -m crossextend_kg.cli rollback \
  --run-dir artifacts/deepseek_20260421_120000 \
  --domain battery \
  --snapshot snapshot_T1.json
```

---

### 实验脚本

#### 运行消融实验

```bash
python -m crossextend_kg.experiments.ablation.runner \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir artifacts/ablation \
  --ground-truth-dir data/ground_truth \
  --data-root ./data
```

当前论文主线默认运行的消融变体包括：

| 变体 ID | 说明 |
|---------|------|
| `full_llm` | 主线系统 |
| `no_preprocessing_llm` | 规则预处理替代 LLM 预处理 |
| `no_rule_filter` | 无规则过滤 |
| `no_embedding_routing` | 无向量检索 |
| `no_attachment_llm` | 用确定性 attachment 替代 LLM attachment |
| `embedding_top1` | 用 embedding top-1 替代 LLM attachment |

说明：

- `no_snapshots`、`no_temporal_metadata`、`no_lifecycle_events`、`no_relation_constraints` 及 relation-family 删除变体属于诊断性消融，不进入当前论文主表。

#### 运行 Baseline 对比

```bash
python scripts/run_baselines.py \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir artifacts/baselines \
  --ground-truth-dir data/ground_truth \
  --data-root ./data
```

Baseline 包括：

| Baseline | 说明 |
|----------|------|
| `rule_pipeline` | 纯规则方法 |
| `llm_direct_graph` | 单提示 LLM 直接生成图谱 |

说明：

- 仓库中仍保留 `spacy` / `direct_llm` 草稿辅助模块，但它们没有接入当前 `run_baseline_suite`，不应作为当前论文主线 baseline 口径。

#### 重复运行统计显著性测试

```bash
python scripts/run_repeated_experiments.py \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir artifacts/repeated \
  --ground-truth-dir data/ground_truth \
  --repeats 5 \
  --include-baselines \
  --data-root ./data
```

---

## 配置文件详解

### 配置文件结构

```
config/persistent/
  ├── pipeline.base.yaml          # 基础 pipeline 配置（骨架、关系约束）
  ├── pipeline.deepseek.yaml      # DeepSeek 模型配置（继承 base）
  ├── pipeline.deepseek.battery_only.yaml  # 单领域调试配置
  ├── pipeline.deepseek_full.yaml # 多变体压力测试配置
  ├── preprocessing.base.yaml     # 预处理基础配置
  ├── preprocessing.deepseek.yaml # 预处理 DeepSeek 配置
  ├── llm_backends.yaml           # LLM 后端注册表
  ├── embedding_backends.yaml     # 向量后端注册表
  └── relation_constraints.json   # 关系约束规则
```

### 配置继承机制

配置文件支持 `extends` 继承，避免重复定义：

```yaml
# pipeline.deepseek.yaml
extends: ./pipeline.base.yaml

llm_backend_id: deepseek
embedding_backend_id: dashscope_text_embedding_v4
benchmark_name: deepseek_experiment

runtime:
  run_prefix: deepseek
```

继承后只需指定差异部分，其余从 `pipeline.base.yaml` 读取。

### LLM 后端配置

```yaml
# llm_backends.yaml
default_backend: deepseek

backends:
  deepseek:
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}   # 从环境变量读取
    model: deepseek-reasoner
    timeout_sec: 1200
    max_tokens: 8192
    temperature: 0.0

  deepseek_chat:
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}
    model: deepseek-chat
    timeout_sec: 600
    max_tokens: 4096
    temperature: 0.1
```

### 向量后端配置

```yaml
# embedding_backends.yaml
default_backend: dashscope_text_embedding_v4

backends:
  dashscope_text_embedding_v4:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: ${TONGYI_API_KEY}
    model: text-embedding-v4
    timeout_sec: 300
    dimensions: 1024
```

### 如何切换模型

#### 方法 1：创建新配置文件

```yaml
# config/persistent/pipeline.my_model.yaml
extends: ./pipeline.base.yaml

llm_backend_id: my_model
embedding_backend_id: my_embedding
```

然后在 `llm_backends.yaml` 中添加：

```yaml
backends:
  my_model:
    base_url: https://api.my-provider.com
    api_key: ${MY_API_KEY}
    model: my-model-name
    timeout_sec: 600
    max_tokens: 4096
    temperature: 0.1
```

#### 方法 2：直接运行时指定

```bash
python -m crossextend_kg.cli run \
  --config config/persistent/pipeline.my_model.yaml
```

### 领域配置

在 `pipeline.base.yaml` 中定义领域：

```yaml
domains:
  - domain_id: battery
    domain_name: Battery System
    role: target
    data_path: ../../data/evidence_records/battery_evidence_records_llm.json
    source_types:
      - om_manual
    domain_keywords:
      - battery
      - pack
      - cell
      - cooling

  - domain_id: cnc
    domain_name: CNC Machine
    role: target
    data_path: ../../data/evidence_records/cnc_evidence_records_llm.json
    source_types:
      - om_manual

  - domain_id: nev
    domain_name: New Energy Vehicle
    role: target
    data_path: ../../data/evidence_records/nev_evidence_records_llm.json
    source_types:
      - om_manual
```

---

## 实验与评估

### 评估指标

系统提供两类指标：

#### 图谱质量指标（核心）

| 指标 | 说明 |
|------|------|
| Entity Precision | 实体召回正确率 |
| Entity Recall | 实体覆盖率 |
| Entity F1 | 实体综合指标 |
| Relation Precision | 关系召回正确率 |
| Relation Recall | 关系覆盖率 |
| Relation F1 | 关系综合指标 |

#### 下游诊断性探针（非论文主指标）

| 指标 | 说明 |
|------|------|
| Fault Diagnosis Accuracy | 故障诊断准确率 |
| Repair Step Accuracy | 维修步骤准确率 |
| Component Dependency Recall | 组件依赖召回率 |

说明：这些结果当前只用于 graph coverage / path probe 级别的诊断分析，不应用作论文主结论中的 end-task QA 证据。

### Gold 标准

评估使用人工标注的 Gold 标准，位于：

```
data/ground_truth/
  ├── battery_BATOM_001.json   # 电池案例 1
  ├── battery_BATOM_002.json   # 电池案例 2
  ├── battery_BATOM_003.json   # 电池案例 3
  ├── cnc_CNCOM_001.json       # CNC 案例 1
  ├── cnc_CNCOM_002.json       # CNC 案例 2
  ├── cnc_CNCOM_003.json       # CNC 案例 3
  ├── nev_EVMAN_001.json       # 新能源汽车案例 1
  ├── nev_EVMAN_002.json       # 新能源汽车案例 2
  ├── nev_EVMAN_003.json       # 新能源汽车案例 3
```

每个 Gold 文件包含人工标注的实体和关系列表。

### 运行评估

```bash
# 运行完整实验流程（消融 + baseline + 重复实验）
python scripts/run_baselines.py --config config/persistent/pipeline.deepseek.yaml
python -m crossextend_kg.experiments.ablation.runner --config config/persistent/pipeline.deepseek.yaml
python scripts/run_repeated_experiments.py --config config/persistent/pipeline.deepseek.yaml --repeats 3
```

---

## 目录结构

```
crossextend_kg/
│
├── backends/                # 后端实现
│   ├── llm.py               # LLM 调用封装
│   ├── embeddings.py        # 向量模型封装
│
├── config/                  # 配置文件
│   ├── persistent/          # 持久化配置（YAML）
│   │   ├── pipeline.base.yaml
│   │   ├── pipeline.deepseek.yaml
│   │   ├── preprocessing.base.yaml
│   │   ├── preprocessing.deepseek.yaml
│   │   ├── llm_backends.yaml
│   │   ├── embedding_backends.yaml
│   │   └── relation_constraints.json
│   ├── prompts/             # LLM 提示模板
│   └── templates/           # 配置模板
│
├── data/                    # 数据目录
│   ├── battery/             # 电池原始数据
│   ├── cnc/                 # CNC 原始数据
│   ├── nev/                 # 新能源汽车原始数据
│   ├── evidence_records/    # 预处理输出的 EvidenceRecord
│   └── ground_truth/        # 人工 Gold 标准
│
├── docs/                    # 文档
│   ├── SYSTEM_DESIGN.md     # 系统设计说明
│   ├── PIPELINE_INTEGRATION.md  # Pipeline 集成说明
│   └── PROJECT_ARCHITECTURE.md  # 项目架构说明
│
├── experiments/             # 实验框架
│   ├── ablation/            # 消融实验
│   ├── baselines/           # Baseline 方法
│   ├── comparison/          # 对比分析
│   ├── metrics/             # 评估指标
│   └── rounds.py            # 实验轮次管理
│
├── pipeline/                # 核心 Pipeline
│   ├── runner.py            # 运行入口
│   ├── evidence.py          # Evidence 加载
│   ├── backbone.py          # Backbone 构建
│   ├── router.py            # 向量检索路由
│   ├── attachment.py        # Attachment 决策
│   ├── graph.py             # 图组装
│   ├── artifacts.py         # 输出导出
│   └── relation_validation.py  # 关系验证
│
├── preprocessing/           # 预处理模块
│   ├── parser.py            # 文档解析
│   ├── extractor.py         # LLM 提取
│   └── processor.py         # 处理流程
│
├── rules/                   # 规则模块
│   ├── filtering.py         # 节点过滤规则
│
├── scripts/                 # 实验脚本
│   ├── run_baselines.py
│   ├── run_repeated_experiments.py
│   ├── run_ablation.py
│   └── compute_metrics.py
│
├── artifacts/               # 输出目录（运行后生成）
│
├── cli.py                   # CLI 入口
├── config.py                # 配置加载
├── models.py                # 数据模型定义
└── exceptions.py            # 异常定义
```

---

## 常见问题

### Q1: LLM 调用超时怎么办？

检查 `llm_backends.yaml` 中的 `timeout_sec` 设置，增大超时时间：

```yaml
backends:
  deepseek:
    timeout_sec: 1800  # 增大到 30 分钟
```

### Q2: 向量检索失败怎么办？

确认 Ollama 服务已启动：

```bash
# 检查 Ollama 服务状态
curl http://127.0.0.1:11434/api/tags

# 如果失败，启动服务
ollama serve
```

### Q3: 如何只处理单个领域？

使用单领域配置：

```bash
python -m crossextend_kg.cli run \
  --config config/persistent/pipeline.deepseek.battery_only.yaml
```

### Q4: 如何查看被拒绝的概念？

查看输出目录中的 `rejected_candidates.json`：

```bash
cat artifacts/deepseek_*/battery/rejected_candidates.json
```

每个被拒绝的概念都有 `reason` 字段说明拒绝理由。

### Q5: 如何添加新的领域？

1. 在 `pipeline.base.yaml` 的 `domains` 中添加新领域配置：

```yaml
domains:
  - domain_id: new_domain
    domain_name: New Domain
    role: target
    data_path: ../../data/evidence_records/new_domain_evidence_records_llm.json
    source_types:
      - om_manual
    domain_keywords:
      - keyword1
      - keyword2
```

2. 在 `preprocessing.base.yaml` 中添加预处理配置

3. 准备原始数据到 `data/new_domain/`

4. 运行预处理和 Pipeline

### Q6: 消融实验结果在哪里？

```bash
ls artifacts/ablation/
```

每个消融变体会有独立的子目录。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/SYSTEM_DESIGN.md` | 系统设计原则、核心规则 |
| `docs/PIPELINE_INTEGRATION.md` | Pipeline 各阶段详解 |
| `docs/PROJECT_ARCHITECTURE.md` | 项目架构、模块职责 |
| `docs/FIVE_ROUND_OPTIMIZATION_REPORT.md` | 五轮优化报告 |
| `docs/FIVE_ROUND_OPTIMIZATION_REPORT_CN.md` | 五轮优化报告（中文） |

---

## 开发与贡献

### 本地开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 当前仓库没有提交 tests/ 目录；使用语法检查和真实运行验证
python -m py_compile cli.py config.py models.py pipeline\\runner.py pipeline\\graph.py preprocessing\\processor.py rules\\filtering.py

# 代码格式检查
ruff check .
```

### 版本要求

- Python >= 3.10
- 依赖见 `pyproject.toml` 或 `setup.py`

---

## 许可证

MIT License

---

## 更新日志

### 2026-04-20

- 重构配置系统：从 JSON 预设转为分层 YAML 配置
- 添加配置继承机制（`extends`）
- 将 LLM 和 Embedding 模型选择拆分到独立后端注册表
- 适配 O&M 表单数据目录命名
- 增强包模式导入稳定性

---

**如有问题，请查阅文档或提交 Issue。**
