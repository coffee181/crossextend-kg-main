# Downstream Evaluation Plan

## Core Position

CrossExtend-KG should not be judged only as a semantic triple generator. The
active graph is workflow-first:

- workflow sequence edges encode procedure order
- workflow grounding edges connect steps to acted-on evidence
- semantic edges provide structural and diagnostic support

Because of that, the downstream benchmark should test whether the graph helps a
technician recover, rank, and complete an O&M workflow.

## Task 1: Evidence-Grounded Workflow Retrieval

### Goal

Given a complaint, symptom cluster, local assembly boundary, or partial prefix,
retrieve the most relevant ordered workflow suffix and the grounded objects that
justify it.

### Expected Output

- ranked workflow steps
- optionally ordered suffix steps
- grounded semantic objects that support the suffix

### Recommended Metrics

- `Step Recall@k`
- `MRR`
- `nDCG@k`
- `Suffix Exact Match`
- `Grounded Object Recall@k`

## Task 2: Repair Suffix Ranking

### Goal

Given an observed workflow prefix and a small set of candidate repair suffixes,
rank which suffix best closes the fault localization, repair, and verification
process.

### Expected Output

- ranked candidate suffix ids
- optionally the best ordered suffix

### Recommended Metrics

- `Top-1 Accuracy`
- `MRR`
- `nDCG@k`
- `Suffix Exact Match`

## Recommended Baselines

Use baselines aligned with the current graph design:

- `text_only_retrieval`
- `semantic_only_graph`
- `workflow_only_graph`
- `dual_layer_graph`

Do not use a pure entity-completion baseline as the only comparison target,
because it does not test the main contribution of the current graph shape.

## Annotation Policy

Downstream labels may be re-annotated from source O&M text and do not need to
inherit the current graph-construction gold one-to-one.

Rules:

- annotate from source text only
- do not inspect model outputs before labeling
- prefer bounded ranking tasks over open-ended QA
- keep each sample grounded to one source document in the first benchmark round

## Suggested First Benchmark

- 9 documents
- 3 to 5 downstream queries per document
- about 30 to 45 total samples

Use the typed schema and template under `experiments/downstream/`.
