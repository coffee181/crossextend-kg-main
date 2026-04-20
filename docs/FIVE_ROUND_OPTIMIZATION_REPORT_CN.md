# 五轮自动优化报告

## 1. 背景与目标

- 本报告记录了 CrossExtend-KG 运维表单图谱主链路在严格 `no fallback` 原则下进行的五轮连续优化。
- 每一轮都遵循同一执行框架：真实运行当前范围内的完整链路、审计端到端数据流、修复主线逻辑问题、立即复跑验证、同步实验与文档产物。
- 固定范围分别为：
- 第 1-2 轮：`BATOM_002`
- 第 3 轮：`BATOM_002`、`CNCOM_002`、`EVMAN_002`
- 第 4 轮：全部 9 份 human-gold
- 第 5 轮：冻结最佳配置后的多文档正式复跑与稳定性审计

## 2. 初始状态与主要问题

- 关系噪声偏高，尤其是被过度提升的 structural 边和 step-local 边。
- `Signal / Fault / State` 的语义边界不稳定，导致 attachment 容易受表面措辞影响。
- 跨域评测一开始并不完全可信，因为 CNC markdown 文件名与 gold id 存在内容错位。
- 实验与评测层缺少统一的 round-preparation、manifest、metrics diff 和报告编译结构，可复现性和可展示性不足。
- human-gold 评测同时暴露出标注风险，最典型的是 `BATOM_001`：staged markdown 有 8 个 step，但当前 gold 只覆盖了其中 6 个。

## 3. 五轮优化总览

| 轮次 | 修改主题 | 影响模块 | 结果 |
|---|---|---|---|
| 第 1 轮 | `BATOM_002` 关系去噪与结构收缩 | `preprocessing/processor.py`、`rules/filtering.py`、预处理契约测试 | concept F1 `0.8485 -> 0.8696`；anchor acc `0.9762 -> 1.0000`；relation F1 `0.5818 -> 0.6957` |
| 第 2 轮 | `Signal / Fault / State` 语义边界精修 | `config/prompts/preprocessing_extraction_om.txt`、`rules/filtering.py`、语义回归测试 | concept F1 `0.8696 -> 0.9556`；anchor acc `1.0000 -> 1.0000`；relation F1 `0.6957 -> 0.8649` |
| 第 3 轮 | 三域 mini-regression 与数据对齐修复 | staged 输入对齐、共享 canonicalization、跨域评测流 | concept F1 `0.5765 -> 0.8183`；anchor acc `0.9815 -> 0.9800`；relation F1 `0.5532 -> 0.6073` |
| 第 4 轮 | 全 9 文档 human-gold 正式评测与消融 | `pipeline/evidence.py`、`rules/filtering.py`、`experiments/*`、round scripts | concept F1 `0.6559 -> 0.6818`；anchor acc `0.9347 -> 0.9410`；relation F1 `0.4701 -> 0.5049` |
| 第 5 轮 | 冻结全量配置并做稳定性复跑 | 冻结配置、round manifest、报告编译、最终产物结构 | concept F1 `0.7070 -> 0.7253`；anchor acc `0.9539 -> 0.9530`；relation F1 `0.5222 -> 0.5218` |

## 4. 第 1 轮详细记录

### 范围与目标

- 对象：`BATOM_002`
- 目标：在不引入 fallback 的前提下压缩关系噪声、收紧 structural 过扩张，并保住已有 concept 和 anchor 优势。

### 关键修改

- 在 [preprocessing/processor.py](D:/crossextend_kg/preprocessing/processor.py) 中加入语义安全的 alias canonicalization，避免 component label 被错误塌缩成 observation label。
- 在 [preprocessing/processor.py](D:/crossextend_kg/preprocessing/processor.py) 中对可恢复的 contextual structural head 进行重写，再清理剩余低价值结构头。
- 在 [rules/filtering.py](D:/crossextend_kg/rules/filtering.py) 中增加高价值硬件节点保留逻辑，并保留显式 `Fault` 提示。

### 数据流变化

- 保持单文档 extraction 范围不变，只在 EvidenceRecord、candidate 和 filtering 层收紧主线。
- 预测图从 `52` 个 concepts / `37` 个 relations 收缩到 `45` 个 concepts / `28` 个 relations。
- `task_dependency` 仍大量存在于 explainability 层，但不再无差别进入 final graph。

### 结果与结论

- concept F1：`0.8485 -> 0.8696`
- anchor accuracy：`0.9762 -> 1.0000`
- relation F1：`0.5818 -> 0.6957`
- 结论：第 1 轮证明关系去噪和结构收缩是有效的，但遗留问题已经从结构噪声转向语义边界。

### 遗留问题

- `stress whitening` 与 `latch-window distortion` 仍没有正确落到 gold 中的故障目标。
- `bend radius`、`clearance`、`operating state` 等几何或运行态概念仍抽取不足。

## 5. 第 2 轮详细记录

### 范围与目标

- 对象：`BATOM_002`
- 目标：修正 `Signal / Fault / State` 语义边界，收敛概念粒度，清理残余低价值概念。

### 关键修改

- 强化 [preprocessing_extraction_om.txt](D:/crossextend_kg/config/prompts/preprocessing_extraction_om.txt) 中的抽取提示词，优先抽取直接 fault target。
- 在 [filtering.py](D:/crossextend_kg/rules/filtering.py) 中拒绝泛化 replacement-part 节点，保留可复用几何测量概念，并停止过度抢救弱 observation 碎片。

### 数据流变化

- preprocessing 的语义约束与 filtering 的 admission 规则首次达到较好一致。
- graph 从第 1 轮的 `45/28` 收缩到 `43/19`，同时 concept 和 relation 质量继续提升。

### 结果与结论

- concept F1：`0.8696 -> 0.9556`
- anchor accuracy：`1.0000 -> 1.0000`
- relation F1：`0.6957 -> 0.8649`
- 结论：第 2 轮基本解决了 battery 单文档上的主要语义边界问题，为跨域验证打下了基础。

### 遗留问题

- 仍缺少 `access panels`、`inlet tube bead`、`burrs`、`corrosion`
- 仍缺少 `bracket side load -> cracked shell` 和 `fresh wetting -> recurring seepage`

## 6. 第 3 轮详细记录

### 范围与目标

- 对象：`BATOM_002`、`CNCOM_002`、`EVMAN_002`
- 目标：防止对 battery 过拟合，验证跨域主线逻辑是否成立。

### 关键修改

- 通过 [data_alignment.json](D:/crossextend_kg/artifacts/optimization_rounds/round_03/data_alignment.json) 显式记录 CNC 的内容对齐关系。
- 复用第 2 轮冻结的 battery 逻辑，加入跨域 contextual-prefix canonicalization。

### 数据流变化

- 评测输入不再依赖原始文件名，而是依赖显式 staged 内容与 gold 的语义对齐关系。
- 这一步修复的是“评测有效性”，不是单纯调参数提分。

### 结果与结论

- concept F1：`0.5765 -> 0.8183`
- anchor accuracy：`0.9815 -> 0.9800`
- relation F1：`0.5532 -> 0.6073`
- 结论：CNC 重新变得可评测，battery 保持强势，NEV 仍是后续全量 human-gold 评测前最需要继续处理的领域。

### 遗留问题

- NEV 仍过度预测泛化 leak-boundary 概念。
- CNC 仍缺少若干 leak-evidence 与 side-load 关系。

## 7. 第 4 轮详细记录

### 范围与目标

- 对象：全部 9 份 `data/ground_truth/*.json`
- 目标：得到第一版完整 human-gold 主结果，并完成系统级消融实验。

### 关键修改

- 在 [pipeline/evidence.py](D:/crossextend_kg/pipeline/evidence.py) 中加入高影响标签的运行时归一化。
- 在 [rules/filtering.py](D:/crossextend_kg/rules/filtering.py) 中加强 verification-outcome 与 placeholder 片段拒绝，并调整 observation / fault anchor 边界。
- 新增 round 级执行与评测支撑：[experiments/rounds.py](D:/crossextend_kg/experiments/rounds.py)、[scripts/prepare_round_run.py](D:/crossextend_kg/scripts/prepare_round_run.py)、[scripts/evaluate_variant_run.py](D:/crossextend_kg/scripts/evaluate_variant_run.py)。

### 数据流变化

- 在保持显式 CNC 对齐的前提下，完整拉通了 9 文档 preprocessing、EvidenceRecord、SchemaCandidate、attachment/filtering、final graph 和 metrics。
- 预测规模从 `425/195` 降到 `415/179`，说明优化主要来自减少噪声和错配。
- `nev_EVMAN_003.json` 是提升最明显的单文件，concept F1 `0.7200 -> 0.8817`，relation F1 `0.3158 -> 0.5532`。

### 结果与结论

- concept F1：`0.6559 -> 0.6818`
- anchor accuracy：`0.9347 -> 0.9410`
- relation F1：`0.4701 -> 0.5049`
- 结论：第 4 轮建立了第一版真正可用于论文的 human-gold 主结果，同时完成了第一版可信消融。

### 遗留问题

- `BATOM_001` 的 gold 与 staged markdown 仍不一致。
- `front manifold face`、quick-coupler boundary 等高精度 structural locus 仍弱于 gold。
- LLM attachment 相对 deterministic / embedding 路由的收益在当前 9 文档规模上仍然偏弱，不能过度宣称。

## 8. 第 5 轮详细记录

### 范围与目标

- 对象：冻结后的全量 9 文档配置
- 目标：完成多文档正式复跑，验证稳定性，并冻结最终架构与 artifact 结构。

### 关键修改

- 使用 round 级专用配置重新 staging 全量数据，从 fresh preprocessing 开始复跑。
- 通过 `baseline_metrics.json`、`post_metrics.json`、`metrics_diff.json` 与两次 audit snapshot 明确定位系统波动来源。
- 完成最终报告编译链路，将 round manifest、metrics、audits 和文档统一汇入最终总报告。

### 数据流变化

- candidate 数在两次复跑中完全一致：
- battery：`166 -> 166`
- cnc：`143 -> 143`
- nev：`142 -> 142`
- edge 数也保持稳定：
- battery：`43 -> 43`
- cnc：`56 -> 56`
- nev：`47 -> 47`
- 仅 accepted node 数存在轻微漂移，说明剩余随机性主要来自 attachment，而不是上游 extraction 或下游 graph promotion。

### 结果与结论

- concept F1：`0.7070 -> 0.7253`
- anchor accuracy：`0.9539 -> 0.9530`
- relation F1：`0.5222 -> 0.5218`
- 结论：关系结构已经非常稳定，概念集仍有少量随机波动，因此系统已经足够作为可信主线，但还不应被描述为严格确定性系统。

### 遗留问题

- `BATOM_001` 标注错位仍然存在。
- LLM attachment 仍带来轻微 concept count 漂移。
- 一些结构位点标签的 specificity 仍低于 gold。

## 9. 五轮指标变化总表

| 轮次 | concept F1 基线 | concept F1 复跑后 | anchor acc 基线 | anchor acc 复跑后 | relation F1 基线 | relation F1 复跑后 |
|---|---:|---:|---:|---:|---:|---:|
| 第 1 轮 | 0.8485 | 0.8696 | 0.9762 | 1.0000 | 0.5818 | 0.6957 |
| 第 2 轮 | 0.8696 | 0.9556 | 1.0000 | 1.0000 | 0.6957 | 0.8649 |
| 第 3 轮 | 0.5765 | 0.8183 | 0.9815 | 0.9800 | 0.5532 | 0.6073 |
| 第 4 轮 | 0.6559 | 0.6818 | 0.9347 | 0.9410 | 0.4701 | 0.5049 |
| 第 5 轮 | 0.7070 | 0.7253 | 0.9539 | 0.9530 | 0.5222 | 0.5218 |

## 10. 五轮数据流变化总表

| 轮次 | 输入范围 | 数据流关键变化 |
|---|---|---|
| 第 1 轮 | `BATOM_002` | 保持单文档 extraction 不变，在 EvidenceRecord、candidate 和 filtering 层收紧主线，final graph 从 `52/37` 收缩到 `45/28`。 |
| 第 2 轮 | `BATOM_002` | 将 preprocessing prompt 与 filtering admission 规则对齐，移除泛化 replacement 节点与低价值 observation 碎片。 |
| 第 3 轮 | `BATOM_002`、`CNCOM_002`、`EVMAN_002` | 引入显式 CNC 内容对齐，使评测输入从“按文件名假设正确”切换为“按 staged 内容与 gold 语义对齐”。 |
| 第 4 轮 | 全部 9 份 human-gold | 全链路扩展到 9 文档，并通过 runtime label normalization 与 verification-fragment rejection 降低 full-corpus 错配。 |
| 第 5 轮 | 冻结后的 9 文档正式复跑 | 两次复跑 candidate 数和 edge 数稳定，仅 accepted node 数轻微波动，说明剩余随机性主要位于 attachment 层。 |

## 11. 五轮代码逻辑与架构变化总表

| 轮次 | 逻辑 / 架构变化 | 关键代码路径 | 效果 |
|---|---|---|---|
| 第 1 轮 | 将 alias canonicalization 从纯字符串匹配改为兼顾语义类型，收紧 structural head promotion | `preprocessing/processor.py`、`rules/filtering.py` | 关系噪声下降，graph 更紧凑 |
| 第 2 轮 | 让 preprocessing 的语义优先级与 filtering 的 anchor / admission 规则一致化 | `config/prompts/preprocessing_extraction_om.txt`、`rules/filtering.py` | 单文档语义边界显著改善 |
| 第 3 轮 | 把跨域正确性从隐式文件名依赖改成显式对齐产物 | `artifacts/optimization_rounds/round_03/data_alignment.json` 等 | CNC 评测恢复可信 |
| 第 4 轮 | 引入 round-execution / evaluation 框架，统一保存 configs、manifests、metrics diff、ablation 和 audits | `experiments/*`、`scripts/*`、`pipeline/evidence.py`、`rules/filtering.py` | full-gold 与 ablation 可复现、可审计 |
| 第 5 轮 | 冻结最终配置与报告编译路径，验证稳定性并收束 artifact 结构 | `experiments/reporting.py`、round 05 configs / manifests | 形成最终可展示的实验与报告体系 |

## 12. 消融实验结论

### 消融结果表

| 变体 | concept F1 | anchor acc | anchor macro-F1 | relation F1 |
|---|---:|---:|---:|---:|
| `full_llm` | 0.6881 | 0.9412 | 0.8412 | 0.5049 |
| `no_memory_bank` | 0.6795 | 0.9431 | 0.8416 | 0.5057 |
| `no_rule_filter` | 0.6683 | 0.9102 | 0.8071 | 0.4673 |
| `no_embedding_routing` | 0.6919 | 0.9417 | 0.8415 | 0.5043 |
| `embedding_top1` | 0.6904 | 0.9404 | 0.8405 | 0.5043 |
| `deterministic` | 0.6904 | 0.9404 | 0.8405 | 0.5043 |

### 结论解释

- `no_rule_filter` 是唯一一个在 concept、anchor、relation 三类指标上都明显变差的消融项，因此 rule filtering 是当前系统中最明确的收益来源。
- `no_memory_bank` 与 `full_llm` 的差距很小，说明在当前 9 文档规模上，memory bank 的贡献存在但仍偏弱，不能被包装成压倒性收益。
- `no_embedding_routing`、`embedding_top1` 与 `deterministic` 的结果与 `full_llm` 非常接近，说明当前数据规模下 LLM attachment 的优势是边际性的，而不是决定性的。
- 因此，现阶段论文可以主张“整条主线有效”，但不适合强宣称“LLM attachment 是主要收益来源”。

## 13. 最终冻结架构

- 最终冻结的主线为：
- staged markdown
- preprocessing extraction
- step-scoped EvidenceRecord
- SchemaCandidate 聚合
- attachment / routing
- rule filtering
- final graph
- human-gold metrics 与 ablation

- 关键冻结原则：
- 不允许 fallback
- 论文主指标只使用人工 gold
- silver 或自动生成标注只作为诊断信息，不进入论文主结果
- `artifacts/optimization_rounds/round_xx/` 是 round 级产物根目录，负责保存输入对齐、配置、运行输出、指标与报告，而不是依赖临时 `working/` 目录

## 14. 当前剩余风险

| 轮次 | 遗留问题关闭情况 | 当前状态 |
|---|---|---|
| 第 1 轮 | 结构噪声和 alias 误塌缩已关闭，语义边界问题转入第 2 轮 | 已关闭主要结构问题 |
| 第 2 轮 | battery 单文档语义边界问题大体关闭，跨域泛化问题转入第 3 轮 | 已关闭单文档主问题 |
| 第 3 轮 | CNC 对齐问题已关闭，跨域剩余误差转入第 4 轮全量评测 | 已关闭数据对齐主问题 |
| 第 4 轮 | full-gold 与消融已完成，但 `BATOM_001` 标注错位、structural specificity 不足仍未关闭 | 部分未关闭 |
| 第 5 轮 | 最终冻结与稳定性审计已完成，但 attachment 轻微随机性与部分结构位点命名问题仍保留 | 部分未关闭 |

- 当前最重要的剩余风险仍然是 `BATOM_001` 标注与 staged 文档不一致。这个问题应该修 gold，而不是改 evaluator 去掩盖。
- 结构位点 specificity 仍弱于部分 gold，典型例子包括 `front manifold face`、quick-coupler boundary 等。
- repeated `full_llm` runs 仍会引入轻微 concept-count 漂移，因此最终论文必须诚实描述系统稳定性边界。

## 15. 后续建议

- 优先修复 `BATOM_001` 的人工 gold，使 staged 文档中的每个 step 都在标注中得到对应表示。
- 如果论文需要更强地支撑 memory bank 或 LLM attachment 的收益，应扩大 human-gold 规模，或增加 repeated-run 采样，而不是只依赖当前 9 文档。
- 继续强化 structural locus labeling，使 manifold、quick connector、outlet boundary、clamp stack 等概念的精度更贴近 gold。
- 后续任何新的实验、表格或论文结论，都应继续走 round-manifest、metrics-diff、ablation-report 这一条统一路径，避免重新回到零散脚本和临时输出的模式。
