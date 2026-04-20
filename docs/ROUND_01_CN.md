# 第 1 轮

第 1 轮聚焦 `BATOM_002`，目标是在不引入 fallback 路径的前提下完成关系去噪。核心修改包括在 [preprocessing/processor.py](D:/crossextend_kg/preprocessing/processor.py) 中加入语义安全的别名规范化、上下文化结构头重写，以及在 [rules/filtering.py](D:/crossextend_kg/rules/filtering.py) 中加强高价值硬件节点的保留逻辑，并保留显式的 `Fault` 先验提示。

本轮通过一次真实的 `full_llm` 运行完成验证，审计指标从 concept F1 `0.8485` 提升到 `0.8696`，anchor accuracy 从 `0.9762` 提升到 `1.0000`，relation F1 从 `0.5818` 提升到 `0.6957`。预测图规模也从 `52` 个 concepts / `37` 个 relations 收缩到 `45` 个 concepts / `28` 个 relations，说明这轮优化真正减少了噪声，而不是仅仅换了一种标签写法。

进入第 2 轮时，主要遗留问题已经从结构膨胀转为语义边界问题：`stress whitening` 和 `latch-window distortion` 仍然没有正确命中 gold 中的故障目标，一些几何量和运行状态相关概念也仍然抽取不足。本轮的详细审计产物保存在 [artifacts/optimization_rounds/round_01](D:/crossextend_kg/artifacts/optimization_rounds/round_01)。
