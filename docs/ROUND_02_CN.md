# 第 2 轮

第 2 轮继续以 `BATOM_002` 为对象，但目标从结构去噪转向语义边界精修。最核心的修改是强化了 [preprocessing_extraction_om.txt](D:/crossextend_kg/config/prompts/preprocessing_extraction_om.txt) 中的抽取提示词，并在 [filtering.py](D:/crossextend_kg/rules/filtering.py) 中引入更有选择性的过滤策略，用来拒绝泛化的替换件节点、保留可复用的几何测量概念，并停止对低价值观察碎片的过度“抢救”。

经过这一轮后，单文档图谱与人工 gold 的贴合度明显提升：concept F1 从 `0.8696` 提升到 `0.9556`，relation F1 从 `0.6957` 提升到 `0.8649`，anchor accuracy 维持在 `1.0000`，额外概念数降为 `0`。剩余误差已经收缩到少量可解释的项，这也使得第 3 轮可以开始验证这些规则是否能在 `CNCOM_002` 和 `EVMAN_002` 上保持有效。
