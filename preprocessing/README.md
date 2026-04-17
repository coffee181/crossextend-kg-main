# Preprocessing Module

将工业领域 markdown 文档转换为主链路可消费的 `EvidenceRecord`。

## 目标

预处理阶段只负责两件事：

- 抽取概念提及
- 抽取关系提及

它不再负责生成评估专用字段。

## 运行方式

```bash
crossextend-kg preprocess \
  --config crossextend_kg/config/persistent/preprocessing.deepseek.json
```

## 最小配置

```json
{
  "data_root": "../../data/",
  "domain_ids": ["battery", "cnc", "nev"],
  "output_path": "../../data/evidence_records_llm.json",
  "role": "target",
  "prompt_template_path": "../prompts/preprocessing_extraction.txt",
  "llm": {
    "base_url": "https://api.deepseek.com",
    "api_key": "${DEEPSEEK_API_KEY}",
    "model": "deepseek-chat"
  }
}
```

## 配置位置

- 预处理 preset: `crossextend_kg/config/persistent/preprocessing*.json`
- 预处理 prompt: `crossextend_kg/config/prompts/preprocessing_extraction.txt`

## 输出格式

```json
{
  "evidence_id": "fault_001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "fault_case",
  "timestamp": "2026-04-17T00:00:00Z",
  "raw_text": "...",
  "concept_mentions": [
    {
      "label": "Battery Pack",
      "description": "Energy storage unit",
      "node_worthy": true
    }
  ],
  "relation_mentions": [
    {
      "label": "contains",
      "family": "structural",
      "head": "Battery Pack",
      "tail": "Temperature Sensor"
    }
  ]
}
```
