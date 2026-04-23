# CrossExtend-KG

[English](README.md)

CrossExtend-KG 是一个面向工业运维手册的知识图谱构建项目。当前主线已经收敛为面向论文与开源交付的 workflow-first 双层图方案，不再维护旧的多套实验分支和临时脚本。

## 当前范围

- 输入类型：`om_manual`
- 有效领域：`battery`、`cnc`、`nev`
- 图谱形态：`单图双层`
- 最高原则：`no fallback`

## 当前图谱设计

- `workflow_step` 是真实流程节点。
- 语义层只保留 `Asset`、`Component`、`Signal`、`State`、`Fault`。
- `Task` 只保留为旧版评测兼容投影，不再作为真实语义挂靠目标。
- `workflow_step -> workflow_step` 表示流程顺序。
- `workflow_step -> semantic node` 表示步骤触达对象。
- 语义层边负责结构与诊断支撑。

## 主线链路

```text
O&M markdown
  -> 预处理
  -> 按 step 切分的 evidence records
  -> 语义候选聚合
  -> 固定 backbone 路由
  -> attachment 决策
  -> 规则过滤
  -> 双层图组装
  -> GraphML / JSON 导出
  -> human gold 评测
```

## 当前配置结构

人工维护配置统一放在 `config/persistent/`：

- `pipeline.base.yaml`
- `pipeline.deepseek.yaml`
- `preprocessing.base.yaml`
- `preprocessing.deepseek.yaml`
- `llm_backends.yaml`
- `embedding_backends.yaml`
- `relation_constraints.json`

默认推荐的外部大模型后端是 `deepseek-reasoner`。

## 常用命令

预处理：

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

运行全领域主线：

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```

只运行指定领域：

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --domains battery
```

评估单个图：

```bash
python -m crossextend_kg.cli evaluate --gold D:\crossextend_kg\data\ground_truth\battery_BATOM_002.json --graph D:\crossextend_kg\artifacts\some_run\full_llm\working\battery\final_graph.json
```

评估整次运行：

```bash
python -m crossextend_kg.cli evaluate --run-root D:\crossextend_kg\artifacts\some_run --variant full_llm --ground-truth-dir D:\crossextend_kg\data\ground_truth
```

## experiments 目录当前只保留两类内容

- `experiments/metrics/`
  当前主线图谱评测与图质量诊断
- `experiments/downstream/`
  面向下游任务的协议设计、样本格式和 benchmark 模板

当前优先的下游任务设计是：

- 证据驱动的 workflow retrieval
- repair suffix ranking

## 文档入口

- `docs/README.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/PIPELINE_DATA_FLOW.md`
- `docs/WORKFLOW_KG_DESIGN.md`
- `docs/DOWNSTREAM_EVALUATION.md`
- `docs/GRAPH_QUALITY_DIAGNOSIS.md`
