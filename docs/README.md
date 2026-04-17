# CrossExtend-KG Documentation

本目录只保留当前主架构相关文档。

## 建议阅读顺序

| 文档 | 作用 |
|------|------|
| `SYSTEM_DESIGN.md` | 主架构、阶段划分、运行时约束 |
| `PIPELINE_INTEGRATION.md` | 模块接口、验证点、回归命令 |
| `PROJECT_ARCHITECTURE.md` | 仓库结构与模块职责 |
| `EXECUTION_MEMORY.md` | 续工执行记忆，记录当前架构、已完成优化和后续计划 |
| `REAL_RUN_DATA_FLOW_BATTERY_20260417.md` | 真实 battery 跑通链路的逐阶段数据流文档 |
| `REAL_RUN_DATA_FLOW_BATTERY_20260417_CN.md` | 上述真实数据流文档的中文版 |

## 范围说明

这里不再保留评测设计、下游任务、历史实验总结或论文草案文档。

## 相关目录

- `../config/`: 运行配置与模板
- `../pipeline/`: 当前核心实现
- `../preprocessing/`: 预处理链路
- `../rules/`: attachment 决策过滤规则
