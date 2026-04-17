# CrossExtend-KG 真实运行数据流

**日期**: 2026-04-17  
**运行类型**: 真实 battery 单文档端到端 smoke test  
**目的**: 展示从原始文档到最终图谱的真实端到端数据流，包括输入/输出格式、中间产物、处理逻辑，以及一次真实运行中的具体结果

## 1. 运行标识

本文档描述的是最近一次已验证通过的真实运行：

- run root: [tmp/crossextend_kg_battery_single_strict_20260417T105948Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z)
- pipeline artifact root: [battery_single_strict-20260417T110121Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z)
- variant: `full_llm`

本次运行使用的后端：

- preprocessing LLM: `deepseek-chat`
- attachment LLM: `deepseek-chat`
- embedding backend: 本地 `ollama`
- embedding model: `bge-m3:latest`

## 2. 本次运行的目录结构

```text
tmp/crossextend_kg_battery_single_strict_20260417T105948Z/
├── raw_data/
│   └── battery/fault_cases/battery_fault_0001.md
├── configs/
│   ├── preprocessing.json
│   └── pipeline.json
├── outputs/
│   └── evidence_records_battery_single.json
└── artifacts/
    └── battery_single_strict-20260417T110121Z/
        └── full_llm/
            ├── run_meta.json
            ├── backbone_seed.json
            ├── backbone_final.json
            ├── backbone.json
            ├── construction_summary.json
            ├── data_flow_trace.json
            ├── temporal_memory_entries.jsonl
            └── working/battery/
                ├── adapter_candidates.json
                ├── adapter_candidates.accepted.json
                ├── adapter_candidates.rejected.json
                ├── adapter_candidates.rejected_by_reason.json
                ├── adapter_schema.json
                ├── attachment_decisions.json
                ├── backbone_reuse_candidates.json
                ├── final_graph.json
                ├── historical_context.json
                ├── relation_edges.accepted.json
                ├── relation_edges.candidates.json
                ├── relation_edges.rejected.json
                ├── relation_edges.rejected_type.json
                ├── retrievals.json
                ├── snapshots/
                └── exports/
```

## 3. 分阶段数据流

## Stage 0. 原始文档输入

### 输入文件

- [battery_fault_0001.md](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/raw_data/battery/fault_cases/battery_fault_0001.md)

### 输入格式

Markdown 故障案例文档，包含：

- 案例概述
- 设备 / 产品标识
- 时间戳
- 环境条件表
- 诊断过程时间线
- 根因分析
- 解决 / 预防说明

### 本文档中的关键内容

- asset 类概念: `Battery Pack`
- component 类概念: `Battery Management System (BMS)`、`Cell`、`Anode`、`Cathode`、`Separator`
- fault / mechanism 类概念: `Capacity Degradation Fault`、`SEI Layer Growth`、`Lithium Plating`、`Cathode Micro-cracking`
- 叙事时间线中还嵌入了 state / signal / task 信息
- 人员信息: `Dr. A. Chen`
- 文档身份信息: `Battery Fault Diagnosis Case Document`

### 该阶段的架构解释

在这一阶段，还没有任何内容成为图节点。

该文件目前只是：

- 原始源文本
- provenance 输入
- extraction 的数据源

## Stage 1. 预处理配置构建

### 输入配置文件

- [preprocessing.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/preprocessing.json)

### 实际关键字段

```json
{
  "data_root": ".../raw_data",
  "domain_ids": ["battery"],
  "output_path": ".../outputs/evidence_records_battery_single.json",
  "prompt_template_path": ".../crossextend_kg/config/prompts/preprocessing_extraction.txt",
  "llm": {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "timeout_sec": 600,
    "max_tokens": 4096,
    "temperature": 0.1
  }
}
```

### 该阶段定义了什么

- 扫描哪个原始数据目录
- 哪些 domain id 合法
- 预处理输出写到哪里
- 抽取使用哪份 prompt 模板
- 哪个 LLM 后端是必需的

### 重要规则

预处理阶段 **没有 fallback**。

如果 `llm.base_url` 或 `llm.model` 缺失，预处理必须显式失败，不能静默切到别的抽取模式。

相关实现：

- [processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)

## Stage 2. Raw Markdown Parsing -> DocumentInput

### 代码路径

- [parser.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/parser.py)

### 转换内容

Markdown 文件会被解析成内部 `DocumentInput` 对象。

### 生成的逻辑字段

- `doc_id`
- `doc_type`
- `domain_id`
- `role`
- `title`
- `content`
- `metadata`
- `timestamp`

### 本次运行中的结果

解析后的有效值大致为：

```json
{
  "doc_id": "battery_fault_0001",
  "doc_type": "fault_case",
  "domain_id": "battery",
  "role": "target",
  "timestamp": "2023-10-26T00:00:00Z"
}
```

### 重要处理细节

该阶段会执行：

- 从 markdown 标题抽取 title
- 根据文件名生成 `doc_id`
- 提取并归一化时间戳为 UTC ISO 格式
- 读取原始内容

在这一阶段，数据仍然是文档导向的，不是图导向的。

## Stage 3. 内容归一化与 LLM 抽取

### 代码路径

- [processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)
- [extractor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/extractor.py)
- prompt: [preprocessing_extraction.txt](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/config/prompts/preprocessing_extraction.txt)

### 输入

- `DocumentInput`
- backbone concept 列表
- relation family 列表
- extraction prompt

### 内部处理

在把内容送入 LLM 之前，会先：

- 归一化 markdown 内容
- 对超长内容做截断，避免超时
- 用下列内容渲染 prompt：
  - backbone concepts
  - relation families
  - document content

### LLM 期望输出格式

抽取器要求返回如下 JSON：

```json
{
  "concepts": [
    {
      "label": "Battery Pack",
      "description": "The main energy storage asset.",
      "node_worthy": true
    }
  ],
  "relations": [
    {
      "label": "contains",
      "family": "structural",
      "head": "Battery Pack",
      "tail": "Cell"
    }
  ],
  "extraction_quality": "high"
}
```

### 预处理阶段中的关系归一化

在 LLM 抽取完成后，写入 `EvidenceRecord` 之前，会先对 relation mention 做确定性归一化。

目前实现的归一化包括：

- 被动转主动：
  - `measured_by` -> `measures`
  - `confirmed_by` -> `confirms`
  - `observed_in` -> `observes`
  - `performed_by` -> `performs`
- 对已知主动标签做 family 归一化
- 被动形式改写时同步翻转 head/tail
- 去掉单个 evidence record 内部的重复关系

这属于架构内部归一化，不是 fallback 路径。

## Stage 4. LLM 抽取输出 -> EvidenceRecord

### 输出文件

- [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)

### 顶层输出结构

```json
{
  "project_name": "crossextend_kg_preprocessing",
  "generated_at": "...",
  "domains": ["battery"],
  "role": "target",
  "document_count": 1,
  "domain_stats": {
    "battery": {
      "fault_case": 1
    }
  },
  "evidence_records": [...]
}
```

### 单个 EvidenceRecord 结构

```json
{
  "evidence_id": "battery_fault_0001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "fault_case",
  "timestamp": "2023-10-26T00:00:00Z",
  "raw_text": "...",
  "concept_mentions": [...],
  "relation_mentions": [...]
}
```

### 本次运行的真实结果

- `document_count = 1`
- `concept_mentions = 30`
- `relation_mentions = 31`

### 实际 concept 示例

```json
[
  {
    "label": "Battery Pack",
    "description": "The main energy storage asset, identified by product ID battery_product_001.",
    "node_worthy": true
  },
  {
    "label": "Battery Management System (BMS)",
    "description": "Component that manages the battery pack, provides operational data.",
    "node_worthy": true
  },
  {
    "label": "Capacity Degradation Fault",
    "description": "Fault characterized by significant reduction in battery capacity (BAT-FLT-001-CAP-DEG).",
    "node_worthy": true
  }
]
```

### 实际 relation 示例

```json
[
  {
    "label": "contains",
    "family": "structural",
    "head": "Battery Pack",
    "tail": "Battery Management System (BMS)"
  },
  {
    "label": "causes",
    "family": "propagation",
    "head": "SEI Layer Growth",
    "tail": "Capacity Degradation Fault"
  },
  {
    "label": "measures",
    "family": "task_dependency",
    "head": "HPPC Test Task",
    "tail": "High Internal Resistance State"
  }
]
```

## Stage 5. Pipeline Config Load

### 输入配置文件

- [pipeline.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/pipeline.json)

### 关键运行时字段

```json
{
  "llm": {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
  },
  "embedding": {
    "base_url": "http://127.0.0.1:11434/v1",
    "model": "bge-m3:latest"
  },
  "relations": {
    "relation_families": [
      "task_dependency",
      "communication",
      "propagation",
      "lifecycle",
      "structural"
    ],
    "allowed_routes": [
      "reuse_backbone",
      "vertical_specialize",
      "reject"
    ]
  },
  "runtime": {
    "retrieval_top_k": 3,
    "llm_attachment_batch_size": 8,
    "enable_relation_validation": true,
    "relation_constraints_path": ".../relation_constraints.json",
    "run_prefix": "battery_single_strict"
  },
  "variants": [
    {
      "variant_id": "full_llm",
      "attachment_strategy": "llm",
      "use_embedding_routing": true,
      "use_rule_filter": true,
      "enable_memory_bank": true,
      "enable_snapshots": true
    }
  ]
}
```

### 该阶段定义了什么

- 只处理哪个 domain
- 当前激活的 variant
- embedding retrieval 的行为
- attachment route 集合
- 是否强制执行 filtering
- 是否执行 relation validation
- 是否写出 snapshots

## Stage 6. EvidenceRecord -> EvidenceUnit

### 代码路径

- [evidence.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/evidence.py)

### 输入

- 来自 `evidence_records_battery_single.json` 的 `EvidenceRecord` 列表

### 输出结构

`EvidenceUnit` 是主链路内部使用的标准化 evidence 容器：

```json
{
  "evidence_id": "battery_fault_0001",
  "domain_id": "battery",
  "role": "target",
  "source_id": "evidence_records_battery_single.json",
  "source_type": "fault_case",
  "locator": "battery/fault_case/0",
  "raw_text": "...",
  "normalized_text": "...",
  "metadata": {
    "timestamp": "2023-10-26T00:00:00Z"
  }
}
```

### 本次运行中的效果

- `evidence_unit_count = 1`

这还不是图对象。
它是主链路运行时使用的 evidence 载体，用于：

- provenance
- memory-bank 构建
- summaries
- export

## Stage 7. EvidenceRecord -> SchemaCandidate

### 代码路径

- [evidence.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/evidence.py)

### 聚合逻辑

候选概念按下列键聚合：

- `(domain_id, mention.label)`

只有 `node_worthy=true` 的 mention 才会被聚合。

### Candidate 结构

```json
{
  "candidate_id": "battery::Battery Pack",
  "domain_id": "battery",
  "role": "target",
  "label": "Battery Pack",
  "description": "The main energy storage asset.",
  "evidence_ids": ["battery_fault_0001"],
  "evidence_texts": ["..."],
  "support_count": 1,
  "routing_features": {
    "support_count": 1,
    "evidence_count": 1,
    "relation_participation_count": 4,
    "relation_head_count": 4,
    "relation_tail_count": 0,
    "relation_families": ["structural"]
  }
}
```

### 关键派生 routing 特征

聚合器会计算：

- 该概念出现在关系中的次数
- 它作为 head 还是 tail 出现
- 它参与了哪些 relation family

这些特征会进一步影响：

- 节点准入
- 弱支持拒绝
- anchor 推理

### 本次运行中的真实结果

- `schema_candidate_count = 30`

相关产物：

- [adapter_candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.json)

## Stage 8. Backbone Build

### 代码路径

- [backbone.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/backbone.py)

### 输入

- `backbone.seed_concepts`
- `backbone.seed_descriptions`
- 可选的 `ontology_seed_path` 条目

### 当前有效设计

- backbone 是冻结的
- 不做动态 backbone 抽取
- 不从文档内容中做运行时 backbone 扩张

### 本次运行使用的 backbone concepts

当前上位 ontology 含有 11 个 seed concepts：

- `Asset`
- `Component`
- `Process`
- `Task`
- `Signal`
- `State`
- `Fault`
- `MaintenanceAction`
- `Incident`
- `Actor`
- `Document`

### 导出产物

- [backbone_seed.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone_seed.json)
- [backbone_final.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone_final.json)
- [backbone.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone.json)

## Stage 9. Anchor Retrieval

### 代码路径

- [runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)
- `retrieve_anchor_rankings(...)`

### 输入

- 每个 `SchemaCandidate`
- backbone descriptions
- embedding backend
- `top_k = 3`

### 输出结构

每个 candidate 会得到最多 3 个 retrieved anchors：

```json
"battery::Battery Pack": [
  {"anchor": "Asset", "score": 0.6625, "rank": 1},
  {"anchor": "Process", "score": 0.5239, "rank": 2},
  {"anchor": "Component", "score": 0.5143, "rank": 3}
]
```

### 实际示例

`Battery Pack`

```json
[
  {"anchor": "Asset", "score": 0.6625352501869202, "rank": 1},
  {"anchor": "Process", "score": 0.5238973498344421, "rank": 2},
  {"anchor": "Component", "score": 0.514290452003479, "rank": 3}
]
```

`Battery Management System (BMS)`

```json
[
  {"anchor": "Process", "score": 0.6121953725814819, "rank": 1},
  {"anchor": "Task", "score": 0.6014306545257568, "rank": 2},
  {"anchor": "Component", "score": 0.5975511074066162, "rank": 3}
]
```

这正好说明 retrieval 只是提示，不是最终裁决：

- 如果纯用 embedding top-1，`BMS` 会被推向 `Process`
- 后续 attachment 和 rule filtering 把它纠正到了 `Component`

产物：

- [retrievals.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/retrievals.json)

## Stage 10. 历史上下文检索

### 代码路径

- [memory.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/memory.py)

### 目的

检索之前写入 memory bank 的历史上下文，帮助 attachment 在时间上保持一致性。

### 输出产物

- [historical_context.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/historical_context.json)

### 本次运行中的情况

这部分基础设施是开启的，但在本次运行里最直观的结果只是：历史上下文会作为 attachment prompt 的一部分输入。

## Stage 11. Attachment Decision

### 代码路径

- [attachment.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/attachment.py)

### 输入

对每个 candidate，输入包括：

- candidate label 和 description
- routing features
- top-k retrieved anchors
- historical context
- backbone descriptions
- allowed routes

### Attachment 输出结构

```json
{
  "candidate_id": "battery::Battery Pack",
  "label": "Battery Pack",
  "route": "vertical_specialize",
  "parent_anchor": "Asset",
  "accept": true,
  "admit_as_node": true,
  "reject_reason": null,
  "confidence": 0.85,
  "justification": "...",
  "evidence_ids": ["battery_fault_0001"]
}
```

### 本次运行中的真实行为

- attachment strategy: `llm`
- batch size: `8`
- 30 个 candidates 分 4 个 batch 处理

### 关键示例

`Battery Pack`

```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Asset",
  "admit_as_node": true
}
```

`Battery Management System (BMS)`

```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Component",
  "admit_as_node": true
}
```

`Battery Fault Diagnosis Case Document`

```json
{
  "route": "reject",
  "parent_anchor": null,
  "admit_as_node": false,
  "reject_reason": "document_title"
}
```

### 关键运行时保护

该阶段还包含：

- 将非法的、非 backbone 的 `reuse_backbone` 决策归一化为带 anchor 的 `vertical_specialize`
- 如果 LLM 对某个 candidate 没有返回决策，则显式生成 reject

产物：

- [attachment_decisions.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/attachment_decisions.json)

## Stage 12. 规则过滤与最终节点准入

### 代码路径

- [filtering.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/rules/filtering.py)

### 目的

这是最终的节点准入闸门。

它会在 LLM attachment 之后强制执行架构规则，而不是直接信任 LLM 输出。

### 主要检查项

- person-name rejection
- document-title rejection
- route 合法性约束
- 非法 anchor rejection
- no-relation-support rejection
- 对明显语义漂移做确定性的 parent-anchor 修正

### 输出影响

只有满足：

- `admit_as_node = true`

的候选概念，才能继续进入 domain schema 构建和图节点实体化。

### 本次运行中的真实结果

- candidates 总数: `30`
- admitted: `28`
- rejected: `2`

被拒绝的 candidates：

1. `Battery Fault Diagnosis Case Document`

```json
{
  "route": "reject",
  "admit_as_node": false,
  "reject_reason": "document_title"
}
```

2. `Diagnosis Engineer`

```json
{
  "route": "reject",
  "admit_as_node": false,
  "reject_reason": "person_name"
}
```

产物：

- [adapter_candidates.rejected_by_reason.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.rejected_by_reason.json)

## Stage 13. Domain Schema 实体化

### 代码路径

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### 输入

- admitted candidates
- attachment decisions
- backbone concept 列表

### 输出结构

只有被准入的 `vertical_specialize` candidates 会成为 `AdapterConcept`。

`DomainSchema` 结构：

```json
{
  "domain_id": "battery",
  "backbone_concepts": [...],
  "adapter_concepts": [
    {
      "label": "Battery Pack",
      "parent_anchor": "Asset",
      "description": "...",
      "evidence_ids": ["battery_fault_0001"]
    }
  ]
}
```

### 本次运行中的结果

- `adapter_concept_count = 28`

产物：

- [adapter_schema.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_schema.json)

## Stage 14. Relation Mention -> CandidateTriple

### 代码路径

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### 输入

- 原始 `relation_mentions`
- admitted node labels
- head 和 tail 概念的 attachment decisions

### CandidateTriple 结构

```json
{
  "triple_id": "battery::triple::battery_fault_0001::1",
  "domain_id": "battery",
  "head": "Battery Pack",
  "relation": "contains",
  "tail": "Cell",
  "relation_family": "structural",
  "evidence_ids": ["battery_fault_0001"],
  "attachment_refs": ["battery::Battery Pack", "battery::Cell"],
  "confidence": 1.0,
  "reject_reason": null,
  "status": "accepted"
}
```

可能的状态：

- `accepted`
- `rejected`
- `rejected_type`

### 本次运行中的结果

- candidate triples 总数: `31`

### 本次运行里的 family 级拒绝

有 3 条 triple 被拒绝，原因是其一端或两端节点此前已被判定为不适合进入图：

1. `Diagnosis Engineer performs Remote Data Dump Task`
2. `Diagnosis Engineer documents Battery Fault Diagnosis Case Document`
3. `Battery Fault Diagnosis Case Document describes Capacity Degradation Fault`

产物：

- [relation_edges.candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.candidates.json)
- [relation_edges.rejected.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected.json)

## Stage 15. Relation Validation

### 代码路径

- [relation_validation.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/relation_validation.py)
- 约束文件: [relation_constraints.json](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/config/persistent/relation_constraints.json)

### 校验输入

对每条 candidate edge，输入包括：

- relation family
- head label
- tail label
- 根据下列信息构造的 node type lookup：
  - backbone labels
  - adapter 的 `parent_anchor`

### 校验输出

每条 candidate relation 最终会变成：

- accepted
- family-rejected
- type-rejected

### 本次运行中的真实结果

```json
{
  "total_candidates": 31,
  "accepted": 28,
  "rejected_family": 3,
  "rejected_type": 0
}
```

解释：

- 3 条被拒绝的关系，都是因为其节点未被准入
- 本次运行中 **没有** 剩余的 type-constraint 失败

产物：

- [relation_edges.accepted.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.accepted.json)
- [relation_edges.rejected_type.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected_type.json)

## Stage 16. GraphNode / GraphEdge 实体化

### 代码路径

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### 节点创建规则

一个 concept mention 只有在满足以下条件时，才会变成 `GraphNode`：

- 它出现在原始记录中
- 它是 `node_worthy`
- 它的 label 位于 admitted label 集合中

### Node 结构

```json
{
  "node_id": "battery::node::Battery Pack",
  "label": "Battery Pack",
  "domain_id": "battery",
  "node_type": "adapter_concept",
  "parent_anchor": "Asset",
  "provenance_evidence_ids": ["battery_fault_0001"]
}
```

### Edge 结构

```json
{
  "edge_id": "battery::edge::Battery Pack::contains::Cell",
  "domain_id": "battery",
  "label": "contains",
  "family": "structural",
  "head": "Battery Pack",
  "tail": "Cell",
  "provenance_evidence_ids": ["battery_fault_0001"]
}
```

### 本次运行中的最终图结果

- nodes: `28`
- edges: `28`

被接受的 edge 示例：

- `Battery Pack contains Battery Management System (BMS)`
- `Battery Pack contains Cell`
- `SEI Layer Growth causes Capacity Degradation Fault`
- `Operational Data Signal indicates Reduced Capacity State`
- `Battery Management System (BMS) provides Operational Data Signal`

## Stage 17. Snapshot 与时序产物生成

### 代码路径

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)
- [artifacts.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/artifacts.py)

### 生成内容

由于 `enable_snapshots=true`，每处理一个 evidence record，就会生成：

- 一个 `SnapshotManifest`
- 一个 `SnapshotState`
- 对新观测到的 nodes 和 edges 生成 `TemporalAssertion` 条目

### 本次运行中的结果

因为只有一条源记录，所以：

- `snapshot_count = 1`

snapshot 文件写在：

- [snapshots](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/snapshots)

### 重要说明

这里仍然是文档级 snapshot 机制，还不是后续为运维表单数据设计的 time-step execution-layer 方案。

## Stage 18. 最终导出层

### 运行级导出文件

在 variant 根目录下：

- [run_meta.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/run_meta.json)
- [construction_summary.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/construction_summary.json)
- [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)

### Domain working 文件

`working/battery/` 内包含：

- candidate audit
- retrieval audit
- attachment audit
- relation acceptance / rejection audit
- final graph
- snapshot state
- export-ready graph formats

### `data_flow_trace.json` 的含义

这个文件是整次运行的压缩摘要，包含：

- candidate 数量
- rejection reasons
- admitted labels
- accepted edges
- node / edge / triple 数量

本次运行中为：

```json
{
  "schema_candidate_count": 30,
  "admitted_candidate_count": 28,
  "rejected_candidate_count": 2,
  "rejected_candidate_reasons": {
    "document_title": 1,
    "person_name": 1
  },
  "graph_node_count": 28,
  "graph_edge_count": 28,
  "candidate_triple_count": 31,
  "accepted_triple_count": 28,
  "rejected_triple_count": 3,
  "type_rejected_triple_count": 0
}
```

## 4. 全链路压缩视图: File-to-File Map

## Raw -> Preprocess

- input:
  - [battery_fault_0001.md](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/raw_data/battery/fault_cases/battery_fault_0001.md)
- config:
  - [preprocessing.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/preprocessing.json)
- output:
  - [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)

## Preprocess Output -> Main Pipeline Input

- input:
  - [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)
- config:
  - [pipeline.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/pipeline.json)
- runtime code:
  - [runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)

## Candidate Build / Retrieval / Attachment

- candidate audit:
  - [adapter_candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.json)
- retrieval audit:
  - [retrievals.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/retrievals.json)
- attachment audit:
  - [attachment_decisions.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/attachment_decisions.json)
- reject audit:
  - [adapter_candidates.rejected_by_reason.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.rejected_by_reason.json)

## Triple / Edge Construction

- all candidate triples:
  - [relation_edges.candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.candidates.json)
- accepted triples / edges:
  - [relation_edges.accepted.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.accepted.json)
- rejected triples:
  - [relation_edges.rejected.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected.json)
- type-rejected triples:
  - [relation_edges.rejected_type.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected_type.json)

## Final Graph and Summary

- final graph:
  - [final_graph.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/final_graph.json)
- construction summary:
  - [construction_summary.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/construction_summary.json)
- data flow summary:
  - [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)

## 5. 本次真实运行的最终观察

### 有效工作的部分

- 全链路从 raw markdown 跑到了 final graph
- 没有使用任何架构 fallback
- 冻结 backbone 保持不变
- 节点准入过滤生效
- 合理 reject 被保留下来且可审计
- 本次运行中 relation type 噪声被压到了 0

### 被刻意拒绝的内容

- 文档标题没有进入图作为节点
- 人名概念没有进入图作为节点
- 与这些被拒绝节点相连的关系也一并被拒绝

### 本次运行还不是什么

本次运行仍然是一次 **document-to-concept-graph** 运行。

它还不是后续要设计的：

- operations-form execution layer
- time-step event chain
- action-instance graph
- state-transition execution graph

这些都需要等拿到真实运维表单样例之后再单独设计。
