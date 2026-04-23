# Downstream Evaluation Design

This directory freezes the current paper-facing downstream contract for the
workflow-first CrossExtend-KG graph.

## Why The Task Set Changed

The active graph is not a generic static semantic KG. It primarily represents:

- `workflow_step -> workflow_step` for ordered maintenance flow
- `workflow_step -> semantic node` for evidence grounding
- semantic edges for structure and diagnosis support

Because of that, the downstream benchmark should reward workflow recovery and
repair completion, not generic entity lookup or one-step-only recommendation.

## Active Tasks

### 1. `workflow_retrieval`

Goal:
Given a complaint, local boundary, symptom cluster, or partial workflow prefix,
retrieve the most relevant ordered workflow suffix together with the grounded
objects that justify it.

Recommended metrics:

- `Step Recall@k`
- `MRR`
- `nDCG@k`
- `Suffix Exact Match`
- `Grounded Object Recall@k`

### 2. `repair_suffix_ranking`

Goal:
Given an observed workflow prefix plus a small set of candidate repair suffixes,
rank which suffix best closes the fault localization, repair, and verification
process.

Recommended metrics:

- `Top-1 Accuracy`
- `MRR`
- `nDCG@k`
- `Suffix Exact Match`

## Annotation Guidance

Downstream labels should be annotated from source O&M text, not from graph
outputs or strict metric reports.

Recommended first benchmark scale:

- 3 to 5 queries per document
- 9 documents total
- about 30 to 45 evaluation samples

## Current Repository Contract

This repository currently freezes:

- the typed schema in `schema.py`
- the benchmark template in `benchmark.template.json`
- the annotation and metric boundary in repo docs

The execution-time downstream benchmark runner is intentionally not frozen yet.
That keeps the repo honest: the committed contract is the benchmark format and
task definition, not an overfit evaluator.
