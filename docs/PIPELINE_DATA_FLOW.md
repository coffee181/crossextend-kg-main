# CrossExtend-KG Pipeline数据流详解

**Updated**: 2026-04-22
**Status**: Technical Reference
**Scope**: Complete pipeline architecture, data flow, and format transformation

---

## 1. 总体架构

CrossExtend-KG采用**7阶段流水线**架构，从原始Markdown文档到最终知识图谱输出：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CrossExtend-KG Pipeline                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [原始输入]                                                                   │
│  data/{domain}_om_manual_en/*.md                                             │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐                                                             │
│  │ 1. 解析阶段 │  parser.py                                                  │
│  │   (Parse)   │  提取Markdown表格、文档元数据                                │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  DocumentInput                                                       │
│  ┌─────────────┐                                                             │
│  │ 2. LLM抽取  │  extractor.py ────────── LLM第1次调用                       │
│  │  (Extract)  │  提取concepts + relations                                   │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  ExtractionResult                                                    │
│  ┌─────────────┐                                                             │
│  │ 3. 证据构建 │  processor.py                                               │
│  │  (Evidence) │  构建EvidenceRecord，按步骤分组                             │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  EvidenceRecord                                                      │
│  ┌─────────────┐                                                             │
│  │ 4. 候选聚合 │  evidence.py                                                │
│  │  (Aggregate)│  提取SchemaCandidate，计算routing_features                  │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  SchemaCandidate                                                     │
│  ┌─────────────┐                                                             │
│  │ 5. 嵌入检索 │  router.py                                                  │
│  │  + Attachment│ attachment.py ───────── LLM第2次调用                       │
│  │  (Route)    │  决定每个候选的parent_anchor                                │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  AttachmentDecision                                                  │
│  ┌─────────────┐                                                             │
│  │ 6. 规则过滤 │  filtering.py + relation_filtering.py                       │
│  │  (Filter)   │  应用安全护栏，剔除低质量候选                                │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  Filtered Decisions                                                  │
│  ┌─────────────┐                                                             │
│  │ 7. 图谱组装 │  graph.py                                                   │
│  │  (Assemble) │  实例化GraphNode + GraphEdge                                │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼  DomainGraphArtifacts                                                │
│  ┌─────────────┐                                                             │
│  │ 8. 制品导出 │  artifacts.py                                               │
│  │  (Export)   │  final_graph.json, GraphML, CSV等                          │
│  └─────────────┘                                                             │
│       │                                                                      │
│       ▼                                                                      │
│  [最终输出]                                                                   │
│  working/{domain}/final_graph.json                                           │
│  graphml/{variant}/{domain}.graphml                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 阶段详解

### 2.1 解析阶段 (parser.py)

**职责**: 解析原始Markdown文档，提取结构化内容

**输入文件**: `data/battery_om_manual_en/BATOM_001.md`

```markdown
# Battery Pack O&M Manual

| Time step | O&M sample text |
|---|---|
| T1 | At the left-rear coolant-plate outlet on Aurex BatteryHub-612 LR, record the complaint as seepage, dried residue, or undertray drip, and capture the coolant concentration, pack serial, and the last chiller or hose service that touched this branch. Save the as-found stain path from the outlet neck to the shield edge before any clip, hose, or connector body is moved. |
| T2 | Make the pack safe, remove the local underbody shield, and expose the aluminum outlet neck, PA12 quick-connector shell, green EPDM O-ring seat, stainless retainer clip, hose saddle bracket, and nearby harness fir-tree clip without changing the hose angle. Keep the connector-to-bracket path intact so the original side load can still be judged. |
| T3 | Clean only the loose dirt and then trace the residue from the lowest drip point upward with a lamp, separating wetting at the latch window from wetting at the tube bead or the cold-plate seam. Residue that begins above the retainer clip and then runs down the shell suggests a different boundary than residue that forms first at the aluminum neck. |
...
```

**处理逻辑**:
- `parse_multi_domain_directory()` -- 扫描域目录
- `parse_markdown_file()` -- 提取title、doc_id、timestamp、metadata
- `classify_doc_type()` -- 确认文档类型为 `om_manual`
- `normalize_content()` -- 清理空行、HTML标签

**输出**: `DocumentInput` (Pydantic模型)

```json
{
  "doc_id": "BATOM_001",
  "doc_type": "om_manual",
  "domain_id": "battery",
  "role": "target",
  "title": "Battery Pack O&M Manual",
  "content": "| Time step | O&M sample text |\n|---|---|\n| T1 | At the left-rear... |",
  "metadata": {},
  "timestamp": "2026-04-22T11:57:41Z"
}
```

---

### 2.2 LLM抽取阶段 (extractor.py) ─── LLM第1次调用

**职责**: 从文档内容中提取概念和关系

**LLM调用详情**:
- 后端: `backends/llm.py` -- OpenAI兼容API
- 模板: `config/prompts/preprocessing_extraction_om.txt`
- 模型: `deepseek-chat` (可配置)
- Temperature: 0.1
- Max Tokens: 4096

**注入的Backbone概念**:
```json
["Asset", "Component", "Process", "Task", "Signal", "State", "Fault", "MaintenanceAction", "Incident", "Actor", "Document"]
```

**注入的Relation Families**:
```json
["task_dependency", "communication", "propagation", "lifecycle", "structural"]
```

**Prompt结构**:
```
You are an O&M knowledge extraction assistant.

Backbone concepts: __BACKBONE_CONCEPTS_JSON__
Relation families: __RELATION_FAMILIES_JSON__

Document content:
__DOCUMENT_CONTENT__

Extract concepts and relations in JSON format:
{
  "concepts": [{"label": "...", "description": "...", "semantic_type_hint": "..."}],
  "relations": [{"label": "...", "family": "...", "head": "...", "tail": "..."}],
  "extraction_quality": "high|medium|low"
}
```

**LLM返回示例**:
```json
{
  "concepts": [
    {
      "label": "Aurex BatteryHub-612 LR",
      "description": "battery pack asset",
      "node_worthy": true,
      "semantic_type_hint": "Asset"
    },
    {
      "label": "seepage",
      "description": "seepage or leakage complaint",
      "node_worthy": true,
      "semantic_type_hint": "Signal"
    },
    {
      "label": "coolant concentration",
      "description": "measured coolant concentration",
      "node_worthy": true,
      "semantic_type_hint": "Signal"
    },
    {
      "label": "left-rear coolant-plate outlet",
      "description": "coolant outlet on the pack",
      "node_worthy": true,
      "semantic_type_hint": "Component"
    }
  ],
  "relations": [
    {
      "label": "observes",
      "family": "task_dependency",
      "head": "T1",
      "tail": "seepage"
    },
    {
      "label": "observes",
      "family": "task_dependency",
      "head": "T1",
      "tail": "coolant concentration"
    },
    {
      "label": "contains",
      "family": "structural",
      "head": "Aurex BatteryHub-612 LR",
      "tail": "left-rear coolant-plate outlet"
    }
  ],
  "extraction_quality": "high"
}
```

**输出**: `ExtractionResult`

```json
{
  "doc_id": "BATOM_001",
  "concepts": [...],
  "relations": [...],
  "extraction_quality": "high",
  "llm_model": "deepseek-chat",
  "processing_time_ms": 3420
}
```

---

### 2.3 证据记录构建 (processor.py)

**职责**: 将LLM抽取结果转换为按步骤分组的EvidenceRecord

**处理逻辑**:

1. **步骤行提取**: `_extract_step_rows()` -- 从Markdown表格提取 `(T1, "text..."), (T2, "text...")`

2. **概念分配到步骤**:
   - 端点包含步骤ID的关系 → 分配到对应 `StepRecord`
   - 无步骤端点 → 分配到 `document_relations`

3. **隐式步骤链重建**: 自动在相邻T步骤间添加 `triggers` 关系
   - T1 → T2 → T3 → ... → Tn

4. **关系规范化**:
   - `task_dependency` → 保持
   - `structural` → 确保 Asset contains Component 方向

**输入**: `DocumentInput` + `ExtractionResult`

**输出**: `EvidenceRecord`

```json
{
  "evidence_id": "BATOM_001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "om_manual",
  "timestamp": "2026-04-22T11:57:41Z",
  "raw_text": "| Time step | O&M sample text |\n|---|---|\n| T1 | At the left-rear... |",
  "step_records": [
    {
      "step_id": "T1",
      "task": {
        "label": "T1",
        "kind": "concept",
        "description": "",
        "node_worthy": true,
        "surface_form": "At the left-rear coolant-plate outlet on Aurex BatteryHub-612 LR, record the complaint as seepage, dried residue, or undertray drip...",
        "semantic_type_hint": null
      },
      "concept_mentions": [
        {
          "label": "Aurex BatteryHub-612 LR",
          "kind": "concept",
          "description": "battery pack asset",
          "node_worthy": true,
          "surface_form": "Aurex BatteryHub-612 LR",
          "semantic_type_hint": "Asset"
        },
        {
          "label": "seepage",
          "kind": "concept",
          "description": "seepage or leakage complaint",
          "node_worthy": true,
          "surface_form": "seepage",
          "semantic_type_hint": "Signal"
        },
        {
          "label": "coolant concentration",
          "kind": "concept",
          "description": "measured coolant concentration",
          "node_worthy": true,
          "surface_form": "coolant concentration",
          "semantic_type_hint": "Signal"
        },
        {
          "label": "left-rear coolant-plate outlet",
          "kind": "concept",
          "description": "coolant outlet on the pack",
          "node_worthy": true,
          "surface_form": "left-rear coolant-plate outlet",
          "semantic_type_hint": "Component"
        }
      ],
      "relation_mentions": [
        {
          "label": "observes",
          "family": "task_dependency",
          "head": "T1",
          "tail": "seepage"
        },
        {
          "label": "observes",
          "family": "task_dependency",
          "head": "T1",
          "tail": "coolant concentration"
        },
        {
          "label": "triggers",
          "family": "task_dependency",
          "head": "T1",
          "tail": "T2"
        }
      ]
    },
    {
      "step_id": "T2",
      "task": {
        "label": "T2",
        "surface_form": "Make the pack safe, remove the local underbody shield..."
      },
      "concept_mentions": [
        {
          "label": "aluminum outlet neck",
          "semantic_type_hint": "Component"
        },
        {
          "label": "PA12 quick-connector shell",
          "semantic_type_hint": "Component"
        },
        {
          "label": "green EPDM O-ring",
          "semantic_type_hint": "Component"
        }
      ],
      "relation_mentions": [
        {
          "label": "exposes",
          "family": "task_dependency",
          "head": "T2",
          "tail": "aluminum outlet neck"
        },
        {
          "label": "triggers",
          "family": "task_dependency",
          "head": "T2",
          "tail": "T3"
        }
      ]
    }
  ],
  "document_concept_mentions": [],
  "document_relation_mentions": [
    {
      "label": "contains",
      "family": "structural",
      "head": "Aurex BatteryHub-612 LR",
      "tail": "left-rear coolant-plate outlet"
    }
  ]
}
```

**存储路径**: `data/evidence_records/full_human_gold_9doc/battery_evidence_records_llm.json`

---

### 2.4 候选聚合阶段 (evidence.py)

**职责**: 跨文档聚合候选概念，计算routing特征

**处理逻辑**:

1. `load_records_by_domain()` -- 按domain加载EvidenceRecord
2. `normalize_records_by_domain()` -- 规范化标签
3. `aggregate_schema_candidates()` -- 提取所有 `node_worthy=true` 的概念

**候选聚合规则**:
- 同一label跨多条证据 → 合并
- 统计关系参与度（作为routing_features）
- 语义类型提示投票（取最高频）

**输出**: `dict[domain_id, list[SchemaCandidate]]`

```json
{
  "battery": [
    {
      "candidate_id": "battery::Aurex BatteryHub-612 LR",
      "domain_id": "battery",
      "role": "target",
      "label": "Aurex BatteryHub-612 LR",
      "description": "battery pack asset",
      "evidence_ids": ["BATOM_001", "BATOM_002", "BATOM_003"],
      "evidence_texts": ["Aurex BatteryHub-612 LR"],
      "routing_features": {
        "evidence_count": 3,
        "relation_participation_count": 5,
        "relation_head_count": 3,
        "relation_tail_count": 2,
        "relation_families": ["structural", "task_dependency"],
        "step_ids": ["T1"],
        "semantic_type_hint": "Asset",
        "semantic_type_hint_candidates": ["Asset"],
        "support_count": 3
      }
    },
    {
      "candidate_id": "battery::seepage",
      "domain_id": "battery",
      "label": "seepage",
      "description": "seepage or leakage complaint",
      "evidence_ids": ["BATOM_001"],
      "routing_features": {
        "evidence_count": 1,
        "relation_participation_count": 2,
        "relation_head_count": 0,
        "relation_tail_count": 2,
        "relation_families": ["task_dependency"],
        "semantic_type_hint": "Signal",
        "support_count": 1
      }
    },
    {
      "candidate_id": "battery::coolant concentration",
      "domain_id": "battery",
      "label": "coolant concentration",
      "description": "measured coolant concentration",
      "evidence_ids": ["BATOM_001"],
      "routing_features": {
        "evidence_count": 1,
        "relation_participation_count": 1,
        "semantic_type_hint": "Signal"
      }
    }
  ]
}
```

---

### 2.5 嵌入检索 + Attachment决策 (router.py + attachment.py) ─── LLM第2次调用

**职责**: 决定每个候选概念如何连接到图谱骨干

#### 2.5a 嵌入检索 (router.py)

**处理逻辑**:
1. 构造 anchor texts: `"{backbone_name}: {description}"`
2. 构造 candidate texts: `"{label}: {description}"`
3. 批量嵌入
4. 计算cosine similarity
5. 取top-k作为候选anchors

**Backbone描述**:
```json
{
  "Asset": "Physical equipment, platform, or system being maintained",
  "Component": "Hardware part, module, or subassembly",
  "Signal": "Measurement, observation, or complaint indication",
  "State": "Operating condition or status",
  "Fault": "Failure mode, defect, or error boundary",
  "Task": "O&M procedure step or maintenance action"
}
```

**检索结果**:
```json
{
  "battery::seepage": [
    {"anchor": "Signal", "score": 0.8921, "rank": 1},
    {"anchor": "Fault", "score": 0.6543, "rank": 2},
    {"anchor": "State", "score": 0.4321, "rank": 3}
  ],
  "battery::Aurex BatteryHub-612 LR": [
    {"anchor": "Asset", "score": 0.9234, "rank": 1},
    {"anchor": "Component", "score": 0.5123, "rank": 2}
  ]
}
```

#### 2.5b Attachment决策 (attachment.py)

**策略选择** (由 `variant.attachment_strategy` 决定):

| 策略 | 说明 |
|------|------|
| `embedding_top1` | 直接使用embedding top-1 |
| `deterministic` | 同上，更高confidence |
| `llm` | 调用LLM做决策（默认） |

**LLM决策流程**:

1. **种子决策**: 如果candidate.label已在backbone_concepts中 → 直接 `reuse_backbone`

2. **批量处理**: 每批次8个候选发送给LLM

3. **Prompt构建**:
```
You are a knowledge graph attachment assistant.

Backbone anchors:
- Asset: Physical equipment, platform, or system being maintained
- Component: Hardware part, module, or subassembly
- Signal: Measurement, observation, or complaint indication
- Fault: Failure mode, defect, or error boundary

Candidates:
[
  {
    "candidate_id": "battery::seepage",
    "label": "seepage",
    "description": "seepage or leakage complaint",
    "routing_features": {"semantic_type_hint": "Signal", ...},
    "retrieved_anchors": [{"anchor": "Signal", "score": 0.89}]
  },
  ...
]

For each candidate, decide:
{
  "candidate_id": "...",
  "route": "vertical_specialize|reuse_backbone|reject",
  "parent_anchor": "...",
  "accept": true|false,
  "confidence": 0.0-1.0,
  "justification": "..."
}
```

4. **LLM返回**:
```json
{
  "domain_id": "battery",
  "decisions": [
    {
      "candidate_id": "battery::seepage",
      "label": "seepage",
      "route": "vertical_specialize",
      "parent_anchor": "Signal",
      "accept": true,
      "admit_as_node": true,
      "reject_reason": null,
      "confidence": 0.95,
      "justification": "type=Signal; anchor=Signal; priors=agree; reason=explicit complaint signal"
    },
    {
      "candidate_id": "battery::Aurex BatteryHub-612 LR",
      "label": "Aurex BatteryHub-612 LR",
      "route": "vertical_specialize",
      "parent_anchor": "Asset",
      "accept": true,
      "admit_as_node": true,
      "confidence": 0.92,
      "justification": "type=Asset; anchor=Asset; reason=explicitly named platform"
    },
    {
      "candidate_id": "battery::some vague thing",
      "label": "some vague thing",
      "route": "reject",
      "parent_anchor": null,
      "accept": false,
      "admit_as_node": false,
      "reject_reason": "low_graph_value",
      "confidence": 0.0,
      "justification": "insufficient evidence, generic placeholder"
    }
  ]
}
```

**输出**: `dict[candidate_id, AttachmentDecision]`

```json
{
  "battery::seepage": {
    "candidate_id": "battery::seepage",
    "label": "seepage",
    "route": "vertical_specialize",
    "parent_anchor": "Signal",
    "accept": true,
    "admit_as_node": true,
    "confidence": 0.95,
    "evidence_ids": ["BATOM_001"]
  },
  "battery::Aurex BatteryHub-612 LR": {
    "candidate_id": "battery::Aurex BatteryHub-612 LR",
    "route": "vertical_specialize",
    "parent_anchor": "Asset",
    "accept": true,
    "admit_as_node": true
  }
}
```

---

### 2.6 规则过滤阶段 (filtering.py + relation_filtering.py)

**职责**: 应用安全护栏，剔除低质量候选

#### 2.6a 节点过滤 (filtering.py)

| 过滤规则 | 说明 |
|----------|------|
| 人名字段过滤 | 匹配Person_name模式 → reject |
| 文档标题过滤 | 匹配document title模式 → reject |
| 通用占位符过滤 | "failure", "fault", "problem"等 → reject |
| Backbone精确匹配 | reuse_backbone需label在backbone中 |
| vertical_specialize验证 | parent_anchor必须在backbone中 |
| Task不允许作为parent | vertical_specialize的parent不能是Task |

#### 2.6b 关系过滤 (relation_filtering.py)

| Family | 过滤规则 |
|--------|----------|
| `structural` | contextual head (branch/path/condition) → reject; 非Asset/Component端点 → reject |
| `communication` | indicates关系中generic target → reject |
| `lifecycle` | transitionsTo中低价值端点 → reject |
| `task_dependency` | semantic→workflow方向 → reject |

**过滤后的Decision**:
```json
{
  "battery::seepage": {
    "route": "vertical_specialize",
    "parent_anchor": "Signal",
    "accept": true  // 通过所有规则
  },
  "battery::some vague thing": {
    "route": "reject",
    "reject_reason": "low_graph_value",
    "accept": false  // 被规则过滤
  }
}
```

---

### 2.7 图谱组装阶段 (graph.py)

**职责**: 实例化GraphNode和GraphEdge

#### 2.7a Workflow Step节点

每个 `step_record` 创建一个workflow_step节点：

```json
{
  "node_id": "battery::node::BATOM_001:T1",
  "label": "BATOM_001:T1",
  "display_label": "Record coolant condition (T1)",
  "domain_id": "battery",
  "node_type": "workflow_step",
  "node_layer": "workflow",
  "parent_anchor": null,
  "surface_form": "At the left-rear coolant-plate outlet on Aurex BatteryHub-612 LR, record the complaint as seepage...",
  "step_id": "T1",
  "order_index": 1,
  "provenance_evidence_ids": ["BATOM_001"],
  "valid_from": "2026-04-22T11:57:41Z"
}
```

#### 2.7b 语义节点

从 `concept_mentions` 中提取，仅包含 `admit_as_node=true`：

```json
{
  "node_id": "battery::node::seepage",
  "label": "seepage",
  "display_label": "seepage",
  "domain_id": "battery",
  "node_type": "adapter_concept",
  "node_layer": "semantic",
  "parent_anchor": "Signal",
  "description": "seepage or leakage complaint",
  "provenance_evidence_ids": ["BATOM_001"],
  "valid_from": "2026-04-22T11:57:41Z"
}
```

Backbone节点：
```json
{
  "node_id": "battery::node::Asset",
  "label": "Asset",
  "node_type": "backbone_concept",
  "node_layer": "semantic"
}
```

#### 2.7c 边的分类

**task_dependency分类逻辑** (`_classify_task_dependency`):

```python
if _extract_step_id(raw_head) and _extract_step_id(raw_tail):
    return ("workflow", "sequence", None)      # T1 → T2
if _extract_step_id(raw_head):
    return ("workflow", "action_object", None)  # T1 → seepage
if head_layer == "workflow" and tail_layer == "workflow":
    return ("workflow", "sequence", None)
if head_layer == "workflow" and tail_layer == "semantic":
    return ("workflow", "action_object", None)
if head_layer == "semantic" and tail_layer == "workflow":
    return ("semantic", None, "semantic_to_workflow_not_allowed")  # reject
```

**Workflow Sequence边** (T1 → T2):
```json
{
  "edge_id": "battery::edge::BATOM_001:T1::triggers::BATOM_001:T2",
  "label": "triggers",
  "family": "task_dependency",
  "edge_layer": "workflow",
  "workflow_kind": "sequence",
  "head": "BATOM_001:T1",
  "tail": "BATOM_001:T2",
  "provenance_evidence_ids": ["BATOM_001"]
}
```

**Workflow Grounding边** (T1 → seepage):
```json
{
  "edge_id": "battery::edge::BATOM_001:T1::observes::seepage",
  "label": "observes",
  "family": "task_dependency",
  "edge_layer": "workflow",
  "workflow_kind": "action_object",
  "head": "BATOM_001:T1",
  "tail": "seepage",
  "provenance_evidence_ids": ["BATOM_001"]
}
```

**Semantic边** (Asset contains Component):
```json
{
  "edge_id": "battery::edge::Aurex BatteryHub-612 LR::contains::left-rear coolant-plate outlet",
  "label": "contains",
  "family": "structural",
  "edge_layer": "semantic",
  "workflow_kind": null,
  "head": "Aurex BatteryHub-612 LR",
  "tail": "left-rear coolant-plate outlet",
  "provenance_evidence_ids": ["BATOM_001"]
}
```

#### 2.7d Triple状态

```json
{
  "triple_id": "battery::triple::BATOM_001::1",
  "head": "BATOM_001:T1",
  "relation": "observes",
  "tail": "seepage",
  "relation_family": "task_dependency",
  "graph_layer": "workflow",
  "workflow_kind": "action_object",
  "status": "accepted",
  "reject_reason": null
}
```

Rejected Triple:
```json
{
  "triple_id": "battery::triple::BATOM_001::99",
  "head": "dry",
  "relation": "transitionsTo",
  "tail": "wet",
  "status": "rejected",
  "reject_reason": "lifecycle_low_value_target"
}
```

---

### 2.8 制品导出阶段 (artifacts.py)

**职责**: 导出所有产物文件

**输出文件列表**:

| 文件 | 路径 | 内容 |
|------|------|------|
| `run_meta.json` | `{output_dir}/` | variant元信息 |
| `construction_summary.json` | `{output_dir}/` | 统计汇总 |
| `final_graph.json` | `working/{domain}/` | 最终图谱 |
| `attachment_audit.json` | `working/{domain}/` | 候选+决策审计 |
| `relation_audit.json` | `working/{domain}/` | 关系验证审计 |
| `adapter_schema.json` | `working/{domain}/` | 域schema |
| `attachment_decisions.json` | `working/{domain}/` | 完整决策 |
| `retrievals.json` | `working/{domain}/` | 嵌入检索结果 |
| `nodes.csv` | `exports/graph_db/` | 节点CSV |
| `edges.csv` | `exports/graph_db/` | 边CSV |
| `{domain}.graphml` | `graphml/{variant}/` | GraphML格式 |

#### final_graph.json格式

```json
{
  "domain_id": "battery",
  "summary": {
    "node_count": 85,
    "edge_count": 62,
    "workflow_step_node_count": 24,
    "semantic_node_count": 61,
    "workflow_edge_count": 20,
    "semantic_edge_count": 42,
    "candidate_triple_count": 95,
    "accepted_triple_count": 62,
    "rejected_triple_count": 20,
    "type_rejected_triple_count": 13
  },
  "nodes": [
    {"node_id": "...", "label": "...", "node_type": "...", ...},
    ...
  ],
  "edges": [
    {"edge_id": "...", "label": "...", "head": "...", "tail": "...", ...},
    ...
  ]
}
```

---

## 3. 数据格式变化追踪

### 3.1 概念从文本到节点

```
原始文本: "coolant concentration" (在T1步骤文本中)
    │
    ▼ [LLM抽取]
ExtractionResult.concepts:
    {"label": "coolant concentration", "semantic_type_hint": "Signal"}
    │
    ▼ [证据构建]
EvidenceRecord.step_records[0].concept_mentions:
    {"label": "coolant concentration", "semantic_type_hint": "Signal", ...}
    │
    ▼ [候选聚合]
SchemaCandidate:
    {
      "candidate_id": "battery::coolant concentration",
      "routing_features": {"semantic_type_hint": "Signal", "evidence_count": 1}
    }
    │
    ▼ [嵌入检索]
RetrievedAnchors:
    [{"anchor": "Signal", "score": 0.89, "rank": 1}]
    │
    ▼ [Attachment决策]
AttachmentDecision:
    {
      "route": "vertical_specialize",
      "parent_anchor": "Signal",
      "accept": true,
      "admit_as_node": true
    }
    │
    ▼ [规则过滤]
Filtered Decision: (通过所有规则)
    │
    ▼ [图谱组装]
GraphNode:
    {
      "node_id": "battery::node::coolant concentration",
      "label": "coolant concentration",
      "node_type": "adapter_concept",
      "node_layer": "semantic",
      "parent_anchor": "Signal"
    }
```

### 3.2 关系从文本到边

```
原始文本: "T1 observes seepage" (LLM从T1步骤提取)
    │
    ▼ [LLM抽取]
ExtractionResult.relations:
    {"label": "observes", "family": "task_dependency", "head": "T1", "tail": "seepage"}
    │
    ▼ [证据构建]
EvidenceRecord.step_records[0].relation_mentions:
    {"label": "observes", "family": "task_dependency", "head": "T1", "tail": "seepage"}
    │
    ▼ [图谱组装 - 关系分类]
CandidateTriple:
    {
      "head": "BATOM_001:T1",
      "relation": "observes",
      "tail": "seepage",
      "relation_family": "task_dependency",
      "graph_layer": "workflow",
      "workflow_kind": "action_object"  ← head是T1，tail是概念
    }
    │
    ▼ [关系过滤]
Filtered Triple: (通过task_dependency规则)
    │
    ▼ [类型约束验证]
Validated Triple: (端点类型符合约束)
    │
    ▼ [最终状态]
GraphEdge:
    {
      "edge_id": "battery::edge::BATOM_001:T1::observes::seepage",
      "label": "observes",
      "family": "task_dependency",
      "edge_layer": "workflow",
      "workflow_kind": "action_object",
      "head": "BATOM_001:T1",
      "tail": "seepage"
    }
```

---

## 4. Workflow层结构

CrossExtend-KG的核心创新是引入**Workflow层**，建模O&M操作步骤：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         三层KG架构                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [语义层]              Asset                                        │
│      │                    │                                        │
│      │ contains           │ contains                               │
│      ▼                    ▼                                        │
│  Component ───────► Signal ───────► Fault                          │
│      │                    │            │                           │
│      │                    │ indicates  │                           │
│      ▼                    ▼            ▼                           │
│  具体硬件            具体信号        具体故障                        │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Workflow层]                                                       │
│                                                                     │
│  [T1] ──triggers──► [T2] ──triggers──► [T3] ──triggers──► [T4]      │
│   │                   │                   │                   │     │
│   │                   │                   │                   │     │
│   ▼                   ▼                   ▼                   ▼     │
│  [接地层] - 步骤与对象的关联                                          │
│                                                                     │
│  T1 ──observes──► seepage (Signal)                                 │
│  T1 ──captures──► coolant concentration (Signal)                   │
│  T2 ──exposes──► aluminum outlet neck (Component)                  │
│  T3 ──inspects──► latch window (Component)                         │
│  T4 ──observes──► connector shell (Component)                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Workflow Step节点识别**:
```python
def _is_workflow_step_node(node):
    # 三种识别方式:
    # 1. node_type == "workflow_step"
    # 2. node_layer == "workflow"
    # 3. label 匹配 T\d+ 模式 (如 T1, T2)
```

---

## 5. LLM调用总结

| 阶段 | 文件 | 调用次数 | 模板 | 输入 | 输出 |
|------|------|----------|------|------|------|
| 预处理抽取 | `extractor.py` | 每文档1次 | `preprocessing_extraction_om.txt` | Markdown内容 | concepts + relations |
| Attachment决策 | `attachment.py` | 每8候选1次 | `attachment_judge.txt` | 候选列表 + 检索结果 | decisions |

**LLM后端配置** (`backends/llm.py`):
```python
client = openai.OpenClient(base_url=config.llm_backend_url)
response = client.chat.completions.create(
    model=config.llm_model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    max_tokens=4096,
    response_format={"type": "json_object"}
)
```

---

## 6. 配置文件说明

### 6.1 Pipeline配置 (`config/persistent/pipeline.deepseek.yaml`)

```yaml
variant_id: full_llm
description: Full LLM pipeline with rule filtering
preprocessing_source: llm
attachment_strategy: llm
use_rule_filter: true
use_embedding_routing: true
llm_backend: deepseek_chat
embedding_backend: local_sentence_transformers
enable_snapshots: false

data_paths:
  battery:
    evidence_records_path: data/evidence_records/full_human_gold_9doc/battery_evidence_records_llm.json
    source_types: [om_manual]
  cnc:
    evidence_records_path: data/evidence_records/full_human_gold_9doc/cnc_evidence_records_llm.json
    source_types: [om_manual]
  nev:
    evidence_records_path: data/evidence_records/full_human_gold_9doc/nev_evidence_records_llm.json
    source_types: [om_manual]

ground_truth_dir: data/ground_truth
output_dir: results/full_llm
```

### 6.2 Backbone配置 (`config/persistent/embedding_backends.yaml`)

```yaml
backbone_descriptions:
  Asset: "Physical equipment, platform, or system being maintained"
  Component: "Hardware part, module, or subassembly"
  Signal: "Measurement, observation, or complaint indication"
  State: "Operating condition or status"
  Fault: "Failure mode, defect, or error boundary"
  Task: "O&M procedure step or maintenance action"
```

---

## 7. 运行命令

```bash
# 运行完整pipeline
python -m crossextend_kg.pipeline.runner \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir results/full_llm

# 运行消融实验
python -m crossextend_kg.experiments.ablation.runner \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir results/ablation \
  --ground-truth-dir data/ground_truth

# 运行基线实验
python scripts/run_baselines.py \
  --config config/persistent/pipeline.deepseek.yaml \
  --output-dir results/baselines
```

---

## 8. 文件路径索引

| 阶段 | 输入文件 | 输出文件 |
|------|----------|----------|
| 解析 | `data/{domain}_om_manual_en/*.md` | `DocumentInput` (内存) |
| LLM抽取 | `DocumentInput` | `ExtractionResult` (内存) |
| 证据构建 | `ExtractionResult` | `data/evidence_records/*/{domain}_evidence_records_llm.json` |
| 候选聚合 | `EvidenceRecord` | `SchemaCandidate` (内存) |
| 嵌入检索 | `SchemaCandidate` | `retrievals.json` |
| Attachment | `SchemaCandidate + retrievals` | `attachment_decisions.json` |
| 图谱组装 | `AttachmentDecision` | `final_graph.json` |
| 导出 | `final_graph.json` | `graphml/*.graphml`, `exports/*.csv` |

---

## 9. 关键设计决策

### 9.1 为什么用两阶段LLM?

1. **预处理抽取**: 处理原始文本 → EvidenceRecord（按步骤组织）
2. **Attachment决策**: 处理候选概念 → 决定图谱连接方式

**分离的好处**:
- 预处理可替换为规则方法（消融实验）
- Attachment决策可替换为embedding_top1（消融实验）
- 两阶段可独立优化

### 9.2 为什么EvidenceRecord按步骤组织?

- Workflow Step节点需要从步骤文本中提取
- 步骤-对象关联（action_object边）需要知道概念属于哪个步骤
- 支持隐式步骤链重建（T1→T2→T3）

### 9.3 为什么需要规则过滤?

LLM可能产生:
- 人名误识别
- 文档标题误识别
- 通用占位符
- 低价值关系

规则过滤作为**安全护栏**，确保图谱质量。

---

## 10. 参考文献

- `docs/SYSTEM_DESIGN.md` -- 系统设计原则
- `docs/WORKFLOW_KG_DESIGN.md` -- Workflow层架构
- `docs/MANUAL_ANNOTATION_PROTOCOL.md` -- Ground Truth标注规范
- `data/ground_truth/template/document_gold.annotation_spec.md` -- 标注格式规范