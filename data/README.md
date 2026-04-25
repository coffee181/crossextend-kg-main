# Data Layout

Source data assets for the CrossExtend-KG v2 mainline.

## Tracked Data

- Source O&M markdown documents under `battery_om_manual_en/`, `cnc_om_manual_en/`, `ev_om_manual_en/`
- Human gold annotations under `ground_truth/` (9 files: 3 per domain)
- Evidence records under `evidence_records/` (3 domain files)
- Ground truth annotation templates under `ground_truth/template/`
- Temporal lifecycle event annotations under `ground_truth/temporal/`

## Directory Structure

```
data/
  battery_om_manual_en/    # Battery O&M source markdown
  cnc_om_manual_en/        # CNC O&M source markdown
  ev_om_manual_en/         # NEV O&M source markdown
  evidence_records/
    battery_evidence_records_llm.json   # 3 battery documents
    cnc_evidence_records_llm.json       # 3 cnc documents
    nev_evidence_records_llm.json       # 3 nev documents
  ground_truth/
    battery_BATOM_001.json   # Gold annotation
    battery_BATOM_002.json
    battery_BATOM_003.json
    cnc_CNCOM_001.json
    cnc_CNCOM_002.json
    cnc_CNCOM_003.json
    nev_EVMAN_001.json
    nev_EVMAN_002.json
    nev_EVMAN_003.json
    template/               # Annotation specs and templates
    temporal/               # Lifecycle event annotations
  faiss-data/              # (empty, runtime cache placeholder)
```

## Untracked Local Runtime Data

The following are intentionally ignored and should stay local:

- FAISS cache files (`faiss-data/`)
- GraphML run artifacts
- Temporary evidence-record regeneration outputs
- Ad hoc debug datasets

The goal is to keep the repo reproducible without turning it into an artifact dump.
