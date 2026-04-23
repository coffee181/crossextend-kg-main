# Graph Quality Diagnosis

## Current Objective

Graph quality is judged in two complementary ways:

1. strict graph-construction metrics
2. readable graph usability for workflow understanding

The repository keeps both views separate:

- `final_graph.json`
  fidelity-first accepted graph
- GraphML
  readable-first exported graph view

## Current Readability Policy

Workflow edges keep both raw and display forms:

- `raw_label`
- `display_label`

GraphML is allowed to hide low-value workflow display edges while preserving the
full accepted graph in JSON artifacts.

## Current Quality Checks

Useful graph-quality diagnostics include:

- workflow display verb vocabulary size
- low-value action-object edge rate
- structural self-loop count
- readable isolated node ratio
- readable semantic family coverage

## Current Interpretation Boundary

If strict metrics improve, that supports graph-construction quality.
If readable GraphML improves, that supports downstream usability.

These are related but not identical claims, so they should not be mixed in the
paper narrative.
