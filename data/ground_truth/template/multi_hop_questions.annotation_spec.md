# Multi-hop Questions 标注规范

## 1. 目标

根据已经确认的标签和链路，构造 2-4 hop 的可复核问题。

## 2. 规则

- `gold_chain` 必须是问题的标准路径。
- `hops == len(gold_chain) - 1`
- `expected_answer` 默认写 `gold_chain` 最后一项。
- 问题必须能由 document gold + support 标注中的标签支撑。

## 3. 问题类型建议

- 平台 -> 组件 -> 局部特征
- 根因 -> 中间故障 -> 外显症状
- 组件 -> 故障边界 -> 可见信号

## 4. 不要做的事

- 不要写开放式问答
- 不要写需要外部知识的题
- 不要写多个答案都对的问题
