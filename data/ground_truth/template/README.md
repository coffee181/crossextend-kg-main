# Ground Truth Annotation Templates

本目录是 `data/ground_truth/` 的标注模板与规范入口。

推荐阅读顺序：

1. `README.md`（本文件）
2. `document_gold.annotation_spec.md`（核心规范，必读）
3. 你当前要修改的那一类 `*.annotation_spec.md`
4. 对应的 `*.template.json`

## 当前分层原则

- `document_gold.*`
  主评测模板
- `dependency_chains.*`
  步骤链辅助标注
- `communication_indicators.*`
  观察信号到故障边界的辅助标注
- `propagation_chains.*`
  根因传播链辅助标注
- `multi_hop_questions.*`
  多跳问答辅助标注
- `lifecycle_events.*`
  生命周期辅助标注

## Document Gold 的新口径

`document_gold` 现在包含两层：

- `concept_ground_truth` + `relation_ground_truth`
  服务 legacy strict 指标
- `workflow_relation_ground_truth`
  服务 workflow grounding 指标

其中：

- `relation_ground_truth` 继续只保留
  - `triggers / task_dependency`（步骤链）
  - `contains / structural`（结构链）
- `workflow_relation_ground_truth` 用来记录
  - `T<n> records X`
  - `T<n> observes X`
  - `T<n> measures X`
  - `T<n> checks X`
  - `T<n> inspects X`
  - `T<n> confirms X`
  - `T<n> exposes X`
  - `T<n> compares X`

## Workflow Step Label格式（关键）

### Pipeline输出格式

Pipeline生成的 workflow_step 节点：

```
label = "BATOM_001:T1"  # {evidence_id}:{step_id}
display_label = "Record leak complaint (T1)"  # 语义摘要
step_id = "T1"
surface_form = "完整原文..."
```

### 评估匹配机制

评估时通过 `normalize_step_label` 函数规范化：
- `"BATOM_001:T1"` → `"T1"`（剥离前缀）

### Gold标注正确格式

```json
{
  "label": "T1",           // 纯编号，用于匹配
  "step_id": "T1",         // 元数据
  "surface_form": "完整原文...",  // 可读性来源
  "expected_anchor": "Task"
}
```

**不要用语义描述作为label**：
```json
// 错误！无法匹配
{"label": "Record leak complaint", "expected_anchor": "Task"}
```

可读性由 `surface_form` 和 Pipeline的 `display_label` 自动生成保证。

## 总原则

1. **只能根据原始源文档标注**，禁止参考模型输出、中间结果、评测报告、错误样例。
2. **标签优先保留源文档原词**，只做最小规范化。
3. **Workflow Step 的 label 使用纯编号** `"T1"` `"T2"` 等，`surface_form` 保留完整原文。
4. **文档级 gold 要稳定、保守、可复核**，不要把推理链和下游解释层内容混进 strict 主标注。
5. **workflow grounding 只标直接落点**，如果某条证据不足，就不要标。
6. **统计字段必须准确**，反映实际标注数量。

## 标注前必读

开始标注前，必须完整阅读 `document_gold.annotation_spec.md`，理解：

1. Pipeline输出格式与评估匹配机制
2. Workflow Step 的正确 label 格式
3. 概念标注顺序与 anchor 分配规则
4. 关系标注的允许类型
5. Workflow grounding 的判断标准
6. 统计字段计算规则

## 快速检查清单

标注完成后，检查：

- [ ] Workflow Step label 是 `"T1"` 格式（不是语义描述）
- [ ] 所有 T1-Tn 步骤都已标注
- [ ] 步骤链完整：T1→T2→...→Tn
- [ ] workflow grounding 的 tail 在 concept_ground_truth 中存在
- [ ] `_statistics` 数值准确