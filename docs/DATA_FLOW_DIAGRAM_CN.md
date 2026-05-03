# CrossExtend-KG v2：完整数据流图

本文档使用**真实单文档示例**，追踪数据经过每个管线阶段时的精确输入/输出格式变化。示例文档为 battery 域的 `Battery_Module_Busbar_Insulator_Shield_Inspection.md`。

---

## 总览：管线阶段

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Stage 0    │────▶│  Stage 1         │────▶│  Stage 2        │
│  源文本      │     │  预处理           │     │  证据加载       │
│  (.md)       │     │  (LLM API)       │     │  & 规范化       │
└─────────────┘     └──────────────────┘     └─────────────────┘
                                                     │
┌─────────────┐     ┌──────────────────┐     ┌───────▼─────────┐
│  Stage 5    │◀────│  Stage 4         │◀────│  Stage 3        │
│  导出        │     │  图组装           │     │  挂靠路由       │
│  (JSON/ML)  │     │  (双层)           │     │  (Embed+LLM)    │
└─────────────┘     └──────────────────┘     └─────────────────┘
```

| 阶段 | 输入 | 输出 | 外部 API |
|------|------|------|---------|
| 0 | 原始 O&M 手册 | Markdown 表格 | 无 |
| 1 | Markdown 文本 | EvidenceRecord (v2 JSON) | DeepSeek LLM |
| 2 | EvidenceRecord | SchemaCandidate[] | 无 |
| 3 | SchemaCandidate[] + Backbone | AttachmentDecision[] | DashScope Embedding + DeepSeek LLM |
| 4 | AttachmentDecision[] + EvidenceRecord | 双层图 | 无 |
| 5 | 图 | final_graph.json + .graphml | 无 |

---

## Stage 0：源文本

**文件**: `data/battery_om_manual_en/Battery_Module_Busbar_Insulator_Shield_Inspection.md`

**格式**：双列 Markdown 表格（`Time step` 和 `O&M sample text`），包含 7 个操作步骤（T1–T7）。

**输入内容**（原文）：

```markdown
| Time step | O&M sample text |
|---|---|
| T1 | For Velorian ModuleShield-584, record whether the busbar-insulator review follows an electrical event, dropped-tool incident, or routine service access, and identify the exact module section carrying the suspect shield. Photograph the shield edge and the exposed busbar geometry before anything is shifted. |
| T2 | Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam barriers, and cover ribs without moving the shield from its as-found seat. The shield edge and the underlying busbar have to be judged together because an intact shield can still be unsafe if it is mis-seated. |
| T3 | Inspect the shield for cracks, heat spots, missing tabs, rub marks, trimmed openings, or loss of stand-off at the busbar edge and stud shoulder. Record which retaining feature or edge actually lost coverage. |
| T4 | Compare the suspect shield position with the neighboring shield or with the untouched side of the same module so tab engagement, stand-off, and busbar coverage are judged against a real reference. This prevents a cosmetic acceptance of a misaligned but unbroken part. |
| T5 | Inspect the neighboring foam barriers and cover ribs for contact witness that could push the shield sideways during closure, then restore only the failed tab, shield panel, or interfering support feature. The coverage path from retaining tab to busbar edge has to remain explicit. |
| T6 | Refit surrounding parts and confirm that the shield still maintains the required stand-off to the busbar edges and stud exits after final loading. A shield that sits correctly only before the cover rib is installed is not acceptable. |
| T7 | End the insulator review only when the note names the exact concern, such as cracked shield panel, missing retaining tab, mis-seated shield edge, or cover-rib interference, and ties it to the final coverage result. The release boundary is a shield that fully covers the intended busbar edges and holds position after the neighboring foam and cover features are restored. |
```

**数据约定**：文件名（`Battery_Module_Busbar_Insulator_Shield_Inspection.md`）决定了管线全程使用的 `evidence_id`。第一列的 `T<n>` 标签定义了 workflow 步骤顺序。

---

## Stage 1：预处理提取（LLM API）

**API**: DeepSeek v4 Pro (`deepseek-v4-pro`)
**Prompt**: `config/prompts/preprocessing_extraction_om.txt`

LLM 对每个文档调用一次。输入包括：
- Stage 0 的原始 markdown 文本
- 15 概念 backbone 及其描述
- 提取指令（概念提取、关系提取、上位词分类、步骤阶段分类）

### Stage 1 输出：EvidenceRecord v2

**文件**: `data/evidence_records/test1_battery.json`

**格式**：JSON 对象，顶层结构如下：

```json
{
  "project_name": "crossextend_kg_preprocessing",
  "generated_at": "2026-04-25T19:10:12Z",
  "domains": ["battery"],
  "role": "target",
  "document_count": 1,
  "domain_stats": { "battery": { "om_manual": 1 } },
  "evidence_records": [ /* EvidenceRecord[] */ ]
}
```

每个 `EvidenceRecord` 的结构（v2 新增字段标记 **[v2]**）：

```json
{
  "evidence_id": "Battery_Module_Busbar_Insulator_Shield_Inspection",
  "domain_id": "battery",
  "role": "target",
  "source_type": "om_manual",
  "timestamp": "2026-04-25T19:09:32Z",
  "raw_text": "<Stage 0 的原始 markdown>",
  "step_records": [ /* StepEvidenceRecord[] */ ],
  "document_concept_mentions": [],
  "document_relation_mentions": [ /* RelationMention[] */ ],
  "procedure_meta": {                    /** [v2] **/
    "asset_name": null,
    "procedure_type": "inspection",
    "primary_fault_type": null
  },
  "cross_step_relations": [              /** [v2] **/
    { "label", "family", "head", "tail", "head_step", "tail_step" }
  ]
}
```

### StepEvidenceRecord：v1 与 v2 对比

**v1 字段**（保留以向后兼容）：

```json
{
  "step_id": "T1",
  "task": {
    "label": "T1",
    "kind": "concept",
    "surface_form": "For Velorian ModuleShield-584, record whether..."
  },
  "concept_mentions": [
    {
      "label": "Velorian ModuleShield-584",
      "kind": "concept",
      "description": "the specific module shield assembly under review",
      "node_worthy": true,
      "surface_form": "Velorian ModuleShield-584",
      "semantic_type_hint": "Asset"
    }
  ],
  "relation_mentions": [
    { "label": "records", "family": "task_dependency", "head": "T1", "tail": "shield edge" },
    { "label": "triggers", "family": "task_dependency", "head": "T1", "tail": "T2" }
  ]
}
```

**v2 新增字段**（全部可选，有默认值）：

```json
{
  "step_phase": "observe",             /** [v2] observe/diagnose/repair/verify */
  "step_summary": "For Velorian ModuleShield-584, record whether...", /** [v2] */
  "surface_form": "For Velorian ModuleShield-584, record whether...", /** [v2] 独立副本 */
  "step_actions": [                    /** [v2] 替代 relation_mentions 用于接地 */
    { "action_type": "records", "target_label": "shield edge" },
    { "action_type": "records", "target_label": "module section" },
    { "action_type": "records", "target_label": "exposed busbar geometry" }
  ],
  "structural_edges": [],              /** [v2] 分离的结构边 */
  "state_transitions": [],             /** [v2] 生命周期状态变更 */
  "diagnostic_edges": [],              /** [v2] 通信/传播边 */
  "sequence_next": "T2"               /** [v2] 替代合成 triggers */
}
```

### 真实 Step T2 示例（v2 完整输出）

```json
{
  "step_id": "T2",
  "task": { "label": "T2", "kind": "concept", "node_worthy": true,
    "surface_form": "Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam barriers, and cover ribs without moving the shield from its as-found seat..." },
  "concept_mentions": [
    { "label": "as-found seat", "semantic_type_hint": "State", "shared_hypernym": null },
    { "label": "busbar edges", "semantic_type_hint": "Component", "shared_hypernym": null },
    { "label": "busbar shield", "semantic_type_hint": "Component", "shared_hypernym": "Housing" },
    { "label": "cover ribs", "semantic_type_hint": "Component", "shared_hypernym": "Housing" },
    { "label": "foam barriers", "semantic_type_hint": "Component", "shared_hypernym": "Seal" },
    { "label": "retaining tabs", "semantic_type_hint": "Component", "shared_hypernym": "Fastener" },
    { "label": "stud exits", "semantic_type_hint": "Component", "shared_hypernym": null }
  ],
  "relation_mentions": [
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "busbar shield" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "retaining tabs" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "busbar edges" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "stud exits" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "foam barriers" },
    { "label": "exposes", "family": "task_dependency", "head": "T2", "tail": "cover ribs" },
    { "label": "triggers", "family": "task_dependency", "head": "T2", "tail": "T3" }
  ],
  "step_phase": null,
  "step_summary": "Expose the busbar shield, retaining tabs, busbar edges, stud exits, foam",
  "step_actions": [
    { "action_type": "exposes", "target_label": "busbar shield" },
    { "action_type": "exposes", "target_label": "retaining tabs" },
    { "action_type": "exposes", "target_label": "busbar edges" },
    { "action_type": "exposes", "target_label": "stud exits" },
    { "action_type": "exposes", "target_label": "foam barriers" },
    { "action_type": "exposes", "target_label": "cover ribs" }
  ],
  "structural_edges": [],
  "state_transitions": [],
  "diagnostic_edges": [],
  "sequence_next": "T3"
}
```

### StepEvidenceRecord 中 v1→v2 关键差异

| 方面 | v1 | v2 |
|------|----|----|
| 步骤阶段 | 未捕获 | `step_phase`：observe/diagnose/repair/verify |
| 步骤-概念接地 | 通过 `relation_mentions`，`family="task_dependency"` | 通过 `step_actions[]`（干净的 `StepAction` 记录） |
| 步骤序列 | 通过合成的 `triggers` 关系 | 通过 `sequence_next`（直接下一跳指针） |
| 结构边 | 混在 `relation_mentions` 中 | 分离到 `structural_edges[]` |
| 诊断边 | 混在 `relation_mentions` 中 | 分离到 `diagnostic_edges[]` |
| 状态变迁 | 未捕获 | `state_transitions[]` |
| 上位词 | 概念上未捕获 | `shared_hypernym` 在 `ConceptMention` 上 |

### 文档级 v2 新增

**`procedure_meta`**：从文档内容推断：
```json
{
  "asset_name": null,
  "procedure_type": "inspection",
  "primary_fault_type": null
}
```

**`cross_step_relations`**：5 条跨步骤诊断关系（T3→T7）：
```json
[
  { "label": "indicates", "family": "communication", "head": "contact witness", "tail": "interfering support feature", "head_step": "T5", "tail_step": "T5" },
  { "label": "indicates", "family": "communication", "head": "loss of stand-off", "tail": "mis-seated shield edge", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "missing tabs", "tail": "missing retaining tab", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "cracks", "tail": "cracked shield panel", "head_step": "T3", "tail_step": "T7" },
  { "label": "indicates", "family": "communication", "head": "rub marks", "tail": "cover-rib interference", "head_step": "T3", "tail_step": "T7" }
]
```

这些跨步骤关系捕获了 T3 中观测到的故障信号（cracks、rub marks、missing tabs、loss of stand-off）在 T7 中被解析为具体故障诊断（cracked shield panel、cover-rib interference、missing retaining tab、mis-seated shield edge）。

### 文档级关系（v1 字段，仍保留）

6 条结构 `contains` 关系 + 5 条通信 `indicates` 关系：
```json
[
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "busbar shield" },
  { "label": "contains", "family": "structural", "head": "busbar shield", "tail": "retaining tabs" },
  { "label": "contains", "family": "structural", "head": "busbar shield", "tail": "shield edge" },
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "foam barriers" },
  { "label": "contains", "family": "structural", "head": "Velorian ModuleShield-584", "tail": "cover ribs" },
  { "label": "indicates", "family": "communication", "head": "contact witness", "tail": "interfering support feature" },
  { "label": "indicates", "family": "communication", "head": "loss of stand-off", "tail": "mis-seated shield edge" },
  { "label": "indicates", "family": "communication", "head": "missing tabs", "tail": "missing retaining tab" },
  { "label": "indicates", "family": "communication", "head": "cracks", "tail": "cracked shield panel" },
  { "label": "indicates", "family": "communication", "head": "rub marks", "tail": "cover-rib interference" }
]
```

---

## Stage 2：证据加载与规范化

**无 API 调用。** 纯 Python 变换。

管线加载 EvidenceRecord 并聚合语义候选：

- 每个 `concept_mentions` 中 `node_worthy=true` 的条目成为一个 `SchemaCandidate`
- 标签规范化（去除尾部标点、空格归一化）
- `shared_hypernym` 传播到 `routing_features["shared_hypernym"]`
- `semantic_type_hint` 传播到 `routing_features["semantic_type_hint"]`
- 为每个候选计算文档级关系统计（`relation_participation_count`、`relation_head_count`、`relation_tail_count`、`relation_families`）

**输出**：37 个 `SchemaCandidate` 对象（来自 7 个步骤中 37 个 `node_worthy=true` 的概念提及）

"Velorian ModuleShield-584" 的候选示例：
```json
{
  "candidate_id": "battery::Velorian ModuleShield-584",
  "domain_id": "battery",
  "label": "Velorian ModuleShield-584",
  "description": "the specific module shield assembly under review",
  "evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "routing_features": {
    "evidence_count": 1,
    "relation_participation_count": 3,
    "relation_head_count": 3,
    "relation_tail_count": 0,
    "relation_families": ["structural"],
    "step_ids": ["T1"],
    "semantic_type_hint": "Asset",
    "semantic_type_hint_candidates": ["Asset"],
    "support_count": 1,
    "shared_hypernym": "Housing"
  }
}
```

注意 `shared_hypernym: "Housing"` 从 `ConceptMention` 传播到了 `routing_features`，在挂靠阶段启用锚点回退。

---

## Stage 3：Backbone 路由与挂靠（Embedding + LLM）

**API**：DashScope text-embedding-v4（向量嵌入）+ DeepSeek Chat（LLM 判断）

### Step 3a：Embedding 检索

每个候选的标签通过 DashScope text-embedding-v4 嵌入。嵌入向量与预计算的 backbone 概念嵌入进行余弦相似度比较。

分批处理：DashScope API 每次请求最多接受 10 个文本。管线自动分批：37 个候选分为 4 批（10+10+10+7）。

"Velorian ModuleShield-584" 的真实检索结果：
```
Anchor: Component  → score: 0.4249  (rank 1)
Anchor: Sensor     → score: 0.3825  (rank 2)
Anchor: Housing    → score: 0.3688  (rank 3)
```

### Step 3b：LLM 挂靠判断

LLM 接收候选的描述、嵌入先验、路由特征（包含 `shared_hypernym`），做出挂靠决策。

"Velorian ModuleShield-584" 的真实 LLM 决策：
```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Component",
  "accept": true,
  "admit_as_node": true,
  "confidence": 0.85,
  "justification": "type=Component; anchor=Component; priors=conflict; reason=Specific named shield assembly, structural relations, semantic type Asset but better grounded as Component under Housing."
}
```

### Step 3c：挂靠审计汇总

| 指标 | 数量 |
|------|------|
| 候选总数 | 37 |
| 接受为 adapter | 34 |
| 接受为 backbone 复用 | 0 |
| 拒绝 | 3 |

**被拒绝的候选**（含原因）：

| 标签 | 拒绝原因 |
|------|---------|
| `busbar-insulator review` | `observation_like_not_grounded` |
| `untouched side` | `low_graph_value` |
| `release boundary` | `low_graph_value` |

### Step 3d：父锚点分配

34 个被接受的候选分配到 backbone 锚点：

| parent_anchor | 数量 | 示例概念 |
|---------------|------|---------|
| Fault | 9 | cracks, heat spots, missing tabs, rub marks, loss of stand-off, ... |
| Component | 7 | exposed busbar geometry, busbar edges, module section, stud exits, ... |
| Housing | 4 | busbar shield, cover ribs, shield edge, neighboring shield, shield panel |
| State | 3 | as-found seat, busbar coverage, tab engagement, final coverage result |
| Signal | 3 | contact witness, coverage path, required stand-off |
| Fastener | 2 | retaining tabs, stud shoulder |
| Asset | 1 | Velorian ModuleShield-584 |
| Seal | 1 | foam barriers |
| ... | ... | （其余 Tier-1 锚点下有 0 个 adapter 概念） |

---

## Stage 4：图组装（双层）

**无 API 调用。** 纯 Python 图构建。

图组装器消费 AttachmentDecisions + EvidenceRecord 构建双层图。

### Workflow 层构建

**Workflow 步骤节点**（共 7 个）：每个 `step_records` 条目生成一个节点。

每个 workflow 节点包含：
- `node_id`：运行时节点 ID，例如 `"battery::node::Battery_Module_Busbar_Insulator_Shield_Inspection:T1"`
- `label`：带文档作用域的 workflow 标签，例如 `"Battery_Module_Busbar_Insulator_Shield_Inspection:T1"`
- `step_id`：原始步骤号（`"T1"` 到 `"T7"`）
- `node_type`："workflow_step"
- `step_phase`：来自 `StepEvidenceRecord.step_phase`
- `display_label`：优先由已接地的 workflow 动作 + 对象推导出的可读短标题；如果推导不出来，再回退到截断步骤文本
- `surface_form` / `provenance_evidence_ids`：完整步骤原文和来源文档证据

| Step | Phase | Display Label |
|------|-------|---------------|
| T1 | observe | "Record busbar-insulator review (T1)" |
| T2 | (null) | "Expose local assembly (T2)" |
| T3 | observe | "Inspect fault boundary (T3)" |
| T4 | diagnose | "Compare reference dimensions (T4)" |
| T5 | observe | "Inspect contact witness (T5)" |
| T6 | verify | "Verify required stand-off (T6)" |
| T7 | observe | "Inspect fault boundary (T7)" |

**Workflow 序列边**（共 6 条）：T1→T2→T3→T4→T5→T6→T7
- 来源：`sequence_next` 字段（v2 权威来源）
- 存储的 `family`：`task_dependency`
- 存储的 `workflow_kind`：`sequence`
- 存储的关系标签：`triggers`

**Workflow 接地边**（action_object，共 24 条）：

来源：`step_actions[]`（v2 权威来源；运行时不会再回退到 `relation_mentions`）。

| Step | 操作类型 | 目标概念 | 显示允许 |
|------|---------|---------|---------|
| T2 | exposes | busbar shield | 是 |
| T2 | exposes | busbar edges | 是 |
| T2 | exposes | stud exits | 是 |
| T2 | exposes | foam barriers | 是 |
| T2 | exposes | cover ribs | 是 |
| T3 | inspects | cracks | 是 |
| T3 | inspects | heat spots | 是 |
| T3 | inspects | missing tabs | 是 |
| T3 | inspects | rub marks | 是 |
| T3 | inspects | trimmed openings | 是 |
| T3 | inspects | loss of stand-off | 是 |
| T5 | inspects | contact witness | 是 |
| T5 | repairs | failed tab | 是 |
| T5 | repairs | interfering support feature | 是 |
| T6 | verifies | required stand-off | 是 |
| T7 | verifies | final coverage result | 是 |
| T1 | records | module section | 否（`record_requires_signal_like_target`） |
| T1 | records | shield edge | 否（`record_requires_signal_like_target`） |
| T1 | records | exposed busbar geometry | 否（`record_requires_signal_like_target`） |
| T2 | exposes | retaining tabs | 否（`expose_requires_component_target`） |
| T4 | compares | neighboring shield | 否（`compare_requires_grounded_target`） |
| T5 | repairs | shield panel | 否（`repair_requires_component_target`） |

### 语义层构建

**语义概念节点**（共 34 个）：来自被接受的挂靠决策。

每个语义节点包含：
- `label`：来自候选标签
- `node_type`："adapter_concept"
- `parent_anchor`：来自挂靠决策
- `shared_hypernym`：来自 routing_features（v2）

**语义边**（2 条被接受）：

均为关系验证器接受的结构 `contains` 边：

| Head | Relation | Tail | Family |
|------|----------|------|--------|
| Velorian ModuleShield-584 | contains | foam barriers | structural |
| Velorian ModuleShield-584 | contains | cover ribs | structural |

其他结构边被关系规则拒绝：
- `busbar shield` → `retaining tabs`：拒绝（`structural_requires_stable_components`）
- `busbar shield` → `shield edge`：拒绝（`structural_low_value_tail`）

通信边被类型约束拒绝（Fault 类型不允许作为通信族的 head）：
- `loss of stand-off` → `mis-seated shield edge`：拒绝（`type_constraint`）
- `missing tabs` → `missing retaining tab`：拒绝（`type_constraint`）
- `cracks` → `cracked shield panel`：拒绝（`type_constraint`）
- `rub marks` → `cover-rib interference`：拒绝（`type_constraint`）

### 关系验证汇总

| 类别 | 数量 | 详情 |
|------|------|------|
| 候选三元组总数 | 40 | |
| 接受 | 30 | |
| 拒绝（族规则） | 6 | structural_low_value_tail:1, structural_requires_stable_components:2, single_step_diagnostic_hypothesis:1, tail:not_in_graph:1, tail:low_graph_value:1 |
| 拒绝（类型约束） | 4 | Fault head 在通信族中 |

---

## Stage 5：导出

**无 API 调用。** 纯 Python 序列化。

### 输出：final_graph.json

**文件**: `results/test1/test1-20260425T191442Z/full_llm/working/battery/final_graph.json`

结构：
```json
{
  "domain_id": "battery",
  "summary": {
    "node_count": 41,
    "edge_count": 30,
    "workflow_step_node_count": 7,
    "semantic_node_count": 34,
    "workflow_edge_count": 28,
    "semantic_edge_count": 2,
    "readable_node_count": 24,
    "readable_edge_count": 24,
    "candidate_triple_count": 40,
    "accepted_triple_count": 30,
    "rejected_triple_count": 6,
    "type_rejected_triple_count": 4,
    "hypernym_coverage": 0.1471,
    "hypernym_distribution": { "Housing": 3, "Seal": 1, "Fastener": 1 },
    "phase_distribution": { "observe": 4, "diagnose": 1, "verify": 1 }
  },
  "nodes": [ ... ],
  "edges": [ ... ],
  "relation_validation": { ... }
}
```

### 节点格式（GraphNode）

`step_summary` 保留在 `StepEvidenceRecord` 上；进入最终图后，workflow 节点主要暴露
`display_label`、`surface_form` 和 provenance。

**Workflow 步骤节点示例**：
```json
{
  "node_id": "battery::node::Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "label": "Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "display_label": "Record busbar-insulator review (T1)",
  "domain_id": "battery",
  "node_type": "workflow_step",
  "node_layer": "workflow",
  "parent_anchor": null,
  "surface_form": "For Velorian ModuleShield-584, record whether the busbar-insulator review follows an electrical event...",
  "step_id": "T1",
  "order_index": 1,
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null,
  "lifecycle_stage": null,
  "shared_hypernym": null,
  "step_phase": "observe"
}
```

**语义 adapter 概念节点示例**：
```json
{
  "node_id": "battery::node::Velorian ModuleShield-584",
  "label": "Velorian ModuleShield-584",
  "display_label": "Velorian ModuleShield-584",
  "domain_id": "battery",
  "node_type": "adapter_concept",
  "node_layer": "semantic",
  "parent_anchor": "Component",
  "surface_form": "Velorian ModuleShield-584",
  "step_id": null,
  "order_index": null,
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null,
  "lifecycle_stage": null,
  "shared_hypernym": "Housing",
  "step_phase": null
}
```

### 边格式（GraphEdge）

**Workflow 序列边示例**：
```json
{
  "edge_id": "battery::edge::Battery_Module_Busbar_Insulator_Shield_Inspection:T1::triggers::Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "domain_id": "battery",
  "label": "triggers",
  "raw_label": "triggers",
  "display_label": "triggers",
  "family": "task_dependency",
  "edge_layer": "workflow",
  "workflow_kind": "sequence",
  "edge_salience": "high",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Battery_Module_Busbar_Insulator_Shield_Inspection:T1",
  "tail": "Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

**Workflow 接地边示例**：
```json
{
  "edge_id": "battery::edge::Battery_Module_Busbar_Insulator_Shield_Inspection:T2::exposes::busbar shield",
  "domain_id": "battery",
  "label": "exposes",
  "raw_label": "exposes",
  "display_label": "expose",
  "family": "action_object",
  "edge_layer": "workflow",
  "workflow_kind": "action_object",
  "edge_salience": "high",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Battery_Module_Busbar_Insulator_Shield_Inspection:T2",
  "tail": "busbar shield",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

**语义结构边示例**：
```json
{
  "edge_id": "battery::edge::Velorian ModuleShield-584::contains::foam barriers",
  "domain_id": "battery",
  "label": "contains",
  "raw_label": "contains",
  "display_label": "contains",
  "family": "structural",
  "edge_layer": "semantic",
  "workflow_kind": null,
  "edge_salience": "medium",
  "display_admitted": true,
  "display_reject_reason": null,
  "head": "Velorian ModuleShield-584",
  "tail": "foam barriers",
  "provenance_evidence_ids": ["Battery_Module_Busbar_Insulator_Shield_Inspection"],
  "valid_from": "2026-04-25T19:09:32Z",
  "valid_to": null
}
```

### GraphML 导出

同一图也导出为 `.graphml`，包含节点属性：
- `shared_hypernym`（在 adapter_concept 节点上）
- `step_phase`（在 workflow_step 节点上）
- `parent_anchor`（在 adapter_concept 节点上）

---

## 完整数据流汇总表

| 阶段 | 输入 | 关键变换 | 输出 | 涉及的 v2 字段 |
|------|------|---------|------|---------------|
| 0 | O&M markdown 表格 | 文件读取 | 原始文本字符串 | 无 |
| 1 | 原始文本 + prompt | LLM 提取 → JSON 转换 | 含 7 个 step_records 的 EvidenceRecord | `shared_hypernym`、`step_phase`、`step_actions`、`sequence_next`、`structural_edges`、`diagnostic_edges`、`state_transitions`、`procedure_meta`、`cross_step_relations` |
| 2 | EvidenceRecord | 聚合 `node_worthy` 概念 | 37 个 SchemaCandidate 对象 | `shared_hypernym` → `routing_features` |
| 3a | 候选标签 | 嵌入 → 余弦相似度 | 每个候选的检索先验 | 无（仅标签文本） |
| 3b | 候选 + 先验 + backbone | LLM 判断 → 接受/拒绝 + 锚点 | 34 个 AttachmentDecision | `shared_hypernym` 用作锚点回退 |
| 4 | 决策 + EvidenceRecord | 构建双层图 | 41 节点、30 边 | `step_phase` → 节点属性；`sequence_next` → 序列边；`step_actions` → 接地边；`shared_hypernym` → 节点属性 |
| 5 | 图 | 序列化 | final_graph.json + .graphml | `hypernym_coverage`、`phase_distribution` 在 summary 中 |

---

## 可视化：最终图拓扑（简化）

```
WORKFLOW 层                       语义层
==========                       ========

  T1 ─triggers→ T2 ─triggers→ T3 ─triggers→ T4 ─triggers→ T5 ─triggers→ T6 ─triggers→ T7
  (observe)      (null)      (observe)    (diagnose)   (observe)     (verify)     (observe)
  │              │           │            │            │             │            │
  │              ├─exposes→  ├─inspects→  ├─compares→  ├─inspects→   ├─verifies→  ├─verifies→
  │              │ busbar    │ cracks     │ neighbor   │ contact     │ required   │ final
  │              │ shield    │ heat spots │ shield     │ witness     │ stand-off  │ coverage
  │              │ busbar    │ missing    └            │             └            └
  │              │ edges     │ tabs                    ├─repairs→
  │              │ stud      │ rub marks              │ failed tab
  │              │ exits     │ trimmed                ├─repairs→
  │              │ foam      │ openings               │ interfering
  │              │ barriers  │ loss of                └
  │              │ cover     │ stand-off
  │              │ ribs      └
  │              └
  │              └─── 另见: Velorian ModuleShield-584 ─contains→ foam barriers
  │                                           └─contains→ cover ribs
  │
  └ (T1 接地边已隐藏: records→module section, shield edge, exposed busbar geometry)
```

---

## v2 增加了什么：三个创新支撑点

### 1. 通过 shared_hypernym 实现跨域泛化

在 v1 中，"busbar shield" 和假设的 CNC "spindle housing" 是互不相关的节点。在 v2 中，两者都携带 `shared_hypernym: "Housing"`，可以通过 Tier-1 backbone 进行跨域对齐。

在本示例中：
- `Velorian ModuleShield-584` → 上位词：**Housing**
- `busbar shield` → 上位词：**Housing**
- `cover ribs` → 上位词：**Housing**
- `foam barriers` → 上位词：**Seal**
- `retaining tabs` → 上位词：**Fastener**

### 2. 通过 step_phase 实现时序回溯

阶段分布呈现清晰的 O&M 程序模式：
- **observe**（T1, T3, T5, T7）：数据采集步骤
- **diagnose**（T4）：分析比较步骤
- **verify**（T6）：确认步骤

这支持下游任务如"哪一步诊断了故障？"或"追溯观测→诊断→验证路径。"

### 3. 通过 cross_step_relations 实现复杂传播路径

5 条跨步骤关系追踪故障信号传播：
```
T3:cracks ─indicates→ T7:cracked shield panel
T3:rub marks ─indicates→ T7:cover-rib interference
T3:missing tabs ─indicates→ T7:missing retaining tab
T3:loss of stand-off ─indicates→ T7:mis-seated shield edge
T5:contact witness ─indicates→ T5:interfering support feature
```

这捕获了 T3 中的故障观测在 T7 中被解析为具体诊断——一条 v1 的扁平 `relation_mentions` 无法表达的 4 步诊断传播链。
