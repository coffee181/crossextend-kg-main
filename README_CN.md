# CrossExtend-KG 中文说明

[English](README.md)

CrossExtend-KG 是一个面向工业 O&M 表单的知识图谱构建项目。当前面向论文主线的版本坚持 `no fallback`，主流程由按步骤抽取、固定 backbone 路由、显式 attachment 决策和规则化图谱精修组成。

## 当前范围

- 输入类型：`om_manual`
- 活跃领域：`battery`、`cnc`、`nev`
- 论文主变体：`full_llm`
- 论文主指标：只使用人工 gold
- 最高执行原则：`no fallback`

## 本次更新的主要变化

- 将 `config/persistent/` 从重复的大 JSON 预设重构为分层 YAML 配置。
- 为 pipeline 和 preprocessing 增加共享 base config。
- 将 LLM 与 embedding 的模型选择拆到 backend registry 中。
- 统一 loader，支持 `extends`、`llm_backend_id`、`embedding_backend_id`。
- 保留 JSON 兼容，用于生成式实验配置、ablation 物化和回归测试。
- 让预处理默认适配当前真实原始目录，如 `battery_om_manual_en`、`ev_om_manual_en`。
- 顺手增强了包模式导入稳定性，减少对根目录绝对导入的隐式依赖。

## 当前主链路

```text
O&M markdown
  -> preprocessing extraction
  -> step-aware EvidenceRecord
  -> SchemaCandidate aggregation
  -> fixed backbone retrieval / routing
  -> attachment decisions
  -> rule filtering
  -> graph assembly
  -> export + human-gold evaluation
```

## 配置结构

现在人工维护的配置统一放在 `config/persistent/` 的 YAML 文件中：

- `pipeline.base.yaml`
  固定 backbone、relations、domains 和 runtime 默认值
- `pipeline.deepseek.yaml`
  推荐主运行配置
- `pipeline.deepseek.battery_only.yaml`
  电池领域单域调试配置
- `pipeline.deepseek_full.yaml`
  多变体压力测试配置
- `preprocessing.base.yaml`
  共享预处理基础配置
- `preprocessing.deepseek.yaml`
  推荐预处理配置
- `llm_backends.yaml`
  LLM 后端注册表
- `embedding_backends.yaml`
  向量后端注册表

现在切换模型通常只需要改薄 wrapper 里的 backend id，不需要再复制整份 pipeline 配置。

## 推荐命令

预处理原始 O&M markdown：

```bash
python -m crossextend_kg.cli preprocess --config D:\crossextend_kg\config\persistent\preprocessing.deepseek.yaml
```

运行主流程：

```bash
python -m crossextend_kg.cli run --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml
```

运行消融实验：

```bash
python -m crossextend_kg.experiments.ablation.runner --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\ablation --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

运行 baseline：

```bash
python D:\crossextend_kg\scripts\run_baselines.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\baselines --ground-truth-dir D:\crossextend_kg\data\ground_truth --data-root D:\crossextend_kg\data
```

运行 repeated experiments：

```bash
python D:\crossextend_kg\scripts\run_repeated_experiments.py --config D:\crossextend_kg\config\persistent\pipeline.deepseek.yaml --output-dir D:\crossextend_kg\artifacts\repeated --ground-truth-dir D:\crossextend_kg\data\ground_truth --repeats 3 --include-baselines --data-root D:\crossextend_kg\data
```

## 文档入口

- `docs/README.md`
- `docs/SYSTEM_DESIGN.md`
- `docs/PIPELINE_INTEGRATION.md`
- `docs/MANUAL_ANNOTATION_PROTOCOL.md`
- `docs/AUTO_REVIEW_ACTION_PLAN.md`
- `docs/FIVE_ROUND_OPTIMIZATION_REPORT.md`
