# 第 5 轮

第 5 轮冻结了第 4 轮表现最优的配置，并从全新的 preprocessing 开始对完整 9 文档链路进行两次正式复跑，以实际测量稳定性，而不是直接假设系统已经稳定。冻结后的运行产物保存在 [artifacts/optimization_rounds/round_05](D:/crossextend_kg/artifacts/optimization_rounds/round_05) 中，其中包含对齐输入、专用配置、evidence records、run manifests、metrics diffs 以及每次运行的审计快照。

两次复跑在论文最关心的指标上保持得非常接近：relation F1 基本不变，为 `0.5222 -> 0.5218`，anchor accuracy 维持在 `0.9539 -> 0.9530`。concept F1 从 `0.7070` 变化到 `0.7253`，这与审计结果一致，即 candidate 数和 edge 数已经稳定，但 accepted node 数仍会因为 LLM attachment 的波动而产生轻微漂移。这说明当前最终架构已经足够可信、可复现、可作为无 fallback 主线用于论文展示，但还不能被描述为严格确定性的系统。
