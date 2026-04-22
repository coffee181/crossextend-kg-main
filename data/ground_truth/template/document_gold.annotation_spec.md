# Document Gold 标注规范

## 1. 目标

每个源文档对应一个 gold JSON。这个文件服务于主评测，因此必须保守、稳定、可复核。

当前模板分成两层：

- `concept_ground_truth` + `relation_ground_truth`
  继续服务 legacy strict 评测
- `workflow_relation_ground_truth`
  服务新的 workflow grounding 评测

## 2. Pipeline输出与评估匹配机制

### 2.1 Pipeline生成的Workflow Step节点格式

Pipeline在 `graph.py` 中生成的 workflow_step 节点结构：

```python
# label格式: "{evidence_id}:{step_id}"
label = "BATOM_001:T1"  # 例如

# display_label: 从原文提取的语义摘要 + step_id
display_label = "Record leak complaint and capture coolant concentration (T1)"

# 其他属性
step_id = "T1"
node_type = "workflow_step"
node_layer = "workflow"
surface_form = "完整原文..."
```

### 2.2 评估匹配机制

在 `experiments/metrics/core.py` 中，评估时通过 `normalize_step_label` 函数规范化：

```python
def normalize_step_label(label, doc_ids):
    # "BATOM_001:T1" → "T1" (剥离文档ID前缀)
    for doc_id in doc_ids:
        prefix = f"{doc_id}:"
        if label.startswith(prefix):
            tail = label[len(prefix):]
            if tail.startswith("T"):
                return tail  # 返回 "T1"
    return label.strip()
```

### 2.3 Gold标注的正确格式

**关键结论**：Gold标注的 workflow step `label` 可以是 `"T1"` 或 `"BATOM_001:T1"`，两者都能正确匹配。

推荐格式：
```json
{
  "label": "T1",                    // 用于评估匹配（必须）
  "surface_form": "完整原文...",     // 用于可读性（必须）
  "expected_anchor": "Task"         // 标识是workflow步骤（必须）
}
```

**说明**：
- 概念和步骤的关联信息已在EvidenceRecord层面建立（`step_records[].concept_mentions`）
- Gold标注不需要额外的 `step_id` 字段来标识关联
- Pipeline通过EvidenceRecord结构已知道每个概念属于哪个步骤

**不要使用**：
```json
// 错误：label是语义描述，无法匹配
{"label": "Record leak complaint", "expected_anchor": "Task"}

// 错误：label是混合格式
{"label": "T1: Record leak complaint", "expected_anchor": "Task"}
```

## 3. 文件范围

一个文件只标一个源文档，例如：

- `battery_BATOM_001.json`
- `cnc_CNCOM_002.json`
- `nev_EVMAN_003.json`

其中：

- `documents[0].doc_id` 必须与文件名里的文档编号一致
- `concept_ground_truth[*].evidence_id`
- `relation_ground_truth[*].evidence_id`
- `workflow_relation_ground_truth[*].evidence_id`

都必须与该文档 id 一致。

## 4. 概念标注规则

### 4.1 Workflow Step节点标注

**格式要求**：
- `label`: `"T1"` 或 `"T2"` 等（纯编号，用于匹配）
- `step_id`: `"T1"` 等（必须与label一致）
- `surface_form`: 从原文表格中完整复制的步骤文本
- `expected_anchor`: `"Task"`

**示例**：
```json
{
  "evidence_id": "BATOM_001",
  "label": "T1",
  "step_id": "T1",
  "surface_form": "At the left-rear coolant-plate outlet on Aurex BatteryHub-612 LR, record the complaint as seepage, dried residue, or undertray drip...",
  "should_be_in_graph": true,
  "expected_anchor": "Task",
  "reason": "O&M step T1 retained verbatim from the source document."
}
```

### 4.2 其他概念标注

允许的 `expected_anchor`：

- `Task` - 工作流步骤
- `Asset` - 设备/平台
- `Component` - 硬件部件、组件、接口
- `Signal` - 测量量、观察量、投诉信号
- `Fault` - 故障边界、失效模式

标注顺序：

1. 先把 markdown 表里的所有 `T1...Tn` 逐步抄进来，`surface_form` 必须保留原句。
2. 再补命名平台、硬件、接口、局部特征（`Component`）。
3. 再补明确的投诉、测量量、观察量（`Signal`）。
4. 最后补明确命名的故障边界或失效模式（`Fault`）。

不应入图的典型内容：

- 序列号
- 纯上下文字段，如"最近维修史""工况说明"
- 外部参考件、备件、对照样本
- 纯修辞性状态词，不能稳定指向对象的不要留

### 4.3 标签命名规范

- 标签优先用源文档原词
- 只有在必须消歧时，才做最小规范化
- 同一文档内同一对象只保留一个主标签
- 避免过长标签（建议 ≤ 50 字符）
- 避免包含文档ID前缀（如 `"BATOM_001:coolant"` → `"coolant"`）

## 5. Legacy Strict 关系标注规则

`relation_ground_truth` 里只允许两类关系：

### 5.1 步骤链

格式：`head=T_i, relation=triggers, tail=T_{i+1}, family=task_dependency`

```json
{
  "evidence_id": "BATOM_001",
  "head": "T1",
  "relation": "triggers",
  "tail": "T2",
  "family": "task_dependency",
  "valid": true,
  "reason": "The source procedure order places T1 before T2."
}
```

**注意**：`head` 和 `tail` 使用纯编号 `"T1"` `"T2"`，与概念标注一致。

### 5.2 结构链

格式：`head=装配或平台, relation=contains, tail=局部部件或特征, family=structural`

```json
{
  "evidence_id": "BATOM_001",
  "head": "Aurex BatteryHub-612 LR",
  "relation": "contains",
  "tail": "left-rear coolant-plate outlet",
  "family": "structural",
  "valid": true,
  "reason": "The outlet is explicitly located on Aurex BatteryHub-612 LR."
}
```

不要在这里标：

- `indicates`
- `causes`
- 生命周期相关关系

## 6. Workflow Grounding 标注规则

`workflow_relation_ground_truth` 用来标步骤到对象的直接落点边。

### 6.1 允许的relation类型

- `records` - 记录数据/投诉
- `observes` - 观察/查看对象
- `measures` - 测量参数
- `checks` - 检查状态/条件
- `inspects` - 检验/检查硬件
- `confirms` - 确认/验证结果
- `exposes` - 暴露/露出组件
- `compares` - 比较对照项
- `captures` - 捕获/记录信息

### 6.2 格式要求

```json
{
  "evidence_id": "BATOM_001",
  "head": "T1",
  "relation": "records",
  "tail": "seepage",
  "family": "action_object",  // 或 "task_dependency"
  "valid": true,
  "reason": "T1 explicitly records seepage as a complaint option."
}
```

**约束**：

- `head` 必须是 `T<n>` 格式（如 `"T1"` `"T3"`）
- `tail` 必须是已经在 `concept_ground_truth` 中保留的稳定概念
- 只标源文本里**直接出现**的步骤落点，不标多跳推理
- 每个step最多标注 3-5 个关键 action_object 边（不要过度标注）

### 6.3 标注判断标准

**应该标注**：
- 步骤文本中明确提到的动作对象
- 例如："T4 observes the connector shell" → 标 `T4 observes connector shell`

**不应标注**：
- 需要跨句推理才能成立的关系
- 间接提及或隐含的操作对象
- Signal → Fault 的推断关系
- 状态变化之间的因果链

## 7. 统计字段

`_statistics` 必须满足：

```json
"_statistics": {
  "total_concepts": 28,
  "positive_concepts": 28,
  "negative_concepts": 0,
  "total_relations": 15,
  "valid_relations": 15,
  "total_workflow_relations": 24,
  "valid_workflow_relations": 24
}
```

计算规则：
- `total_concepts == len(concept_ground_truth)`
- `positive_concepts == should_be_in_graph == true` 的数量
- `negative_concepts == should_be_in_graph == false` 的数量
- `total_relations == len(relation_ground_truth)`
- `valid_relations == valid == true` 的数量
- `total_workflow_relations == len(workflow_relation_ground_truth)`
- `valid_workflow_relations == valid == true` 的数量

## 8. 盲标注要求

- **禁止看**：预测图、错误分析、模型中间输出、评测报告、实验结果
- **禁止根据**"模型错在哪里"去倒推标签
- **只允许看**：原始 markdown 表格和本目录模板
- 标注完成后，统计字段必须准确反映实际标注数量

## 9. 高质量标注检查清单

在提交标注前，检查以下项目：

### 9.1 Workflow Step检查
- [ ] 所有 T1-Tn 步骤都已标注
- [ ] `label` 使用纯编号格式 `"T1"` `"T2"` 等
- [ ] `step_id` 与 `label` 一致
- [ ] `surface_form` 完整复制原文，无删减
- [ ] `expected_anchor` 都是 `"Task"`

### 9.2 概念检查
- [ ] Asset 使用 `expected_anchor = "Asset"`
- [ ] Component 使用 `expected_anchor = "Component"`
- [ ] Signal 使用 `expected_anchor = "Signal"`
- [ ] Fault 使用 `expected_anchor = "Fault"`
- [ ] 标签来自原文，不做过度推断

### 9.3 关系检查
- [ ] 步骤链完整：T1→T2→T3...Tn
- [ ] 结构链合理：Asset contains Component
- [ ] workflow grounding 边的 `head` 是 `T<n>` 格式
- [ ] workflow grounding 边的 `tail` 在 concept_ground_truth 中存在

### 9.4 统计检查
- [ ] `_statistics` 各字段数值准确
- [ ] 无遗漏、无重复

## 10. 示例模板

完整示例见 `battery_BATOM_001.json`。

关键字段示例：

```json
{
  "schema_version": "human_gold.v3",
  "domain_id": "battery",
  "annotation_status": "human_annotated",
  "annotator_id": "blind_human_annotator",
  "annotation_date": "2026-04-22",
  "annotation_basis": "Blind annotation from source O&M text only.",
  "documents": [{"doc_id": "BATOM_001", "doc_type": "om_manual"}],
  "concept_ground_truth": [...],
  "relation_ground_truth": [...],
  "workflow_relation_ground_truth": [...],
  "_statistics": {...}
}