# 开源更新说明

本文档用于说明当前这次覆盖 GitHub 主仓库的内容边界、主要更新点以及仓库裁剪原则。

## 这次提交的目标

本次更新不是继续叠加临时实验脚本，而是把仓库收敛到当前真正可维护、可复现、可开源展示的主线版本：

- 保留 workflow-first 双层图主链路
- 保留当前有效配置、提示词、评测与测试
- 删除历史性、一次性、强实验草稿性质的代码和脚本
- 明确区分开源源码与本地产物

## 当前保留的开源主线

### 1. 核心构图链路

- 预处理生成按步骤切分的 `EvidenceRecord`
- 固定 backbone 的语义路由与 attachment 决策
- workflow / semantic 双层图组装
- `final_graph.json` 与 GraphML 导出

### 2. 当前有效实验面

- `experiments/metrics/`
  保留工作流优先的评测主线，默认强调：
  - `workflow_step_f1`
  - `workflow_sequence_f1`
  - `workflow_grounding_precision / recall / f1`
  - `anchor_accuracy`
  - `anchor_macro_f1`
- `experiments/downstream/`
  保留新的下游任务协议：
  - `workflow_retrieval`
  - `repair_suffix_ranking`

### 3. 开源必备文档

- 根目录 `README.md`
- 根目录 `README_CN.md`
- `docs/PIPELINE_DATA_FLOW.md`
- `docs/WORKFLOW_KG_DESIGN.md`
- `docs/DOWNSTREAM_EVALUATION.md`
- `docs/GRAPH_QUALITY_DIAGNOSIS.md`

### 4. 回归测试

- `tests/test_workflow_dual_layer.py`
- `tests/test_cli_and_downstream.py`

## 这次删除或收缩的内容

为了让仓库更符合正式开源项目规范，本次移除了大量历史残留内容，包括但不限于：

- 旧的 ablation / baselines / comparison 目录
- 一次性 reporting 与 rounds 脚本
- 已失效的 `scripts/` 辅助脚本
- 旧配置分支与临时 YAML
- `egg-info` 打包产物
- 过时的项目总览与实验结果草稿文档

这些删除不是功能回退，而是为了减少冗余、避免误导，并让当前主线更加清晰。

## 本次不推送到 GitHub 的内容

以下内容属于本地运行产物、缓存或中间文件，不应作为源码仓库的一部分：

- `artifacts/`
- `graphml/` 下的运行结果
- `data/faiss-data/`
- 临时 `data/evidence_records/docset_*`
- 新生成的单文档 evidence record 中间文件

其中，已经保留在仓库中的少量 `data/evidence_records/full_human_gold_9doc/` 文件继续作为复现实验输入资产保留，不再继续扩张。

## 当前仓库的定位

截至本次更新，仓库定位已经明确为：

- 一个以 workflow-first O&M KG 为核心的开源代码仓库
- 一个保留最小必要评测与下游协议定义的研究工程仓库
- 一个强调 `no fallback`、强调主线清晰、避免临时实验污染的可维护项目

## 建议的后续协作方式

后续若继续演进，建议遵守以下原则：

- 新功能优先进入主线代码，而不是新增一次性脚本
- 新实验优先复用 `cli.py` 与 `experiments/` 现有入口
- 新文档优先更新现有主文档，而不是再建历史性流水账
- 运行产物和缓存继续留在本地，不进入 Git 仓库
