# Data Layout

This repository keeps only the source data assets needed for the current
open-source mainline.

## Tracked Data

- source O&M markdown documents
- human gold annotations under `ground_truth/`
- the frozen multi-document evidence record bundle under
  `evidence_records/full_human_gold_9doc/`

## Untracked Local Runtime Data

The following are intentionally ignored and should stay local:

- temporary evidence-record regeneration outputs
- FAISS cache files
- GraphML run artifacts
- ad hoc debug datasets

The goal is to keep the repo reproducible without turning it into an artifact
dump.
