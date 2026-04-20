# 第 4 轮

第 4 轮把链路从三文档 mini-regression 推进到完整的 9 文档 human-gold 基准，同时保留了第 3 轮发现的显式 CNC 对齐策略。本轮主线修复是刻意收敛的：在 [pipeline/evidence.py](D:/crossextend_kg/pipeline/evidence.py) 中增加运行时标签归一化，在 [rules/filtering.py](D:/crossextend_kg/rules/filtering.py) 中加强验证性碎片拒绝和 observation/fault anchor 边界修正，并通过 [experiments/rounds.py](D:/crossextend_kg/experiments/rounds.py)、[scripts/prepare_round_run.py](D:/crossextend_kg/scripts/prepare_round_run.py)、[scripts/evaluate_variant_run.py](D:/crossextend_kg/scripts/evaluate_variant_run.py) 建立了可复现的轮次执行层。

修复后的复跑结果将宏平均 concept F1 从 `0.6559` 提升到 `0.6818`，anchor accuracy 从 `0.9347` 提升到 `0.9410`，relation F1 从 `0.4701` 提升到 `0.5049`，同时预测规模从 `425/195` 个 concepts/relations 收缩到 `415/179`。消融实验也让论文叙事更加清晰：rule filtering 是确实有贡献的，但在当前 9 文档规模下，memory bank 和 LLM attachment 的收益都还比较边际。当前最大的剩余风险仍然是数据质量而不是链路逻辑，尤其是 [battery_BATOM_001.json](D:/crossextend_kg/data/ground_truth/battery_BATOM_001.json)，其 gold step 与 staged 文档并未完全对齐。
