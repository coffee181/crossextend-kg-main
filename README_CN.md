# CrossExtend-KG 中文文档

[English](README.md) | 中文

## 项目概述

`CrossExtend-KG` 用固定共享 backbone 和受控 attachment 链路来构建工业知识图谱。当前有效运行时只保留主架构：

- backbone 由 `backbone.seed_concepts` 预定义
- 可选共享补充概念只来自 `domains[].ontology_seed_path`
- 所有领域统一视为应用域，`role` 固定为 `target`
- 输出以结构构建结果为主，不再保留指标评测链路

## 文档入口

| 文档 | 作用 |
|------|------|
| `docs/SYSTEM_DESIGN.md` | 主架构、阶段划分、核心约束 |
| `docs/PIPELINE_INTEGRATION.md` | 模块接口与回归检查点 |
| `docs/PROJECT_ARCHITECTURE.md` | 仓库结构与模块职责 |
| `docs/EXECUTION_MEMORY.md` | 新终端/新会话续工执行记忆 |
| `docs/REAL_RUN_DATA_FLOW_BATTERY_20260417.md` | 真实 battery 单文档从原始文档到最终图谱的详细数据流英文版 |
| `docs/REAL_RUN_DATA_FLOW_BATTERY_20260417_CN.md` | 真实 battery 单文档从原始文档到最终图谱的详细数据流中文版 |
| `config/README.md` | 配置 schema 与预设说明 |

## 流程概览

```text
数据 -> 证据 -> 固定 Backbone -> 检索 -> 适配 -> 过滤 -> 组装 -> 快照 -> 导出
```

## 快速开始

推荐主链路单变体运行：

```bash
export DEEPSEEK_API_KEY="your-api-key"

python3 -m crossextend_kg.cli run \
  --config crossextend_kg/config/persistent/pipeline.deepseek.json
```

可选多变体压力运行：

```bash
export DEEPSEEK_API_KEY="your-api-key"

python3 -m crossextend_kg.cli run \
  --config crossextend_kg/config/persistent/pipeline.deepseek_full.json
```

预处理原始文档：

```bash
python3 -m crossextend_kg.cli preprocess \
  --config crossextend_kg/config/persistent/preprocessing.deepseek.json
```

## 当前目录结构

```text
crossextend_kg/
  __init__.py
  cli.py
  config.py
  models.py
  io.py
  exceptions.py
  logging_config.py
  validation.py
  backends/
    embeddings.py
    llm.py
  config/
    README.md
    persistent/
    prompts/
    templates/
  docs/
    README.md
    SYSTEM_DESIGN.md
    PIPELINE_INTEGRATION.md
    PROJECT_ARCHITECTURE.md
  pipeline/
    runner.py
    evidence.py
    backbone.py
    router.py
    attachment.py
    memory.py
    graph.py
    artifacts.py
    utils.py
  preprocessing/
  rules/
    filtering.py
  scripts/
    visualize_propagation.py
  data/
  artifacts/
```

## Python API

```python
from crossextend_kg import run_pipeline

result = run_pipeline("crossextend_kg/config/persistent/pipeline.deepseek.json")
summary = result.variant_results["full_llm"].construction_summary

print(summary["backbone_size"])
print(summary["per_domain"]["battery"]["adapter_concept_count"])
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `run` | 执行主链路 |
| `preprocess` | 将原始文档转成 `EvidenceRecord` |
| `replay` | 读取某个快照状态 |
| `rollback` | 回放某个快照对应的回滚状态 |

## 输出文件

每个变体输出到 `<artifact_root>/<run_id>/<variant_id>/`：

```text
run_meta.json
backbone_seed.json
backbone_final.json
backbone.json
construction_summary.json
temporal_memory_entries.jsonl

working/<domain_id>/
  evidence_units.jsonl
  schema_candidates.jsonl
  adapter_schema.json
  adapter_candidates.json
  adapter_candidates.accepted.json
  adapter_candidates.rejected.json
  backbone_reuse_candidates.json
  retrievals.json
  attachment_decisions.json
  historical_context.json
  graph_nodes.jsonl
  graph_edges.jsonl
  candidate_triples.jsonl
  relation_edges.*.json
  final_graph.json
  temporal_assertions.jsonl
  snapshot_manifest.jsonl
  snapshots/<snapshot_id>/
    nodes.jsonl
    edges.jsonl
    consistency.json
  exports/
```

## 架构原则

1. 运行时 backbone 固定，不做动态扩张。
2. 没有 privileged domain，也没有 source-first 聚合。
3. 变体只来自显式开关，不允许 fallback。
4. 主链路不允许静默降级，架构要求的阶段要么正确执行，要么显式失败。
5. 导出摘要使用结构计数，不再依赖指标评测。

## 最近修改

- 删除实验链路、指标评测链路和下游任务相关代码，仅保留主架构。
- 主路由只保留 `reuse_backbone`、`vertical_specialize`、`reject`。
- 强化节点准入与拒绝原因审计导出。
- 增加关系校验和 `data_flow_trace.json`。
- 已用真实 battery 单文档链路完成一次 DeepSeek + 本地 `bge-m3:latest` 的端到端验证。

## 测试

```bash
python -m py_compile $(rg --files crossextend_kg tests | rg '\.py$')
pytest -q tests/test_crossextend_kg_regressions.py
```

## 许可证

MIT License
