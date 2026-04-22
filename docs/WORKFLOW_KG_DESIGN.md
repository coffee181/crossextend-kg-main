# Workflow Knowledge Graph Design

**Updated**: 2026-04-22
**Status**: Design Document
**Scope**: Workflow layer architecture and downstream task design for O&M domain

## 1. Overview

CrossExtend-KG在传统语义KG基础上引入了**Workflow层**，专门用于建模O&M（运维与维修）领域的操作步骤序列和步骤-对象接地关系。

### 1.1 三层架构

| 层次 | 内容 | 目的 |
|------|------|------|
| **语义层 (Semantic Layer)** | Asset → Component → Signal → Fault | 传统KG语义关系，描述设备结构和信号-故障关联 |
| **Workflow层 (Workflow Layer)** | T1 → T2 → T3 ... → Tn | 操作步骤执行序列，描述维修流程顺序 |
| **接地层 (Grounding Layer)** | T1 records Signal, T3 inspects Component | 步骤-对象操作关系，描述每个步骤具体操作什么对象 |

### 1.2 Workflow的核心价值

- **时序建模**: 描述操作步骤之间的依赖关系
- **操作追溯**: 每个步骤关联到具体的操作对象
- **下游任务支持**: 支持多跳问答、维修路径生成、故障定位推荐等实用任务

---

## 2. Data Structure

### 2.1 Workflow Step节点

来源: `concept_ground_truth` 中 `expected_anchor="Task"` 的概念

```json
{
  "label": "T1",              // 用于评估匹配（纯编号）
  "step_id": "T1",            // 元数据属性
  "surface_form": "完整原文...",  // 用于可读性，保留原文
  "expected_anchor": "Task",  // 标识这是workflow步骤
  "should_be_in_graph": true
}
```

**设计原则**:
- `label` 使用纯编号 `"T1"` `"T2"` 等，便于评估匹配
- `surface_form` 保留完整原文，保证图谱可读性
- Pipeline生成时自动提取 `display_label` 作为语义摘要

### 2.2 Workflow Sequence边

来源: `relation_ground_truth` 中 `family="task_dependency"` 的关系

```json
{
  "head": "T1",
  "relation": "triggers",
  "tail": "T2",
  "family": "task_dependency",
  "valid": true,
  "reason": "The source procedure order places T1 before T2."
}
```

**形成步骤链**:
```
T1 triggers T2 triggers T3 triggers T4 triggers T5 triggers T6 triggers T7 triggers T8
```

### 2.3 Workflow Grounding边

来源: `workflow_relation_ground_truth`

```json
{
  "head": "T1",
  "relation": "records",
  "tail": "seepage",
  "family": "action_object",
  "valid": true,
  "reason": "T1 explicitly records seepage as a complaint option."
}
```

**允许的relation类型**:
- `records` - 记录数据/投诉
- `observes` - 观察/查看对象
- `measures` - 测量参数
- `checks` - 检查状态/条件
- `inspects` - 检验/检查硬件
- `confirms` - 确认/验证结果
- `exposes` - 暴露/露出组件
- `compares` - 比较对照项
- `captures` - 捕获/记录信息

---

## 3. Graph Visualization

### 3.1 示例：battery_BATOM_001

```
                    Aurex BatteryHub-612 LR (Asset)
                              │
                              │ contains
                              ↓
                 left-rear coolant-plate outlet (Component)
                              │
            ┌─────────────────┼─────────────────┬─────────────────┐
            │ contains        │ contains        │ contains       │ contains
            ↓                 ↓                 ↓               ↓
   aluminum outlet    PA12 quick-    green EPDM     stainless retainer
        neck          connector shell    O-ring         clip

         ┌───────────────┼───────────────┐
         │               │               │
         ↓               ↓               ↓
    [T1]──→[T2]──→[T3]──→[T4]──→[T5]──→[T6]──→[T7]──→[T8]
     │     │     │     │     │     │     │     │
     │     │     │     │     │     │     │     │
     ↓     ↓     ↓     ↓     ↓     ↓     ↓     ↓
  seepage  exposes  inspects  observes  compares  confirms  measures
  (Signal) (action)  (action)  (action)  (action)  (action)  (action)
     │
     └─── T1 操作的对象（投诉信号）
```

### 3.2 Workflow Grounding示例

```
T1 ──records──→ seepage
T1 ──records──→ dried residue
T1 ──records──→ undertray drip
T1 ──captures──→ coolant concentration

T2 ──exposes──→ aluminum outlet neck
T2 ──exposes──→ PA12 quick-connector shell
T2 ──exposes──→ green EPDM O-ring
T2 ──exposes──→ stainless retainer clip
T2 ──exposes──→ hose saddle bracket

T3 ──inspects──→ latch window
T3 ──inspects──→ tube bead
T3 ──inspects──→ cold-plate seam

T4 ──observes──→ PA12 quick-connector shell
T4 ──observes──→ green EPDM O-ring
T4 ──observes──→ cold-plate seam
T4 ──records──→ applied pressure
T4 ──records──→ time to first wetting

T5 ──compares──→ insertion depth
T5 ──checks──→ stainless retainer clip
T5 ──checks──→ hose saddle bracket

T6 ──confirms──→ stainless retainer clip
T6 ──confirms──→ hose saddle bracket

T7 ──measures──→ inlet and outlet temperatures
T7 ──observes──→ PA12 quick-connector shell
```

---

## 4. Evaluation Metrics

### 4.1 Workflow指标

| 指标 | Gold来源 | Predicted来源 | 匹配单位 |
|------|----------|---------------|----------|
| `workflow_step_f1` | `concept_ground_truth` (anchor=Task) | nodes (workflow_step类型) | 标签字符串 `"T1"` |
| `workflow_sequence_f1` | `relation_ground_truth` (family=task_dependency) | edges (workflow_kind=sequence) | 四元组 `(head, rel, tail, family)` |
| `workflow_grounding_f1` | `workflow_relation_ground_truth` | edges (workflow_kind=action_object) | 四元组 `(head, rel, tail, family)` |

### 4.2 计算公式

```python
TP = |predicted_set ∩ gold_set|
FP = |predicted_set - gold_set|
FN = |gold_set - predicted_set|

precision = TP / (TP + FP)
recall    = TP / (TP + FN)
F1        = 2 * precision * recall / (precision + recall)
```

### 4.3 匹配机制

Pipeline生成的节点label格式: `"BATOM_001:T1"`（带文档前缀）

评估时规范化: `"BATOM_001:T1"` → `"T1"`（剥离前缀后匹配）

Gold标注使用纯编号 `"T1"`，两者可以正确匹配。

---

## 5. Downstream Task Design

Workflow图谱包含完整信息，可支持多种下游任务证明有效性：

### 5.1 多跳问答 (Multi-hop QA)

**任务**: 给定投诉信号，回答需要检查哪些组件

**示例**:
```
问题: "检测到seepage投诉后，需要检查哪些组件？"
答案路径: T1(records seepage) → T2 → T3(inspects latch window, tube bead, cold-plate seam)
答案: latch window, tube bead, cold-plate seam
```

### 5.2 故障定位推荐 (Fault Localization Recommendation)

**任务**: 给定投诉描述，推荐执行步骤链和关键检查点

**示例**:
```
输入: "冷却液渗漏投诉"
输出:
  - 推荐步骤链: T1→T2→T3→T4→T5→T6→T7→T8
  - 关键检查点: latch window, tube bead, cold-plate seam, O-ring
  - 测量参数: applied pressure, time to first wetting, inlet/outlet temperatures
```

### 5.3 维修步骤生成 (Maintenance Procedure Generation)

**任务**: 给定问题描述，生成结构化维修步骤

**示例**:
```
问题: "如何定位左侧冷却板出口的泄漏边界？"
答案:
  Step 1 (T1): 记录投诉类型(seepage/dried residue/undertray drip)，记录冷却液浓度
  Step 2 (T2): 暴露aluminum outlet neck, PA12 quick-connector shell, green EPDM O-ring
  Step 3 (T3): 检查latch window, tube bead, cold-plate seam的泄漏路径
  Step 4 (T4): 压力测试，观察connector shell, O-ring, plate seam，记录applied pressure
  Step 5 (T5): 比较insertion depth, retainer-clip seating, bracket position
  Step 6 (T6): 修复接口，确认retainer clip锁定，bracket无侧向推力
  Step 7 (T7): 循环冷却液，测量inlet/outlet temperatures
  Step 8 (T8): 确认泄漏边界，记录修复结果
```

### 5.4 步骤-对象关联预测 (Step-Object Link Prediction)

**任务**: 给定新步骤描述，预测其操作对象

**示例**:
```
输入: "检查连接器外壳是否有裂纹"
预测:
  - 对象: connector shell (Component)
  - relation: inspects
```

### 5.5 步骤补全 (Step Completion)

**任务**: 给定部分步骤序列，预测缺失步骤

**示例**:
```
输入: T1 → T2 → T3 → ?
预测: T4 (基于sequence pattern和接地对象关联)
```

---

## 6. Paper Experiment Design

### 6.1 主实验

| 实验 | 指标 | 证明内容 |
|------|------|----------|
| Workflow Step Detection | F1 | 系统能正确识别操作步骤 |
| Workflow Sequence Prediction | F1 | 系统能推断正确的步骤顺序 |
| Workflow Grounding | F1 | 系统能关联步骤到正确的操作对象 |

### 6.2 下游任务实验

| 实验 | 指标 | 证明内容 |
|------|------|----------|
| 多跳问答 | Accuracy/F1 | KG支持下游推理任务 |
| 维修路径生成 | BLEU/Rouge/Step Accuracy | KG支持结构化文本生成 |
| 步骤-对象关联预测 | Precision/Recall | KG支持新样本预测 |

### 6.3 消融实验

| 变体 | 验证内容 |
|------|----------|
| `no_workflow_layer` | 移除Workflow层，仅保留语义层，证明Workflow层的必要性 |
| `no_grounding` | 移除接地边，证明步骤-对象关联的价值 |
| `no_sequence` | 移除步骤链，证明时序建模的价值 |

---

## 7. Comparison with Traditional KG

| 方面 | 传统语义KG | Workflow KG |
|------|-----------|-------------|
| 节点类型 | Concept, Entity | Concept + WorkflowStep |
| 关系类型 | Semantic relations | Semantic + TaskDependency + ActionObject |
| 推理方式 | 语义推理链 | 操作执行序列 |
| 应用场景 | 知识检索、问答 | 维修决策、步骤生成 |
| 可追溯性 | 有限 | 完整（步骤→对象→结果） |

---

## 8. Implementation Notes

### 8.1 Pipeline输出格式

```python
# graph.py 中生成 workflow_step 节点
label = f"{evidence_id}:{step_id}"  # "BATOM_001:T1"
display_label = f"{semantic_summary} ({step_id})"  # "Record leak complaint (T1)"
step_id = "T1"
node_type = "workflow_step"
node_layer = "workflow"
surface_form = "完整原文..."
```

### 8.2 评估匹配机制

```python
# core.py 中规范化label
def normalize_step_label(label, doc_ids):
    # "BATOM_001:T1" → "T1"
    for doc_id in doc_ids:
        prefix = f"{doc_id}:"
        if label.startswith(prefix):
            tail = label[len(prefix):]
            if tail.startswith("T"):
                return tail
    return label.strip()
```

### 8.3 Gold标注格式

```json
{
  "label": "T1",           // 纯编号，用于匹配
  "step_id": "T1",         // 元数据
  "surface_form": "...",   // 可读性来源
  "expected_anchor": "Task"
}
```

---

## 9. Files Reference

| 文件 | 内容 |
|------|------|
| `data/ground_truth/*.json` | 单文档标注文件，包含workflow三层结构 |
| `data/ground_truth/template/document_gold.annotation_spec.md` | 标注规范 |
| `experiments/metrics/core.py` | Workflow指标计算实现 |
| `pipeline/graph.py` | Workflow节点生成逻辑 |
| `scripts/validate_ground_truth.py` | 标注验证脚本 |

---

## 10. Summary

Workflow KG的核心贡献：

1. **领域适配**: O&M领域需要建模操作步骤序列，传统语义KG无法直接表达
2. **三层架构**: 语义层 + Workflow层 + 接地层，完整描述设备、步骤、操作对象
3. **下游任务**: 支持多跳问答、维修路径生成、故障定位等实用任务
4. **可评估**: workflow_step_f1, workflow_sequence_f1, workflow_grounding_f1 三个指标量化质量

这个设计可以支持论文发表，证明Workflow层增强了KG对O&M领域的建模能力。