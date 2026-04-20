# 第 3 轮

第 3 轮把范围扩展到 `BATOM_002`、`CNCOM_002` 和 `EVMAN_002`，目的是检查第 2 轮之后的逻辑是否能跨领域稳定成立。本轮最重要的发现不是代码 bug，而是数据对齐问题：[cnc_CNCOM_002.json](D:/crossextend_kg/data/ground_truth/cnc_CNCOM_002.json) 实际对应的内容是当前存放在 [CNCOM_003.md](D:/crossextend_kg/data/cnc/CNCOM_003.md) 中的文本，而不是 [CNCOM_002.md](D:/crossextend_kg/data/cnc/CNCOM_002.md)。因此，本轮引入了显式对齐记录 [data_alignment.json](D:/crossextend_kg/artifacts/optimization_rounds/round_03/data_alignment.json)，并在修正后的 staged inputs 上重新完成了三域评测。

复跑之后，三域宏平均 concept F1 从 `0.5765` 提升到 `0.8183`，relation F1 从 `0.5532` 提升到 `0.6073`。battery 领域依然保持强势，CNC 重新变得可评测，NEV 则仍然是最需要继续清理的领域，尤其是在精确 leak-boundary 命名上。这说明第 4 轮已经具备进入全量 human-gold 评测的条件，但前提是必须显式保留 CNC 的对齐策略，而不是再依赖当前原始文件名。
