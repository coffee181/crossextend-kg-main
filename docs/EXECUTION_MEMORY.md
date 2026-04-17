# CrossExtend-KG Execution Memory

**Updated**: 2026-04-17  
**Purpose**: Resume-oriented working memory for future terminals / sessions  
**Scope**: Current active `crossextend_kg` main architecture, fixes completed so far, validated behavior, and agreed next-step direction

## 1. Current Project Position

CrossExtend-KG is currently kept on the **main architecture only**.

The active direction is:

- fixed shared backbone
- no dynamic backbone growth
- domain concepts must attach to the fixed backbone
- keep the main chain only: `reuse_backbone`, `vertical_specialize`, `reject`
- no architectural fallback or silent degradation
- keep graph construction auditable
- prioritize stable end-to-end runtime over experiments or downstream tasks

Removed / de-emphasized:

- dynamic backbone experiments
- evaluation-only paths
- downstream-task code and docs
- extra route families such as `relation_instantiate` and `slot_bind`

## 2. Architecture Decisions Already Confirmed

These are user-confirmed architectural constraints and should be treated as active design law unless explicitly changed.

### Backbone

- backbone is **predefined and frozen**
- backbone is shared upper ontology across industrial domains
- backbone does **not** grow dynamically during runtime
- domain candidates must hang under backbone concepts

### Active Attachment Routes

Only these routes are allowed:

- `reuse_backbone`
- `vertical_specialize`
- `reject`

### No Fallback Principle

This is an explicit user-added hard rule and must be preserved:

- **no fallback operations**
- the full chain must run according to the designed architecture
- do not silently downgrade to alternative heuristics just to "make it run"
- if a stage is architecturally required, it should either:
  - run correctly
  - or fail explicitly

Implications:

- do not introduce alternate degraded paths that bypass architecture decisions
- do not replace required semantic stages with loose best-effort shortcuts without explicit approval
- do not silently skip required checks, routing, validation, or structure-building steps
- explicit deterministic normalization inside the architecture is acceptable
- silent emergency downgrade behavior is not acceptable

### Node Admission Policy

The agreed principle is:

- `宽进严出`
- preprocessing may keep coarse `node_worthy`
- final graph admission happens at attachment/filtering time

Confirmed node policy:

- person names do not enter the graph
- document titles do not enter the graph
- observations may enter only if they are graph-worthy and grounded appropriately
- state-transition / fault-chain style nodes are allowed when useful
- components / mechanisms must both:
  - anchor to the backbone
  - participate in relation chains
- rejected candidates must be preserved in audit artifacts with explicit reject reasons

Important clarification:

- **reasonable reject is correct and desired**
- the goal is **not** to make `reject = 0`
- the goal is to reduce noisy failures caused by bad anchoring, bad relation family assignment, or wrong direction, especially `rejected_type`

## 3. Current Runtime Architecture

The active chain is:

1. `preprocessing/` converts raw documents into `EvidenceRecord`
2. `pipeline/evidence.py` loads records and aggregates `SchemaCandidate`
3. `pipeline/backbone.py` builds frozen backbone from config
4. `pipeline/router.py` retrieves candidate-to-backbone anchors via embeddings
5. `pipeline/memory.py` retrieves historical context from memory bank
6. `pipeline/attachment.py` decides candidate routing
7. `rules/filtering.py` enforces legality and final node admission
8. `pipeline/graph.py` builds schema, triples, edges, temporal artifacts, snapshots
9. `pipeline/artifacts.py` exports run artifacts and summaries

Key active files:

- [config.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/config.py)
- [models.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/models.py)
- [pipeline/runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)
- [pipeline/evidence.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/evidence.py)
- [pipeline/attachment.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/attachment.py)
- [pipeline/graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)
- [pipeline/artifacts.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/artifacts.py)
- [pipeline/relation_validation.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/relation_validation.py)
- [preprocessing/processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)
- [rules/filtering.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/rules/filtering.py)

## 4. Important Fixes Already Completed

### Earlier reliability fixes

Completed before the latest architecture tuning:

- snapshot replay bug fixed when `write_jsonl_artifacts=false`
- preprocessing timestamp normalization fixed
- preprocessing strictness for missing / empty configured domains fixed
- preprocessing `config_path` propagation fixed
- `pipeline/validation.py` renamed to `pipeline/relation_validation.py`
- preprocessing remains fail-explicit when required LLM config is missing; no extraction fallback is allowed

### Main architecture simplification

Completed:

- removed old route branches from active configs and validation
- removed legacy active types related to now-removed route branches
- simplified schema candidate handling to the active route set
- aligned docs, templates, and tests to the simplified route model

### Node-admission and reject-reason work

Completed:

- introduced structured reject-reason handling
- `AttachmentDecision` now has:
  - `admit_as_node`
  - `reject_reason`
- candidate triples now preserve reject reasons
- artifacts now export rejected candidates grouped by reason

Current reject reasons in active use include:

- `person_name`
- `document_title`
- `observation_like_not_grounded`
- `cannot_anchor_backbone`
- `weak_relation_support`
- `unsupported_semantic_type`
- `route_not_allowed`
- `invalid_backbone_parent`
- `llm_no_decision`
- `backbone_label_mismatch`

### Runtime robustness fixes from real smoke testing

Completed:

- missing-LLM-decision explicit reject handling now rejects with `admit_as_node=false`
- prompt/schema mismatch for reject reasons fixed
- invalid LLM `reuse_backbone` on non-backbone labels now normalizes into anchored `vertical_specialize`
- document-title heuristic narrowed to avoid misclassifying component-like concepts just because descriptions mention logging
- relation constraints updated to better reflect active runtime semantics
- relation direction normalization added in preprocessing for passive forms such as:
  - `measured_by`
  - `confirmed_by`
  - `observed_in`
  - `performed_by`
- deterministic parent-anchor correction added to reduce avoidable anchor drift
- data-flow trace artifact added

## 5. Current Artifact and Audit Structure

Each variant exports the usual run artifacts, plus important per-domain audit files.

Most useful current working artifacts:

- `adapter_candidates.json`
- `adapter_candidates.accepted.json`
- `adapter_candidates.rejected.json`
- `adapter_candidates.rejected_by_reason.json`
- `attachment_decisions.json`
- `relation_edges.candidates.json`
- `relation_edges.accepted.json`
- `relation_edges.rejected.json`
- `relation_edges.rejected_type.json`
- `final_graph.json`
- `construction_summary.json`
- `data_flow_trace.json`

Current design intent:

- candidate rejection should remain visible
- relation rejection should distinguish:
  - family-level rejection
  - type-constraint rejection
- snapshot state files must remain replayable even when general JSONL export is disabled
- architecture-required stages should fail explicitly rather than silently degrading

## 6. Validation Status

Regression suite status at last update:

- `pytest -q tests/test_crossextend_kg_regressions.py`
- result: `25 passed`

Key regression coverage now includes:

- config loading and schema consistency
- fixed backbone loading
- preprocessing path/env correctness
- removed evaluation-field regression protection
- snapshot replay export correctness
- timestamp normalization
- missing/empty configured-domain handling
- person/document rejection
- no-relation-support rejection
- signal/state admission survival
- rejected-by-reason artifact export
- missing LLM decision fallback behavior
- invalid `reuse_backbone` normalization
- observation reject-reason schema compatibility
- relation-constraint sanity
- component re-anchoring
- passive relation normalization
- signal-like observation re-anchoring

## 7. Latest Real Smoke-Test Status

Real battery single-document runs were executed with:

- local embedding backend: `ollama` + `bge-m3:latest`
- external LLM backend: DeepSeek API

The latest strong smoke result is:

- run root: [tmp/crossextend_kg_battery_single_strict_20260417T105948Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z)
- pipeline artifact root: [battery_single_strict-20260417T110121Z](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z)

Most relevant outputs:

- [construction_summary.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/construction_summary.json)
- [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)
- [final_graph.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/final_graph.json)
- [adapter_candidates.rejected_by_reason.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/adapter_candidates.rejected_by_reason.json)

Summary of this latest smoke run:

- `30` schema candidates
- `28` admitted candidates
- `2` candidate rejects
- reject reasons:
  - `document_title = 1`
  - `person_name = 1`
- graph:
  - `28` nodes
  - `28` edges
  - `31` candidate triples
  - `28` accepted triples
  - `3` family-level rejected triples
  - `0` type-rejected triples
- important spot check:
  - `Battery Management System (BMS)` now anchors to `Component`

Interpretation:

- reasonable candidate reject remains present
- avoidable `rejected_type` noise has been effectively removed in this tested battery path
- main chain is currently usable for document-to-graph construction

## 8. Current Design Interpretation of Labels

Current working understanding:

- backbone concepts are upper anchors, not graph labels to rename everything into
- domain labels should remain **vertical concepts**
- graph nodes should keep concrete industrial terms
- the backbone should appear through `parent_anchor`, not by rewriting every label into a type-style name

Examples of the intended pattern:

- `Battery Management System (BMS)` with `parent_anchor=Component`
- `Voltage Curve` with `parent_anchor=Signal`
- `Remote Data Dump` with `parent_anchor=Task`
- `Capacity Fade` or `Reduced Capacity` with `parent_anchor=State` or `Fault` depending on semantics

Rejected naming direction:

- do **not** aggressively rewrite concepts into labels like `Voltage Curve Signal` or `Remote Data Dump Task` merely to make type explicit
- the architecture is meant to be **vertical specialization under backbone**, not type-label rewriting

## 9. Agreed Direction for Future Data

The user clarified that future real data will likely be:

- operations / maintenance forms
- stepwise records
- time-stamped action logs

Because of this, the current conclusion is:

- heavy concept-merge optimization is **not** the immediate priority
- only light terminology normalization remains worth keeping
- the more important future design problem is:
  - time steps
  - actions
  - observations
  - state transitions
  - record-to-graph construction

## 10. Agreed Future Architecture Direction

The next major design direction should be **two-layer graph organization**, but implementation should wait until concrete example data is provided.

### Concept Layer

This layer should contain reusable vertical domain concepts attached to fixed backbone concepts.

Examples:

- assets
- components
- tasks
- signals
- states
- faults

This layer should remain stable and reusable across records.

### Execution Layer

This layer should represent time-step / operation-record instances.

Likely future event-node style:

- action execution
- signal observation
- state assertion
- fault confirmation
- maintenance action
- inspection / diagnosis step

This layer is intended to capture:

- when something happened
- in what order
- to which object
- with what result

### Cross-Layer Links

Execution-layer instances should link into concept-layer nodes through relations such as:

- uses task
- acts on component / asset
- observes signal
- asserts state
- confirms fault

Important principle:

- do not pollute the concept layer with raw time-step instances
- do not force timestamps, work-order ids, form titles, or person names into concept nodes

## 11. What Is Deferred For Now

The following are intentionally **not** the immediate next implementation target:

- heavy semantic merge / merge-proposal pipeline
- embedding-driven concept merge optimization
- LLM concept-equivalence judgement
- cross-document open-ended concept clustering
- detailed execution-layer implementation without seeing real operations-form examples

Rationale:

- likely future data is form/timeline centric
- current priority should stay on runtime correctness and later timeline-aware structure design

## 12. Recommended Resume Procedure For Future Sessions

When resuming work in a new terminal/session:

1. Read this file first:
   [EXECUTION_MEMORY.md](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/docs/EXECUTION_MEMORY.md)
2. Then inspect:
   [PROJECT_ARCHITECTURE.md](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/docs/PROJECT_ARCHITECTURE.md)
   [SYSTEM_DESIGN.md](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/docs/SYSTEM_DESIGN.md)
3. If checking code status, start from:
   [runner.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/runner.py)
   [attachment.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/attachment.py)
   [filtering.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/rules/filtering.py)
   [processor.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/preprocessing/processor.py)
   [graph.py](/home/libaizheng/Auto-claude-code-research-in-sleep/crossextend_kg/pipeline/graph.py)
4. If checking latest validated runtime behavior, inspect:
   [data_flow_trace.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/data_flow_trace.json)
   [final_graph.json](/home/libaizheng/Auto-claude-code-research-in-sleep/tmp/crossextend_kg_battery_single_strict_20260417T105948Z/artifacts/battery_single_strict-20260417T110121Z/full_llm/working/battery/final_graph.json)

## 13. Immediate Next Step When Real Form Data Arrives

Do **not** jump straight into code.

First:

- inspect concrete operations-form examples
- determine the real shape of:
  - time steps
  - actions
  - observations
  - status fields
  - actor/operator fields
  - object identifiers
  - provenance fields

Then design:

- execution-layer event schema
- concept-layer / execution-layer boundary
- event admission rules
- cross-layer linking rules
- artifact export shape for timeline replay

That future design should be grounded in real example data, not guessed in advance.
