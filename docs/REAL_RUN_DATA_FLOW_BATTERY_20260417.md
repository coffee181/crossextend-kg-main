# CrossExtend-KG Real Run Data Flow

**Date**: 2026-04-17  
**Run Type**: Real battery single-document end-to-end smoke test  
**Purpose**: Show the actual end-to-end data flow from raw document to final graph, including input/output formats, intermediate artifacts, processing logic, and concrete results from one real run

## 1. Run Identity

This document describes the latest validated real run:

- run root: [tmp/crossextend_kg_battery_single_strict_20260417T105948Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z)
- pipeline artifact root: [battery_single_strict-20260417T110121Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z)
- variant: `full_llm`

Backends used in this run:

- preprocessing LLM: `deepseek-chat`
- attachment LLM: `deepseek-chat`
- embedding backend: local `ollama`
- embedding model: `bge-m3:latest`

## 2. Directory Layout Used By This Run

```text
tmp/crossextend_kg_battery_single_strict_20260417T105948Z/
├── raw_data/
│   └── battery/fault_cases/battery_fault_0001.md
├── configs/
│   ├── preprocessing.json
│   └── pipeline.json
├── outputs/
│   └── evidence_records_battery_single.json
└── artifacts/
    └── battery_single_strict-20260417T110121Z/
        └── full_llm/
            ├── run_meta.json
            ├── backbone_seed.json
            ├── backbone_final.json
            ├── backbone.json
            ├── construction_summary.json
            ├── data_flow_trace.json
            ├── temporal_memory_entries.jsonl
            └── working/battery/
                ├── adapter_candidates.json
                ├── adapter_candidates.accepted.json
                ├── adapter_candidates.rejected.json
                ├── adapter_candidates.rejected_by_reason.json
                ├── adapter_schema.json
                ├── attachment_decisions.json
                ├── backbone_reuse_candidates.json
                ├── final_graph.json
                ├── historical_context.json
                ├── relation_edges.accepted.json
                ├── relation_edges.candidates.json
                ├── relation_edges.rejected.json
                ├── relation_edges.rejected_type.json
                ├── retrievals.json
                ├── snapshots/
                └── exports/
```

## 3. Stage-by-Stage Data Flow

## Stage 0. Raw Document Input

### Input file

- [battery_fault_0001.md](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/raw_data/battery/fault_cases/battery_fault_0001.md)

### Input format

Plain Markdown fault case document containing:

- case overview
- equipment / product identifiers
- timestamp
- environment conditions table
- diagnosis process timeline
- root cause analysis
- solution / prevention notes

### Key content present in this document

- asset-like concept: `Battery Pack`
- component-like concepts: `Battery Management System (BMS)`, `Cell`, `Anode`, `Cathode`, `Separator`
- fault / mechanism concepts: `Capacity Degradation Fault`, `SEI Layer Growth`, `Lithium Plating`, `Cathode Micro-cracking`
- state / signal / task information embedded in the narrative timeline
- person information: `Dr. A. Chen`
- document identity: `Battery Fault Diagnosis Case Document`

### Architectural interpretation at this stage

At this stage nothing is yet a graph node.

The file is only:

- raw source text
- provenance input
- extraction source

## Stage 1. Preprocessing Config Construction

### Input config file

- [preprocessing.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/preprocessing.json)

### Actual important fields

```json
{
  "data_root": ".../raw_data",
  "domain_ids": ["battery"],
  "output_path": ".../outputs/evidence_records_battery_single.json",
  "prompt_template_path": ".../crossextend_kg/config/prompts/preprocessing_extraction.txt",
  "llm": {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "timeout_sec": 600,
    "max_tokens": 4096,
    "temperature": 0.1
  }
}
```

### What this stage defines

- which raw directory to scan
- which domain ids are valid
- where preprocessing output will be written
- which prompt template is used for extraction
- which LLM backend is mandatory

### Important rule

Preprocessing has **no fallback**.

If `llm.base_url` or `llm.model` is missing, preprocessing must fail explicitly rather than silently using another extraction mode.

Related implementation:

- [processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)

## Stage 2. Raw Markdown Parsing -> DocumentInput

### Code path

- [parser.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/parser.py)

### Transformation

The markdown file is parsed into an internal `DocumentInput` object.

### Logical fields created

- `doc_id`
- `doc_type`
- `domain_id`
- `role`
- `title`
- `content`
- `metadata`
- `timestamp`

### For this run

The parsed values effectively become:

```json
{
  "doc_id": "battery_fault_0001",
  "doc_type": "fault_case",
  "domain_id": "battery",
  "role": "target",
  "timestamp": "2023-10-26T00:00:00Z"
}
```

### Important processing details

This stage performs:

- title extraction from markdown heading
- `doc_id` generation from file name
- timestamp extraction and normalization into UTC ISO format
- raw content loading

At this stage the data is still document-oriented, not graph-oriented.

## Stage 3. Content Normalization and LLM Extraction

### Code path

- [processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)
- [extractor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/extractor.py)
- prompt: [preprocessing_extraction.txt](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/config/prompts/preprocessing_extraction.txt)

### Input

- `DocumentInput`
- backbone concept list
- relation family list
- extraction prompt

### Internal processing

Before sending content to the LLM:

- markdown content is normalized
- overlong content is truncated to avoid timeout
- prompt is rendered with:
  - backbone concepts
  - relation families
  - document content

### LLM expected output format

The extractor expects JSON with:

```json
{
  "concepts": [
    {
      "label": "Battery Pack",
      "description": "The main energy storage asset.",
      "node_worthy": true
    }
  ],
  "relations": [
    {
      "label": "contains",
      "family": "structural",
      "head": "Battery Pack",
      "tail": "Cell"
    }
  ],
  "extraction_quality": "high"
}
```

### Relation normalization inside preprocessing

After LLM extraction, relation mentions are normalized deterministically before writing `EvidenceRecord`.

Implemented normalizations include:

- passive -> active:
  - `measured_by` -> `measures`
  - `confirmed_by` -> `confirms`
  - `observed_in` -> `observes`
  - `performed_by` -> `performs`
- family normalization for known active labels
- head/tail flipping when passive forms are converted
- duplicate relation removal inside one evidence record

This is architecture-internal normalization, not a fallback path.

## Stage 4. LLM Extraction Output -> EvidenceRecord

### Output file

- [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)

### Top-level output shape

```json
{
  "project_name": "crossextend_kg_preprocessing",
  "generated_at": "...",
  "domains": ["battery"],
  "role": "target",
  "document_count": 1,
  "domain_stats": {
    "battery": {
      "fault_case": 1
    }
  },
  "evidence_records": [...]
}
```

### Single EvidenceRecord shape

```json
{
  "evidence_id": "battery_fault_0001",
  "domain_id": "battery",
  "role": "target",
  "source_type": "fault_case",
  "timestamp": "2023-10-26T00:00:00Z",
  "raw_text": "...",
  "concept_mentions": [...],
  "relation_mentions": [...]
}
```

### Actual result for this run

- `document_count = 1`
- `concept_mentions = 30`
- `relation_mentions = 31`

### Actual concept examples

```json
[
  {
    "label": "Battery Pack",
    "description": "The main energy storage asset, identified by product ID battery_product_001.",
    "node_worthy": true
  },
  {
    "label": "Battery Management System (BMS)",
    "description": "Component that manages the battery pack, provides operational data.",
    "node_worthy": true
  },
  {
    "label": "Capacity Degradation Fault",
    "description": "Fault characterized by significant reduction in battery capacity (BAT-FLT-001-CAP-DEG).",
    "node_worthy": true
  }
]
```

### Actual relation examples

```json
[
  {
    "label": "contains",
    "family": "structural",
    "head": "Battery Pack",
    "tail": "Battery Management System (BMS)"
  },
  {
    "label": "causes",
    "family": "propagation",
    "head": "SEI Layer Growth",
    "tail": "Capacity Degradation Fault"
  },
  {
    "label": "measures",
    "family": "task_dependency",
    "head": "HPPC Test Task",
    "tail": "High Internal Resistance State"
  }
]
```

## Stage 5. Pipeline Config Load

### Input config file

- [pipeline.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/pipeline.json)

### Important runtime fields

```json
{
  "llm": {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
  },
  "embedding": {
    "base_url": "http://127.0.0.1:11434/v1",
    "model": "bge-m3:latest"
  },
  "relations": {
    "relation_families": [
      "task_dependency",
      "communication",
      "propagation",
      "lifecycle",
      "structural"
    ],
    "allowed_routes": [
      "reuse_backbone",
      "vertical_specialize",
      "reject"
    ]
  },
  "runtime": {
    "retrieval_top_k": 3,
    "llm_attachment_batch_size": 8,
    "enable_relation_validation": true,
    "relation_constraints_path": ".../relation_constraints.json",
    "run_prefix": "battery_single_strict"
  },
  "variants": [
    {
      "variant_id": "full_llm",
      "attachment_strategy": "llm",
      "use_embedding_routing": true,
      "use_rule_filter": true,
      "enable_memory_bank": true,
      "enable_snapshots": true
    }
  ]
}
```

### What this stage defines

- the only domain to process
- the active variant
- embedding retrieval behavior
- attachment route set
- whether filtering is enforced
- whether relation validation runs
- whether snapshots are written

## Stage 6. EvidenceRecord -> EvidenceUnit

### Code path

- [evidence.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/evidence.py)

### Input

- `EvidenceRecord` list from `evidence_records_battery_single.json`

### Output structure

`EvidenceUnit` is a normalized evidence container used by the main pipeline:

```json
{
  "evidence_id": "battery_fault_0001",
  "domain_id": "battery",
  "role": "target",
  "source_id": "evidence_records_battery_single.json",
  "source_type": "fault_case",
  "locator": "battery/fault_case/0",
  "raw_text": "...",
  "normalized_text": "...",
  "metadata": {
    "timestamp": "2023-10-26T00:00:00Z"
  }
}
```

### Effect in this run

- `evidence_unit_count = 1`

This is not yet a graph object.
It is a runtime evidence carrier used for:

- provenance
- memory-bank construction
- summaries
- export

## Stage 7. EvidenceRecord -> SchemaCandidate

### Code path

- [evidence.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/evidence.py)

### Aggregation logic

Candidates are grouped by:

- `(domain_id, mention.label)`

Only mentions with `node_worthy=true` are aggregated.

### Candidate structure

```json
{
  "candidate_id": "battery::Battery Pack",
  "domain_id": "battery",
  "role": "target",
  "label": "Battery Pack",
  "description": "The main energy storage asset.",
  "evidence_ids": ["battery_fault_0001"],
  "evidence_texts": ["..."],
  "support_count": 1,
  "routing_features": {
    "support_count": 1,
    "evidence_count": 1,
    "relation_participation_count": 4,
    "relation_head_count": 4,
    "relation_tail_count": 0,
    "relation_families": ["structural"]
  }
}
```

### Important derived routing features

The aggregator computes:

- how many times the concept appears in relations
- whether it appears as head or tail
- which relation families it participates in

This later affects:

- node admission
- weak-support rejection
- anchor reasoning

### Actual result in this run

- `schema_candidate_count = 30`

Relevant artifact:

- [adapter_candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.json)

## Stage 8. Backbone Build

### Code path

- [backbone.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/backbone.py)

### Input

- `backbone.seed_concepts`
- `backbone.seed_descriptions`
- optional `ontology_seed_path` entries

### Current active design

- backbone is frozen
- no dynamic backbone extraction
- no runtime backbone growth from document content

### Backbone concepts used in this run

The active upper ontology contains 11 seed concepts:

- `Asset`
- `Component`
- `Process`
- `Task`
- `Signal`
- `State`
- `Fault`
- `MaintenanceAction`
- `Incident`
- `Actor`
- `Document`

### Exported artifacts

- [backbone_seed.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone_seed.json)
- [backbone_final.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone_final.json)
- [backbone.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/backbone.json)

## Stage 9. Anchor Retrieval

### Code path

- [runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)
- `retrieve_anchor_rankings(...)`

### Input

- each `SchemaCandidate`
- backbone descriptions
- embedding backend
- `top_k = 3`

### Output structure

Each candidate gets up to 3 retrieved anchors:

```json
"battery::Battery Pack": [
  {"anchor": "Asset", "score": 0.6625, "rank": 1},
  {"anchor": "Process", "score": 0.5239, "rank": 2},
  {"anchor": "Component", "score": 0.5143, "rank": 3}
]
```

### Actual examples

`Battery Pack`

```json
[
  {"anchor": "Asset", "score": 0.6625352501869202, "rank": 1},
  {"anchor": "Process", "score": 0.5238973498344421, "rank": 2},
  {"anchor": "Component", "score": 0.514290452003479, "rank": 3}
]
```

`Battery Management System (BMS)`

```json
[
  {"anchor": "Process", "score": 0.6121953725814819, "rank": 1},
  {"anchor": "Task", "score": 0.6014306545257568, "rank": 2},
  {"anchor": "Component", "score": 0.5975511074066162, "rank": 3}
]
```

This is a good example of why retrieval is only a hint:

- pure embedding top-1 would have pushed `BMS` toward `Process`
- later attachment and rule filtering corrected it to `Component`

Artifact:

- [retrievals.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/retrievals.json)

## Stage 10. Historical Context Retrieval

### Code path

- [memory.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/memory.py)

### Purpose

Retrieve previously stored memory-bank context that may help attachment stay temporally consistent.

### Output artifact

- [historical_context.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/historical_context.json)

### In this run

The infrastructure is active, but the main observable result is simply that historical context is available as one of the prompt inputs to attachment.

## Stage 11. Attachment Decision

### Code path

- [attachment.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/attachment.py)

### Input

Per candidate:

- candidate label and description
- routing features
- top-k retrieved anchors
- historical context
- backbone descriptions
- allowed routes

### Attachment output structure

```json
{
  "candidate_id": "battery::Battery Pack",
  "label": "Battery Pack",
  "route": "vertical_specialize",
  "parent_anchor": "Asset",
  "accept": true,
  "admit_as_node": true,
  "reject_reason": null,
  "confidence": 0.85,
  "justification": "...",
  "evidence_ids": ["battery_fault_0001"]
}
```

### Actual runtime behavior in this run

- attachment strategy: `llm`
- batch size: `8`
- 30 candidates processed in 4 batches

### Important examples

`Battery Pack`

```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Asset",
  "admit_as_node": true
}
```

`Battery Management System (BMS)`

```json
{
  "route": "vertical_specialize",
  "parent_anchor": "Component",
  "admit_as_node": true
}
```

`Battery Fault Diagnosis Case Document`

```json
{
  "route": "reject",
  "parent_anchor": null,
  "admit_as_node": false,
  "reject_reason": "document_title"
}
```

### Important runtime protections

This stage also includes:

- normalization of invalid non-backbone `reuse_backbone` decisions into anchored `vertical_specialize`
- explicit reject generation if the LLM returns no decision for a candidate

Artifact:

- [attachment_decisions.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/attachment_decisions.json)

## Stage 12. Rule Filtering and Final Node Admission

### Code path

- [filtering.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/rules/filtering.py)

### Purpose

This is the final node admission gate.

It enforces architecture rules after LLM attachment, rather than trusting the LLM directly.

### Major checks

- person-name rejection
- document-title rejection
- route legality enforcement
- invalid anchor rejection
- no-relation-support rejection
- deterministic parent-anchor correction for obvious semantic drifts

### Output consequence

Only candidates with:

- `admit_as_node = true`

can continue into domain schema construction and graph node materialization.

### Actual result in this run

- candidates total: `30`
- admitted: `28`
- rejected: `2`

Rejected candidates:

1. `Battery Fault Diagnosis Case Document`

```json
{
  "route": "reject",
  "admit_as_node": false,
  "reject_reason": "document_title"
}
```

2. `Diagnosis Engineer`

```json
{
  "route": "reject",
  "admit_as_node": false,
  "reject_reason": "person_name"
}
```

Artifact:

- [adapter_candidates.rejected_by_reason.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.rejected_by_reason.json)

## Stage 13. Domain Schema Materialization

### Code path

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### Input

- admitted candidates
- attachment decisions
- backbone concept list

### Output structure

Only admitted `vertical_specialize` candidates become `AdapterConcept`.

`DomainSchema` shape:

```json
{
  "domain_id": "battery",
  "backbone_concepts": [...],
  "adapter_concepts": [
    {
      "label": "Battery Pack",
      "parent_anchor": "Asset",
      "description": "...",
      "evidence_ids": ["battery_fault_0001"]
    }
  ]
}
```

### Result in this run

- `adapter_concept_count = 28`

Artifact:

- [adapter_schema.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_schema.json)

## Stage 14. Relation Mention -> CandidateTriple

### Code path

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### Input

- original `relation_mentions`
- admitted node labels
- attachment decisions for head and tail concepts

### CandidateTriple structure

```json
{
  "triple_id": "battery::triple::battery_fault_0001::1",
  "domain_id": "battery",
  "head": "Battery Pack",
  "relation": "contains",
  "tail": "Cell",
  "relation_family": "structural",
  "evidence_ids": ["battery_fault_0001"],
  "attachment_refs": ["battery::Battery Pack", "battery::Cell"],
  "confidence": 1.0,
  "reject_reason": null,
  "status": "accepted"
}
```

Possible statuses:

- `accepted`
- `rejected`
- `rejected_type`

### Result in this run

- candidate triples total: `31`

### Family-level rejections in this run

Three triples were rejected because one or both ends had already been rejected as non-graph-worthy:

1. `Diagnosis Engineer performs Remote Data Dump Task`
2. `Diagnosis Engineer documents Battery Fault Diagnosis Case Document`
3. `Battery Fault Diagnosis Case Document describes Capacity Degradation Fault`

Artifact:

- [relation_edges.candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.candidates.json)
- [relation_edges.rejected.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected.json)

## Stage 15. Relation Validation

### Code path

- [relation_validation.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/relation_validation.py)
- constraint file: [relation_constraints.json](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/config/persistent/relation_constraints.json)

### Validation inputs

For each candidate edge:

- relation family
- head label
- tail label
- node type lookup built from:
  - backbone labels
  - adapter `parent_anchor`

### Validation outputs

Each candidate relation can become:

- accepted
- family-rejected
- type-rejected

### Actual result in this run

```json
{
  "total_candidates": 31,
  "accepted": 28,
  "rejected_family": 3,
  "rejected_type": 0
}
```

Interpretation:

- all 3 rejected relations were rejected because their nodes were not admitted
- there were **no** remaining type-constraint failures in this run

Artifact:

- [relation_edges.accepted.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.accepted.json)
- [relation_edges.rejected_type.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected_type.json)

## Stage 16. GraphNode / GraphEdge Materialization

### Code path

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)

### Node creation rule

A concept mention becomes a `GraphNode` only if:

- it appears in the raw record
- it is `node_worthy`
- its label is in the admitted label set

### Node structure

```json
{
  "node_id": "battery::node::Battery Pack",
  "label": "Battery Pack",
  "domain_id": "battery",
  "node_type": "adapter_concept",
  "parent_anchor": "Asset",
  "provenance_evidence_ids": ["battery_fault_0001"]
}
```

### Edge structure

```json
{
  "edge_id": "battery::edge::Battery Pack::contains::Cell",
  "domain_id": "battery",
  "label": "contains",
  "family": "structural",
  "head": "Battery Pack",
  "tail": "Cell",
  "provenance_evidence_ids": ["battery_fault_0001"]
}
```

### Final graph result in this run

- nodes: `28`
- edges: `28`

Examples of accepted edges:

- `Battery Pack contains Battery Management System (BMS)`
- `Battery Pack contains Cell`
- `SEI Layer Growth causes Capacity Degradation Fault`
- `Operational Data Signal indicates Reduced Capacity State`
- `Battery Management System (BMS) provides Operational Data Signal`

## Stage 17. Snapshot and Temporal Artifact Generation

### Code path

- [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)
- [artifacts.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/artifacts.py)

### What is generated

Because `enable_snapshots=true`, each processed evidence record generates:

- one `SnapshotManifest`
- one `SnapshotState`
- `TemporalAssertion` entries for newly observed nodes and edges

### Result in this run

There is only one source record, so:

- `snapshot_count = 1`

Snapshot files are written under:

- [snapshots](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/snapshots)

### Important note

This is still a document-level snapshot mechanism, not yet the future time-step execution-layer design discussed for operations-form data.

## Stage 18. Final Export Layer

### Run-level exported files

At the variant root:

- [run_meta.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/run_meta.json)
- [construction_summary.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/construction_summary.json)
- [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)

### Domain working files

Inside `working/battery/`:

- candidate audit
- retrieval audit
- attachment audit
- relation acceptance / rejection audit
- final graph
- snapshot state
- export-ready graph formats

### Meaning of `data_flow_trace.json`

This file is a compressed summary of the whole run, containing:

- candidate counts
- rejection reasons
- admitted labels
- accepted edges
- node / edge / triple counts

For this run:

```json
{
  "schema_candidate_count": 30,
  "admitted_candidate_count": 28,
  "rejected_candidate_count": 2,
  "rejected_candidate_reasons": {
    "document_title": 1,
    "person_name": 1
  },
  "graph_node_count": 28,
  "graph_edge_count": 28,
  "candidate_triple_count": 31,
  "accepted_triple_count": 28,
  "rejected_triple_count": 3,
  "type_rejected_triple_count": 0
}
```

## 4. Full Pipeline Compression: File-to-File Map

## Raw -> Preprocess

- input:
  - [battery_fault_0001.md](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/raw_data/battery/fault_cases/battery_fault_0001.md)
- config:
  - [preprocessing.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/preprocessing.json)
- output:
  - [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)

## Preprocess Output -> Main Pipeline Input

- input:
  - [evidence_records_battery_single.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/outputs/evidence_records_battery_single.json)
- config:
  - [pipeline.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/configs/pipeline.json)
- runtime code:
  - [runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)

## Candidate Build / Retrieval / Attachment

- candidate audit:
  - [adapter_candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.json)
- retrieval audit:
  - [retrievals.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/retrievals.json)
- attachment audit:
  - [attachment_decisions.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/attachment_decisions.json)
- reject audit:
  - [adapter_candidates.rejected_by_reason.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.rejected_by_reason.json)

## Triple / Edge Construction

- all candidate triples:
  - [relation_edges.candidates.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.candidates.json)
- accepted triples / edges:
  - [relation_edges.accepted.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.accepted.json)
- rejected triples:
  - [relation_edges.rejected.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected.json)
- type-rejected triples:
  - [relation_edges.rejected_type.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/relation_edges.rejected_type.json)

## Final Graph and Summary

- final graph:
  - [final_graph.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/final_graph.json)
- construction summary:
  - [construction_summary.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/construction_summary.json)
- data flow summary:
  - [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)

## 5. Final Observations From This Real Run

### What worked

- full chain ran from raw markdown to final graph
- no architectural fallback was used
- frozen backbone remained intact
- node-admission filtering worked
- reasonable rejects remained visible
- relation type noise was reduced to zero in this run

### What was intentionally rejected

- document title did not become a graph node
- person-name concept did not become a graph node
- relations attached to those rejected nodes were also rejected

### What this run still is not

This run is still a **document-to-concept-graph** run.

It is not yet the future:

- operations-form execution layer
- time-step event chain
- action-instance graph
- state-transition execution graph

Those will need separate design once real operations-form examples are provided.
