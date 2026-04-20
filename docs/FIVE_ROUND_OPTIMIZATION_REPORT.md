# Five-Round Optimization Report

## 1. Background And Goal

- This report records a five-round optimization program for the CrossExtend-KG O&M pipeline under a strict no-fallback rule.
- Every round used real runs, audited the end-to-end dataflow, fixed mainline logic defects, reran evaluation, and synchronized the project documentation.
- The fixed round scopes were BATOM_002 in Rounds 1-2, BATOM_002/CNCOM_002/EVMAN_002 in Round 3, all 9 human-gold files in Round 4, and frozen multi-document replay in Round 5.

## 2. Initial State And Major Problems

- Relation noise was too high, especially from over-promoted structural and step-local edges.
- Signal / Fault / State boundaries were unstable, which made attachment quality sensitive to phrasing rather than semantics.
- Cross-domain evaluation was partially invalid because the CNC markdown filenames and gold ids were content-misaligned.
- The evaluation layer lacked a unified round-preparation, manifest, and reporting structure, which made reproducibility and ablation tracking weaker than the paper needed.
- Human-gold evaluation also exposed annotation risks, most notably BATOM_001 where the staged markdown has 8 task steps but the current gold covers only 6.

## 3. Five-Round Overview

| Round | Modification Theme | Impact Module | Result |
|---|---|---|---|
| Round 1 | Relation denoising and structural contraction on BATOM_002 | preprocessing/processor.py; rules/filtering.py; preprocessing contract tests | concept F1 0.8485 -> 0.8696; anchor acc 0.9762 -> 1.0000; relation F1 0.5818 -> 0.6957 |
| Round 2 | Semantic boundary refinement for Signal / Fault / State | config/prompts/preprocessing_extraction_om.txt; rules/filtering.py; semantic regression tests | concept F1 0.8696 -> 0.9556; anchor acc 1.0000 -> 1.0000; relation F1 0.6957 -> 0.8649 |
| Round 3 | Three-domain mini-regression and alignment repair | round staging / alignment inputs; shared canonicalization path; multi-domain evaluation flow | concept F1 0.5765 -> 0.8183; anchor acc 0.9815 -> 0.9800; relation F1 0.5532 -> 0.6073 |
| Round 4 | Full 9-document human-gold validation and ablation | pipeline/evidence.py; rules/filtering.py; experiments/metrics/core.py; experiments/metrics/evaluate.py; experiments/rounds.py; scripts/prepare_round_run.py; scripts/evaluate_variant_run.py | concept F1 0.6559 -> 0.6818; anchor acc 0.9347 -> 0.9410; relation F1 0.4701 -> 0.5049 |
| Round 5 | Frozen full-corpus replay and stability audit | round freeze configs; reporting / packaging path; final artifact layout | concept F1 0.7070 -> 0.7253; anchor acc 0.9539 -> 0.9530; relation F1 0.5222 -> 0.5218 |

## 4. Round 1 Detailed Record

### Round Metadata

- Title: BATOM_002 Relation Denoising
- Scope: BATOM_002
- Notes: Round 1 fixed alias over-collapse, rewrote contextual structural heads into stable connector parents when recoverable, and rescued high-value hardware candidates from weak-support rejection.

### Summary

### Goal

- Reduce relation noise in the single-document battery run without adding fallback paths.
- Shrink over-expanded structural edges while preserving high-value component anchors.
- Keep the mainline simple: raw extraction -> EvidenceRecord -> candidate aggregation -> attachment -> filtering -> final graph -> metrics.

### Baseline

- Baseline graph: `restore_recovery_batom002-20260419T165617Z`
- Baseline concept metrics: precision `0.8077`, recall `0.8936`, F1 `0.8485`
- Baseline anchor metrics: accuracy `0.9762`, macro-F1 `0.9742`
- Baseline relation metrics: precision `0.4324`, recall `0.8889`, F1 `0.5818`
- Baseline graph size: `52` concepts, `37` relations
- Main baseline issues:
- Structural over-expansion from contextual heads such as `cooling branch`
- Alias instability such as `O-ring` / `green O-ring` and `inner retainer` / `retainer`
- High-value hardware nodes being vulnerable to weak-support rejection

### Post-Run Result

- Post graph: `round01_batom002-20260419T175223Z`
- Concept metrics: precision `0.8889`, recall `0.8511`, F1 `0.8696`
- Anchor metrics: accuracy `1.0000`, macro-F1 `1.0000`
- Relation metrics: precision `0.5714`, recall `0.8889`, F1 `0.6957`
- Graph size reduced to `45` concepts and `28` relations
- Round 1 gate result: passed
- Relation precision improved by `+0.1390`
- Concept F1 improved by `+0.0211`
- Anchor accuracy improved by `+0.0238`
- Main visible effect: noisy structural edges were cut back, while connector-centric component structure was preserved better than baseline

### Next Focus

- Round 2 should address semantic boundary errors that remain in T3 and later steps.
- The biggest remaining issues are:
- Missing `stress whitening -> cracked shell` and `latch-window distortion -> broken latch ear`
- Missing grounded components/signals such as `access panels`, `operating state`, `bend radius`, `clearance`, and `upper-to-lower offset`
- Extra generic concepts such as `replacement connector`, `seal`, and `full engagement`

### Change Log

#### ISSUE-001

- Problem: document-local alias canonicalization collapsed stable components into semantically different observation nodes, most clearly `internal retainer -> inner-retainer wear`
- Root cause: alias matching only used token subsequence and ignored semantic type compatibility
- Modified area: `preprocessing/processor.py`, `tests/test_preprocessing_om_contract.py`
- Expected effect: preserve stable component labels while still canonicalizing safe aliases such as `O-ring -> green O-ring`
- Actual effect: component recall recovered, concept precision rose, and anchor confusions from alias over-collapse were removed
- Status: fixed

#### ISSUE-002

- Problem: contextual structural heads such as `cooling branch` were either over-promoted into the graph or, after naive pruning, caused loss of valuable connector substructure
- Root cause: structural sanitization treated all contextual heads as uniformly low-value instead of attempting to recover a stable parent
- Modified area: `preprocessing/processor.py`, `tests/test_preprocessing_om_contract.py`
- Expected effect: rewrite recoverable `branch -> shell / retainer / O-ring` edges onto a stable connector parent, then prune the remaining contextual noise
- Actual effect: final graph kept connector-centered structure while reducing the structural edge count from `37` baseline relations to `28`
- Status: fixed

#### ISSUE-003

- Problem: high-value hardware nodes such as `aluminum tube bead` and `hose overmold` could still be dropped because LLM attachment gave weak-support rejects
- Root cause: filtering only rescued task nodes and observation-like nodes, but did not rescue high-value component candidates
- Modified area: `rules/filtering.py`, `tests/test_filtering_rules.py`
- Expected effect: keep explicit hardware components when they carry clear component semantics, even if relation support is sparse
- Actual effect: concept F1 rose to `0.8696`, and anchor accuracy reached `1.0000`
- Status: fixed

#### ISSUE-004

- Problem: explicit `Fault` hints such as `recurring seepage` were being demoted to `Signal`
- Root cause: filtering treated all observation-like labels as signal-like even when preprocessing had already emitted a stronger `Fault` prior
- Modified area: `rules/filtering.py`, `tests/test_filtering_rules.py`
- Expected effect: preserve fault anchoring when the label itself carries persistent fault semantics
- Actual effect: anchor confusion list for Round 1 is empty in the final rerun
- Status: fixed

### Dataflow Audit

#### 1. Raw Input

- Input document count: `1`
- Input steps: `10`
- Source document: `BATOM_002.md`
- Key audit note: this round froze one battery O&M form and kept all later reruns scoped to the same document

#### 2. Extraction Output

- Raw extraction concepts: `39`
- Raw extraction relations: `53`
- Extraction quality: `high`
- Important extraction pattern:
- Step-local `task_dependency` edges remained abundant upstream, but these are intentionally explainability-only and not promoted into the final graph
- The remaining upstream weakness is semantic overreach in T3, where `stress whitening` and `latch-window distortion` still point to `bracket side load` instead of the more immediate faults in gold

#### 3. EvidenceRecord

- Step concepts: `32`
- Step relations: `29`
- Document concepts: `6`
- Document relations: `23`
- Key normalization changes:
- alias-safe canonicalization now keeps `internal retainer` separate from `inner-retainer wear`
- contextual structural heads are rewritten when a stable connector parent is recoverable
- structural noise like `cooling branch -> hose overmold` is dropped instead of reaching the final graph

#### 4. SchemaCandidate

- Candidate count: `48`
- Candidate relation-family distribution:
- `task_dependency`: `30`
- `communication`: `13`
- `structural`: `7`
- `lifecycle`: `6`
- `propagation`: `5`
- Important audit note: candidate volume did not collapse; the round improved quality mainly by better normalization and filtering

#### 5. Attachment / Filtering

- Accepted adapter candidates: `45`
- Rejected candidates: `3`
- Reject reasons:
- `observation_like_not_grounded`: `1`
- `low_graph_value`: `2`
- Filtering behavior improved in two ways:
- high-value hardware nodes are now rescued from weak-support rejection
- explicit `Fault` hints are no longer automatically demoted to `Signal`

#### 6. Final Graph

- Final node count: `45`
- Final edge count: `28`
- Accepted triples: `28`
- Rejected triples: `21`
- Edge family distribution:
- `task_dependency`: `9`
- `communication`: `9`
- `structural`: `6`
- `propagation`: `4`
- Node anchor distribution:
- `Task`: `10`
- `Component`: `15`
- `Signal`: `10`
- `Fault`: `5`
- `State`: `4`
- `Asset`: `1`
- Compared with baseline, the graph is materially smaller and cleaner while preserving the same relation recall

#### 7. Metrics

- Concept precision: `0.8077 -> 0.8889`
- Concept recall: `0.8936 -> 0.8511`
- Concept F1: `0.8485 -> 0.8696`
- Anchor accuracy: `0.9762 -> 1.0000`
- Relation precision: `0.4324 -> 0.5714`
- Relation recall: `0.8889 -> 0.8889`
- Relation F1: `0.5818 -> 0.6957`
- Remaining error pattern after Round 1:
- missing grounded geometry and operating-state concepts
- extra generic concepts still not fully canonicalized
- T3 communication edges still need semantic boundary repair

### Logic Audit

- Main logic issue 1: alias canonicalization was syntactic but not semantic.
- Resolution: canonicalization now respects semantic type compatibility so that component labels do not collapse into signal labels.

- Main logic issue 2: structural denoising originally had a false dichotomy.
- Old behavior: either keep contextual structural heads and over-expand the graph, or drop them and lose good substructure.
- New behavior: first try to rewrite recoverable contextual heads to a stable parent, then prune what still looks contextual and low-value.

- Main logic issue 3: the filtering layer was stricter than the architecture intended.
- The pipeline design already treated hardware components as durable graph material, but reject rescue only covered step and observation-like nodes.
- Round 1 aligned the filtering layer with the design by rescuing high-value hardware candidates.

- Edge cases checked this round:
- `internal retainer` vs `inner-retainer wear`
- `cooling branch -> internal retainer` rewritten to `chiller-inlet connector -> internal retainer`
- `recurring seepage` with explicit `Fault` hint

- Remaining risks:
- Attachment still depends on an LLM judge, so semantic ambiguity in T3 can still surface as communication/propagation noise.
- Geometry and setup-state terms such as `bend radius`, `clearance`, and `operating state` are still under-extracted upstream.
- Generic labels such as `seal` and `replacement connector` still need tighter canonicalization rules in Round 2.

### Code Quality Audit

- Naming / responsibility:
- `preprocessing/processor.py` still owns several normalization concerns, but the new helpers are at least separated by intent: aliasing, structural rewriting, and relation retention
- `rules/filtering.py` now better reflects the actual architectural policy instead of only mirroring raw LLM decisions

- Redundancy:
- Round 1 reduced downstream redundancy in the graph by cutting predicted relations from `37` to `28`
- The code now has less implicit duplication between semantic hints and filtering overrides

- Artifact cleanliness:
- Detailed working artifacts remain inside the round-specific output root, not in the general project `working/` path
- The round root now contains a stable set of evidence, raw extraction, metrics, graph summaries, and report files

- Open-source quality judgment:
- Positive: the mainline is clearer, tests were added exactly where logic was tightened, and the round is reproducible from saved inputs and configs
- Still improvable: attachment reproducibility is limited by LLM variability, so later rounds should keep reducing semantic dependence on brittle judge phrasing

### Test Report

- Tests run:
- `pytest tests/test_preprocessing_om_contract.py -q`
- `pytest tests/test_filtering_rules.py -q`
- `pytest tests/test_attachment_logic.py tests/test_graph_assembly.py tests/test_evidence_aggregation.py tests/test_experiments_metrics_and_ablation.py tests/test_reporting_framework.py -q`
- Real run:
- frozen single-document preprocessing snapshot for `BATOM_002`
- full pipeline run with `full_llm`
- metric computation against `data/ground_truth/battery_BATOM_002.json`

- Failures encountered:
- One initial regression test exposed alias collapse because canonical labels were not replacing raw labels in `ConceptMention`
- One runtime bug existed before this round in `preprocessing/processor.py`, where `owner_step` was referenced before assignment

- Regression tests added:
- alias canonicalization with unique document aliases
- structural contextual-head rewrite and prune behavior
- component vs signal alias separation
- rejected high-value component rescue
- explicit `Fault` hint preservation for `recurring seepage`

- Final status:
- All targeted tests passed
- Round 1 single-document real run passed its acceptance gate

## 5. Round 2 Detailed Record

### Round Metadata

- Title: BATOM_002 Semantic Boundary Refinement
- Scope: BATOM_002
- Notes: Round 2 tightened preprocessing semantics for immediate fault targets, preferred stable component labels, accepted reusable geometry measurements, and rejected generic replacement-part nodes plus low-value proof artifacts.

### Summary

### Goal

- Refine `Signal / Fault / State` boundaries in the battery single-document run.
- Keep the Round 1 structural cleanup, then improve semantic fidelity upstream and reduce generic or presentation-only concepts downstream.
- Ensure Round 2 still uses the same no-fallback mainline.

### Baseline

- Baseline was frozen from the final Round 1 run.
- Baseline concept F1: `0.8696`
- Baseline anchor accuracy: `1.0000`
- Baseline relation F1: `0.6957`
- Main open issues entering Round 2:
- missing grounded geometry and operating-state concepts
- generic extras such as `seal`, `replacement connector`, and `full engagement`
- noisy T3 signal-to-fault boundaries

### Post-Run Result

- Post graph: `round02_batom002-20260419T181147Z`
- Concept metrics: precision `1.0000`, recall `0.9149`, F1 `0.9556`
- Anchor metrics: accuracy `1.0000`, macro-F1 `1.0000`
- Relation metrics: precision `0.8421`, recall `0.8889`, F1 `0.8649`
- Extra concepts reduced to `0`
- Predicted graph shrank from `45` concepts / `28` relations in Round 1 to `43` concepts / `19` relations while improving both concept and relation quality

### Next Focus

- Round 3 should verify that the new semantic and filtering rules are not battery-specific.
- Remaining battery issues are narrow and interpretable:
- missing `access panels`, `inlet tube bead`, `burrs`, and `corrosion`
- missing `bracket side load -> cracked shell`
- missing `fresh wetting -> recurring seepage`
- extra structural edges from `tube neck -> aluminum tube bead / lead-in chamfer / O-ring land`

### Change Log

#### ISSUE-001

- Problem: preprocessing still attached several T3 observations to a broad root cause instead of the immediate grounded fault targets
- Root cause: prompt guidance did not strongly distinguish immediate defect targets from broader explanatory causes
- Modified area: `config/prompts/preprocessing_extraction_om.txt`
- Expected effect: make `stress whitening -> cracked shell` and `latch-window distortion -> broken latch ear` easier to elicit, while avoiding relation fan-out
- Actual effect: the T3 relation surface improved substantially and overall relation F1 rose to `0.8649`
- Status: fixed in large part, with only two relation misses remaining overall

#### ISSUE-002

- Problem: generic component labels such as `replacement connector`, `seal`, and `retainer` still polluted the graph
- Root cause: generic replacement-part wording was accepted as stable component nodes even when more specific component labels already existed
- Modified area: `rules/filtering.py`, `config/prompts/preprocessing_extraction_om.txt`, `tests/test_filtering_rules.py`
- Expected effect: reject generic replacement-part nodes and prefer the most specific stable label from extraction
- Actual effect: Round 2 ended with `0` extra concepts against the frozen human gold
- Status: fixed

#### ISSUE-003

- Problem: geometry measurements needed by the gold set, such as `clearance` and `upper-to-lower offset`, were being thrown away as low-value fragments
- Root cause: the filtering layer grouped reusable geometry verification targets together with disposable bookkeeping artifacts
- Modified area: `rules/filtering.py`, `tests/test_filtering_rules.py`
- Expected effect: rescue reusable geometry measurements as `Signal` while continuing to reject bookkeeping artifacts
- Actual effect: concept recall increased from `0.8511` to `0.9149`
- Status: fixed

#### ISSUE-004

- Problem: observation rescue was too permissive and let presentation-only nodes such as `as-found leak path` and `bead condition` back into the graph
- Root cause: any observation-like node with a weak grounding signal could be rescued, even if it only participated in one step-local action edge
- Modified area: `rules/filtering.py`
- Expected effect: make observation rescue depend on stronger evidence, while preserving reusable measurements and genuinely grounded diagnostic nodes
- Actual effect: extra concept count dropped from `5` in Round 1 to `0` in Round 2
- Status: fixed

### Dataflow Audit

#### 1. Raw Input

- Input document count: `1`
- Input steps: `10`
- Same source document as Round 1, allowing direct before/after comparison

#### 2. Extraction Output

- Raw extraction concepts: `49`
- Raw extraction relations: `51`
- Extraction quality: `high`
- Major upstream improvements relative to Round 1:
- `operating state`, `bend radius`, `upper-to-lower offset`, and `clearance` now appear in extraction
- `stress whitening -> cracked shell` and `latch-window distortion -> broken latch ear` are grounded directly in extraction output
- `chiller-inlet connector` is now used as the structural head for `quick-connector shell`, `internal retainer`, and `green O-ring`

#### 3. EvidenceRecord

- Step concepts: `42`
- Step relations: `40`
- Document concepts: `8`
- Document relations: `14`
- Evidence normalization remained step-aware, but the document-level structural layer became much cleaner than Round 1 because the extraction itself was more specific

#### 4. SchemaCandidate

- Candidate count: `59`
- Candidate relation-family distribution:
- `task_dependency`: `38`
- `structural`: `10`
- `communication`: `6`
- `lifecycle`: `3`
- Candidate count rose because the extractor now captures more grounded geometry and verification concepts, but later layers absorb that without graph bloat

#### 5. Attachment / Filtering

- Accepted adapter candidates: `43`
- Rejected candidates: `16`
- Reject reasons:
- `low_graph_value`: `11`
- `observation_like_not_grounded`: `5`
- Important filtering shift in Round 2:
- rescue became more selective for observation-like nodes
- generic replacement-part wording is now rejected
- reusable geometry measurements are rescued as `Signal`

#### 6. Final Graph

- Final node count: `43`
- Final edge count: `19`
- Accepted triples: `19`
- Rejected triples: `35`
- Edge family distribution:
- `task_dependency`: `9`
- `structural`: `7`
- `communication`: `3`
- Node anchor distribution:
- `Task`: `10`
- `Component`: `12`
- `Signal`: `12`
- `Fault`: `5`
- `State`: `3`
- `Asset`: `1`
- Compared with Round 1, the graph is smaller, semantically tighter, and almost perfectly aligned to the single-document gold

#### 7. Metrics

- Concept F1: `0.8696 -> 0.9556`
- Anchor accuracy: `1.0000 -> 1.0000`
- Relation precision: `0.5714 -> 0.8421`
- Relation F1: `0.6957 -> 0.8649`
- Predicted concepts: `45 -> 43`
- Predicted relations: `28 -> 19`
- The central Round 2 outcome is that both concept quality and relation quality improved at the same time

### Logic Audit

- Main logic issue 1: upstream semantic guidance was under-specified for immediate fault targets.
- Round 2 fixed this in the extraction prompt rather than patching it downstream, which is the right direction for long-term code health.

- Main logic issue 2: filtering still treated some reusable geometry measurements as disposable notes.
- The logic is now more faithful to the paper task: measurements explicitly required by the O&M procedure are allowed into the graph when they are reusable diagnostic targets.

- Main logic issue 3: rescue logic had become too forgiving.
- Round 1 made sure useful nodes were not lost; Round 2 added the missing selectivity so that rescued observations must now look genuinely reusable.

- Edge cases checked this round:
- `stress whitening -> cracked shell`
- `latch-window distortion -> broken latch ear`
- `clearance` and `upper-to-lower offset`
- `replacement connector`, `seal`, and `retainer`
- `as-found leak path` and `bead condition`

- Remaining risks:
- Some final misses still originate upstream: `access panels`, `inlet tube bead`, `burrs`, and `corrosion`
- Structural tails under `tube neck` are still slightly over-expanded relative to gold
- Cross-domain behavior is still unproven, which is exactly what Round 3 needs to check

### Code Quality Audit

- Naming / responsibility:
- The extraction prompt now carries more of the semantic burden it should have carried from the start.
- The filtering layer is still regex-heavy, but the regex additions are aligned to explicit audit findings and backed by tests.

- Redundancy:
- Round 2 removed residual conceptual redundancy from the graph itself: `0` extra concepts remain in the single-document evaluation.
- Graph edges also became much more compact, dropping from `28` to `19` while improving relation F1.

- Artifact cleanliness:
- Round-specific raw extraction, evidence, graph output, and report files remain isolated under `artifacts/optimization_rounds/round_02`
- This keeps the main project workspace from re-inflating while still preserving everything needed for auditability

- Open-source quality judgment:
- Stronger than Round 1 because the pipeline now explains more of its gains through principled semantics rather than narrow denoising alone
- Still needs Round 3 validation before these rules can be considered truly general

### Test Report

- Tests run:
- `pytest tests/test_filtering_rules.py -q`
- `pytest tests/test_preprocessing_om_contract.py tests/test_attachment_logic.py tests/test_graph_assembly.py tests/test_evidence_aggregation.py tests/test_experiments_metrics_and_ablation.py tests/test_reporting_framework.py -q`
- Real run:
- extraction rerun for `BATOM_002` with prompt v2 and `temperature=0.0`
- full `full_llm` pipeline rerun
- metric computation against `battery_BATOM_002.json`

- Failures encountered:
- No new code-level test failures after the Round 2 patches
- One intermediate real run still had too many rescued observation nodes, which directly led to the stricter rescue logic now captured in code

- Regression tests added:
- contextual container rejection
- geometry measurement rescue
- generic replacement component rejection

- Final status:
- All targeted tests passed
- Round 2 single-document run exceeded the round gate on both concept and relation metrics

## 6. Round 3 Detailed Record

### Round Metadata

- Title: Three-Domain Mini Regression
- Scope: BATOM_002, CNCOM_002, EVMAN_002
- Notes: Round 3 exposed a CNC doc?gold alignment mismatch, added cross-domain label canonicalization for contextual prefixes, reused the frozen Round 2 battery evidence, and reran three-domain evaluation with CNC content aligned to CNCOM_002 gold semantics.

### Summary

### Goal

- Check whether the Round 1-2 rules generalize beyond battery.
- Separate true code-logic problems from data-alignment problems.
- Keep the mainline unified across battery, CNC, and NEV without reintroducing fallback behavior or domain-specific side paths.

### Baseline

- Baseline three-domain macro metrics:
- concept F1 `0.5765`
- anchor accuracy `0.9815`
- relation F1 `0.5532`
- The baseline immediately exposed a non-code issue:
- `CNCOM_002` gold was being compared against the wrong markdown file
- Root cause: the current `data/cnc/` filenames and the `cnc_CNCOM_002.json` gold annotation are misaligned by content

### Post-Run Result

- Post three-domain macro metrics:
- concept F1 `0.8183`
- anchor accuracy `0.9800`
- relation F1 `0.6073`
- Main changes behind the recovery:
- reused frozen Round 2 battery evidence to avoid battery regression from extraction noise
- aligned `CNCOM_002` evaluation to the semantically matching markdown content while preserving the `CNCOM_002` evidence id
- added cross-domain contextual-prefix canonicalization such as `vehicle ...`, `nearby ...`, and `adjacent ...`

### Next Focus

- Round 4 should move to all 9 human-gold files with an explicit alignment policy for the swapped CNC filenames.
- The main remaining cross-domain risks are:
- NEV still over-predicts generic leak-boundary nodes
- CNC still misses several side-load and leak-evidence relations
- full-corpus evaluation still needs a reusable mapping for the CNC filename/gold mismatch

### Change Log

#### ISSUE-001

- Problem: the initial Round 3 CNC result was invalid because the markdown source and the frozen gold annotation did not describe the same document
- Root cause: `cnc_CNCOM_002.json` matches the content currently stored in `data/cnc/CNCOM_003.md`, not `data/cnc/CNCOM_002.md`
- Modified area: round staging inputs, `artifacts/optimization_rounds/round_03/data_alignment.json`
- Expected effect: restore a meaningful CNC evaluation instead of debugging a false code regression
- Actual effect: three-domain concept F1 improved from `0.5765` to `0.8183` after the alignment fix
- Status: fixed for the optimization run, to be formalized for Round 4 full-gold execution

#### ISSUE-002

- Problem: cross-domain runs still carried contextual label prefixes such as `vehicle`, `nearby`, and `adjacent` into the final graph
- Root cause: label canonicalization handled aliases but did not normalize obvious contextual prefixes on stable entity names
- Modified area: `preprocessing/processor.py`, `tests/test_preprocessing_om_contract.py`
- Expected effect: improve cross-domain concept matching without introducing domain-specific heuristics
- Actual effect: battery and NEV both benefited from cleaner stable labels
- Status: fixed

#### ISSUE-003

- Problem: battery performance could fluctuate in Round 3 simply because extraction was rerun again, even though Round 2 had already frozen a strong single-document result
- Root cause: repeated LLM extraction adds noise when the round objective is cross-domain compatibility, not battery re-optimization
- Modified area: round execution policy
- Expected effect: use frozen best-known battery evidence while testing new rules on other domains
- Actual effect: battery remained at Round 2 quality inside the three-domain run
- Status: fixed

### Dataflow Audit

#### 1. Raw Input

- Domains evaluated: `battery`, `cnc`, `nev`
- Documents evaluated: `BATOM_002`, `CNCOM_002`, `EVMAN_002`
- Important audit discovery:
- CNC required content alignment because the gold id `CNCOM_002` currently matches the markdown content stored in `CNCOM_003.md`

#### 2. Extraction Output

- Battery reused the frozen Round 2 extraction and evidence
- CNC and NEV used fresh extraction with the updated prompt and `temperature=0.0`
- Cross-domain extraction outcome:
- battery remained stable
- CNC recovered from invalid baseline once content alignment was fixed
- NEV still produced generic leak-boundary labels more often than desired

#### 3. EvidenceRecord

- The same step-aware evidence schema was used for all three domains
- Cross-domain benefit of Round 3:
- contextual-prefix canonicalization now improves label stability before candidate aggregation
- no domain required a separate evidence structure or separate pipeline branch

#### 4. SchemaCandidate

- Post-run per-domain candidate counts:
- battery: `59`
- cnc: `40`
- nev: `69`
- This round confirmed the current mainline is broad enough to handle three domains, but NEV still generates the largest amount of generic candidate clutter

#### 5. Attachment / Filtering

- Post-run per-domain rejected candidate counts:
- battery: `16`
- cnc: `8`
- nev: `8`
- Reject-reason patterns:
- battery mostly `low_graph_value`
- CNC a mix of `low_graph_value` and `observation_like_not_grounded`
- NEV still includes generic leak-boundary concepts that the current filter does not fully collapse

#### 6. Final Graph

- Post-run per-domain edge counts:
- battery: `19`
- cnc: `15`
- nev: `19`
- Edge family distributions show the domains now remain comparable without any battery-only branching, but NEV still has a higher share of communication and propagation noise than the other two domains

#### 7. Metrics

- Three-domain macro concept F1: `0.5765 -> 0.8183`
- Three-domain macro relation F1: `0.5532 -> 0.6073`
- Battery: concept F1 `0.9556`, relation F1 `0.8649`
- CNC: concept F1 `0.7838`, relation F1 `0.5000`
- NEV: concept F1 `0.7156`, relation F1 `0.4571`
- Round 3 verdict:
- the mainline is cross-domain usable
- remaining issues are now specific and diagnosable rather than catastrophic

### Logic Audit

- Main logic issue 1: not every bad metric in a multi-domain run is a code regression.
- Round 3 validated that part of the initial collapse was caused by a source/gold mismatch, so the audit process correctly separated data problems from code problems.

- Main logic issue 2: label stability needed one more cross-domain normalization layer.
- The new prefix normalization is lightweight, domain-agnostic, and improves both battery and NEV without creating a special-case branch.

- Main logic issue 3: execution policy matters for trustworthy iteration.
- Reusing the frozen Round 2 battery evidence prevented unrelated extraction drift from masking the true cross-domain compatibility picture.

- Remaining risks:
- NEV still needs better exact leak-boundary naming
- CNC still under-recovers side-load and leak-evidence semantics
- Round 4 needs an explicit reusable alignment policy for the CNC filename swap before full-gold evaluation can be considered trustworthy

### Code Quality Audit

- Naming / responsibility:
- Cross-domain label cleanup stayed inside preprocessing normalization instead of leaking into domain-specific attachment logic
- Data alignment was handled as staged input metadata, which is the correct layer for it

- Redundancy:
- No new domain-specific branch was introduced to make CNC or NEV work
- The same filtering and graph-assembly logic remained shared across domains

- Artifact cleanliness:
- Round 3 now stores a dedicated `data_alignment.json` so that the alignment fix is explicit rather than hidden in ad hoc shell history

- Open-source quality judgment:
- Stronger than a silent hotfix because the round preserves the evidence of the bad baseline and records the reason for the recovery
- Still incomplete until the alignment policy is lifted into the full-corpus Round 4 execution path

### Test Report

- Tests run:
- `pytest tests/test_preprocessing_om_contract.py -q`
- `pytest tests/test_filtering_rules.py tests/test_attachment_logic.py tests/test_graph_assembly.py tests/test_evidence_aggregation.py tests/test_experiments_metrics_and_ablation.py tests/test_reporting_framework.py -q`
- Real runs:
- initial three-domain baseline with the original selected filenames
- corrected three-domain rerun after CNC content alignment and cross-domain label canonicalization

- Failures encountered:
- No unit-test failures after the Round 3 code changes
- The major runtime failure mode was experimental invalidity from data alignment, not a crashing pipeline

- Regression tests added:
- contextual-prefix stripping for stable labels

- Final status:
- All targeted tests passed
- Three-domain rerun completed successfully after alignment correction

## 7. Round 4 Detailed Record

### Round Metadata

- Title: Full Human-Gold Validation And Ablation
- Scope: BATOM_001, BATOM_002, BATOM_003, CNCOM_001, CNCOM_002, CNCOM_003, EVMAN_001, EVMAN_002, EVMAN_003
- Notes: Round 4 carried the explicit CNC gold-to-markdown alignment into the full 9-document corpus, established the first full human-gold baseline, then tightened runtime label canonicalization plus verification-outcome filtering before rerunning the main variant and the complete ablation matrix.
- Recommended variant: full_llm

### Summary

### Goal

- Run the no-fallback mainline on all 9 human-gold documents with the explicit CNC alignment policy carried forward from Round 3.
- Produce the first paper-facing full-corpus baseline, then fix only mainline logic defects that appear in the real run.
- Execute a complete ablation matrix under the same evaluation protocol so the contribution of each major component can be discussed honestly.

### Baseline

- Baseline run root: `round04_full_gold-20260419T194710Z`
- Baseline concept metrics: precision `0.7026`, recall `0.6414`, F1 `0.6559`
- Baseline anchor metrics: accuracy `0.9347`, macro-F1 `0.8454`
- Baseline relation metrics: precision `0.4530`, recall `0.5120`, F1 `0.4701`
- Baseline graph size: `425` predicted concepts and `195` predicted relations against `460` gold concepts and `166` gold relations
- Main baseline findings:
- `BATOM_001` is annotation-misaligned because the staged markdown has `8` steps while the current gold annotates only `6`
- label variation such as `... stable`, `orange handle sits proud`, and `service-disconnect` vs `service disconnect` still inflated mismatch against human gold
- post-repair verification outcomes and placeholders were still entering the graph as if they were reusable domain concepts

### Post-Run Result

- Post run root: `round04_full_gold-20260419T203835Z`
- Post concept metrics: precision `0.7398`, recall `0.6577`, F1 `0.6818`
- Post anchor metrics: accuracy `0.9410`, macro-F1 `0.8412`
- Post relation metrics: precision `0.4978`, recall `0.5342`, F1 `0.5049`
- Predicted graph size dropped to `415` concepts and `179` relations, which means the metric gains came from reducing mismatch rather than expanding the graph
- Strongest per-file improvement: `nev_EVMAN_003.json` improved from concept F1 `0.7200 -> 0.8817` and relation F1 `0.3158 -> 0.5532`
- Round 4 gate result: passed
- Full ablation completed after the post-fix rerun

### Next Focus

- Freeze the best configuration and replay the full 9-document run at least twice to measure stability instead of assuming determinism.
- Report the Round 4 ablation conservatively:
- `no_rule_filter` is the clearly harmful ablation
- memory-bank and LLM-attachment gains are present but marginal on this small corpus
- Keep `BATOM_001` annotation mismatch explicitly listed as an evaluation risk rather than hiding it in evaluator logic.

### Change Log

#### ISSUE-001

- Problem: human-gold matching was still losing precision because runtime labels preserved unstable surface variants such as `HVIL path stable`, `ready-state permissive stable`, and `orange handle sits proud`
- Root cause: preprocessing emitted valid concepts, but evidence loading and aggregation still treated several common surface variants as separate labels instead of paper-level canonical forms
- Modified area: `pipeline/evidence.py`, `tests/test_evidence_aggregation.py`
- Expected effect: improve alignment between extracted labels and frozen human-gold concepts without changing the no-fallback mainline
- Actual effect: concept F1 improved from `0.6559` to `0.6818`, and the full-corpus prediction count dropped from `425` to `415`
- Status: fixed

#### ISSUE-002

- Problem: post-repair verification outcomes and generic placeholders were still entering the candidate set and surviving too deep into the graph pipeline
- Root cause: rule filtering did not explicitly reject several acceptance-fragment and placeholder patterns that are useful for narrative evidence but low-value as reusable graph nodes
- Modified area: `rules/filtering.py`, `tests/test_filtering_rules.py`
- Expected effect: prevent proof-of-fix observations from polluting paper-facing graph metrics while preserving real fault / component / signal content
- Actual effect: relation precision improved from `0.4530` to `0.4978`, and rejected candidates became more concentrated in `low_graph_value` instead of noisy late-stage mismatches
- Status: fixed

#### ISSUE-003

- Problem: observation-like labels with strong fault semantics were still too easy to anchor as `Signal`
- Root cause: preferred-anchor heuristics did not sufficiently distinguish geometry / seating observations from fault-like deformation or misalignment language
- Modified area: `rules/filtering.py`
- Expected effect: better `Signal` vs `Fault` routing for labels such as `flush`, `proud`, `off-axis`, `bow`, and `short-stroke`
- Actual effect: anchor accuracy improved from `0.9347` to `0.9410`, and several NEV labels aligned better to gold after rerun
- Status: fixed

#### ISSUE-004

- Problem: full-corpus runs and ablations were reproducible in practice, but the project lacked a clean round-level execution and reporting framework
- Root cause: preparation, evaluation, baseline/post diffs, and round manifests were still scattered across ad-hoc commands and working outputs
- Modified area: `experiments/rounds.py`, `experiments/metrics/core.py`, `experiments/metrics/evaluate.py`, `scripts/prepare_round_run.py`, `scripts/evaluate_variant_run.py`, `tests/test_round_preparation.py`, `tests/test_experiments_metrics_and_ablation.py`
- Expected effect: make Round 4 and later rounds auditable, reproducible, and paper-ready without introducing side paths
- Actual effect: Round 4 now has dedicated configs, manifests, metrics diffs, audit snapshots, and ablation reports under a single round root
- Status: fixed

### Dataflow Audit

#### 1. Raw Input

- Input document count: `9`
- Input scope:
- battery: `BATOM_001`, `BATOM_002`, `BATOM_003`
- cnc: `CNCOM_001`, `CNCOM_002`, `CNCOM_003`
- nev: `EVMAN_001`, `EVMAN_002`, `EVMAN_003`
- Critical input policy:
- the CNC markdown / gold mismatch discovered in Round 3 was preserved as an explicit alignment artifact rather than hidden behind raw filenames
- Main anomaly discovered from raw input review:
- `BATOM_001` staged markdown has `8` steps, but `battery_BATOM_001.json` currently annotates only `6`

#### 2. Extraction Output

- Full preprocessing completed successfully on all `9` documents
- Round-scoped evidence output root: `artifacts/optimization_rounds/round_04/evidence_records/`
- Upstream extraction was good enough to scale, but still showed recurring surface variation and verification-only fragments that later needed runtime normalization and filtering
- Persistent upstream weakness after the post-fix rerun:
- structural locus specificity is still weak for front-manifold and quick-coupler boundary concepts

#### 3. EvidenceRecord

- Evidence unit count: `9`
- Evidence loading now performs runtime canonicalization for the specific high-impact variants found in the Round 4 baseline
- Important examples:
- strip `stable` suffixes from labels like `HVIL path stable` and `ready-state permissive stable`
- normalize `service-disconnect` to `service disconnect`
- normalize handle-seating observations to `handle proud` / `handle flushness`
- Resulting effect:
- fewer label mismatches reached candidate aggregation, especially in NEV

#### 4. SchemaCandidate

- Post-rerun candidate counts by domain:
- battery: `191`
- cnc: `127`
- nev: `137`
- Post-rerun accepted adapter candidates by domain:
- battery: `148`
- cnc: `114`
- nev: `109`
- Candidate volume stayed broad enough for full-corpus coverage; the improvement came from candidate quality and label consistency rather than aggressive pruning upstream

#### 5. Attachment / Filtering

- Post-rerun reject reason distribution:
- battery: `low_graph_value=29`, `weak_relation_support=6`, `observation_like_not_grounded=8`
- cnc: `low_graph_value=13`
- nev: `low_graph_value=24`, `observation_like_not_grounded=4`
- The most useful downstream change was not a routing rewrite but cleaner rejection of verification-outcome fragments and generic placeholders
- Attachment still remains the main stochastic layer, but Round 4 showed that filtering is the strongest reliable contributor in the current 9-document setting

#### 6. Final Graph

- Post-rerun graph counts by domain:
- battery: `148` nodes, `58` edges
- cnc: `114` nodes, `67` edges
- nev: `109` nodes, `50` edges
- Total post-rerun graph size: `371` nodes and `175` edges across domain graphs
- Compared with baseline:
- predicted concepts dropped from `425 -> 415`
- predicted relations dropped from `195 -> 179`
- Final graphs are still denser than the single-document rounds, but materially cleaner than the Round 4 baseline

#### 7. Metrics

- Full-corpus macro metrics:
- concept F1 `0.6559 -> 0.6818`
- anchor accuracy `0.9347 -> 0.9410`
- relation F1 `0.4701 -> 0.5049`
- Strongest per-file recovery:
- `nev_EVMAN_003.json`: concept F1 `0.7200 -> 0.8817`, relation F1 `0.3158 -> 0.5532`
- Stable or negative cases that still matter:
- `battery_BATOM_001.json` stayed poor because of annotation mismatch, not because the rerun broke
- `battery_BATOM_003.json` still misses several highly specific structural concepts and one relation family remains slightly worse after cleanup

### Logic Audit

- Main logic issue 1: full-corpus evaluation was being distorted by label-surface variation, not just by missing concepts.
- Resolution: runtime evidence normalization now collapses only the concrete high-impact variants seen in the real run instead of adding a generic fallback canonicalizer.

- Main logic issue 2: proof-of-fix observations were still competing with reusable domain concepts.
- Resolution: rule filtering now rejects verification-outcome fragments and placeholders earlier, which keeps explainability evidence available in records without forcing it into the final graph.

- Main logic issue 3: the execution path itself needed to become auditable.
- Resolution: Round 4 introduced explicit round preparation, run manifests, baseline/post metric capture, metrics diffs, and standalone evaluation helpers under `experiments/` and `scripts/`.

- Edge cases checked this round:
- `service-disconnect status stable`
- `HVIL path stable`
- `orange handle sits proud`
- placeholder / acceptance-style fragments after repair verification

- Remaining risks:
- `BATOM_001` is still a real human-gold mismatch and should be fixed in the annotation, not masked in evaluation code.
- Structural specificity is still weaker than gold for `front manifold face`, quick-coupler boundary concepts, and similar fine-grained locus labels.
- The ablation shows only marginal separation between `full_llm`, embedding-only, and deterministic routing on this corpus, so any paper claim about LLM attachment must stay modest.

### Code Quality Audit

- Naming / responsibility:
- runtime evidence normalization now lives in `pipeline/evidence.py`, which is a better ownership boundary than scattering label-repair logic across unrelated downstream modules
- round execution and evaluation concerns are now grouped under `experiments/` and `scripts/` instead of being embedded in one-off notebook-style commands

- Redundancy:
- Round 4 reduced output redundancy by centralizing baseline metrics, post metrics, metrics diffs, audit snapshots, and ablation artifacts under a single round directory
- the reporting framework now consumes those stable files directly instead of needing extra ad-hoc parsing logic

- Artifact cleanliness:
- the main evidence, configs, input alignment, output runs, and reports are isolated under `artifacts/optimization_rounds/round_04/`
- this is much cleaner than letting the generic `working/` path become the primary inspection surface for experiments

- Open-source quality judgment:
- Positive: the round is reproducible from saved configs and manifests, the no-fallback rule stayed intact, and the paper-facing evaluation path is now explicit
- Still improvable: some domain specificity is still encoded as targeted normalization rather than a cleaner typed canonicalization layer, and attachment reproducibility remains bounded by LLM variance

### Test Report

- Tests run:
- `pytest tests/test_round_preparation.py -q`
- `pytest tests/test_experiments_metrics_and_ablation.py -q`
- `pytest tests/test_reporting_framework.py -q`
- `pytest tests/test_filtering_rules.py -q`
- `pytest tests/test_evidence_aggregation.py -q`
- `pytest tests/test_attachment_logic.py tests/test_graph_assembly.py tests/test_experiments_metrics_and_ablation.py -q`
- Real runs:
- round preparation for the full 9-document corpus
- full preprocessing on all `9` documents
- baseline `full_llm` evaluation
- post-fix `full_llm` rerun
- complete ablation matrix

- Failures encountered:
- no post-fix test failures remained
- the most important runtime issue discovered by the baseline was the `BATOM_001` annotation mismatch, which is a gold problem rather than a code regression

- Regression tests added or updated:
- dedicated round-preparation coverage
- metrics and ablation aggregation coverage
- evidence aggregation normalization coverage
- filtering regressions for verification-outcome and placeholder rejection

- Final status:
- all targeted suites passed
- Round 4 full human-gold rerun passed
- Round 4 ablation completed and artifacts were frozen under the round directory

## 8. Round 5 Detailed Record

### Round Metadata

- Title: Final Freeze And Stability Replay
- Scope: BATOM_001, BATOM_002, BATOM_003, CNCOM_001, CNCOM_002, CNCOM_003, EVMAN_001, EVMAN_002, EVMAN_003
- Notes: Round 5 restaged all 9 aligned documents under the frozen full_llm configuration, reran preprocessing from scratch, then executed two full pipeline replays to measure stability. Relation quality stayed effectively unchanged across the two runs while concept counts drifted modestly, exposing residual LLM attachment variance without breaking the mainline graph behavior.
- Recommended variant: full_llm

### Summary

### Goal

- Freeze the best Round 4 configuration under a clean round root and rerun the entire 9-document pipeline from fresh preprocessing.
- Measure replay stability with at least two full `full_llm` runs instead of assuming repeatability from a single result.
- Package the final architecture, artifacts, and reporting outputs so the project can be presented as one coherent paper system.

### Baseline

- Baseline run root: `round05_final-20260419T233745Z`
- Baseline concept metrics: precision `0.7500`, recall `0.6903`, F1 `0.7070`
- Baseline anchor metrics: accuracy `0.9539`, macro-F1 `0.8372`
- Baseline relation metrics: precision `0.5535`, recall `0.5187`, F1 `0.5222`
- Baseline graph size: `419` predicted concepts and `152` predicted relations
- Baseline audit signal:
- the frozen configuration was already stronger than Round 4 post-run
- candidate counts and edge counts looked stable enough to support a replay-based stability audit

### Post-Run Result

- Post run root: `round05_final-20260419T235812Z`
- Post concept metrics: precision `0.7571`, recall `0.7163`, F1 `0.7253`
- Post anchor metrics: accuracy `0.9530`, macro-F1 `0.8375`
- Post relation metrics: precision `0.5542`, recall `0.5187`, F1 `0.5218`
- Stability diff:
- concept F1 `+0.0183`
- anchor accuracy `-0.0009`
- relation F1 `-0.0004`
- Candidate counts stayed fixed by domain, edge counts stayed fixed by domain, and the only meaningful drift was modest node-count variation from LLM attachment decisions
- Round 5 gate result: passed

### Next Focus

- Treat the Round 5 configuration and artifact layout as frozen unless new human-gold annotations require a real methodological change.
- Before paper submission, fix the annotation mismatch in `BATOM_001` and decide whether to enlarge the corpus or repeated-run sampling if stronger claims about LLM attachment or memory-bank benefit are needed.

### Change Log

#### ISSUE-001

- Problem: the project still needed a freeze-grade full-corpus replay rooted in one explicit configuration snapshot
- Root cause: Round 4 proved the method, but it did not yet provide a dedicated final-freeze replay pass with fresh preprocessing and repeated evaluation
- Modified area: `artifacts/optimization_rounds/round_05/configs/`, round-preparation inputs, final run manifests
- Expected effect: make the final result reproducible from one frozen config set and one aligned 9-document scope
- Actual effect: Round 5 reran preprocessing from scratch and produced two complete `full_llm` runs under the frozen configuration
- Status: fixed

#### ISSUE-002

- Problem: the pipeline still needed an explicit stability check to separate real logic errors from ordinary LLM variance
- Root cause: a single good run can hide whether variation comes from candidate generation, filtering, or attachment randomness
- Modified area: Round 5 replay protocol, audit snapshots, `baseline_metrics.json`, `post_metrics.json`, `metrics_diff.json`
- Expected effect: show exactly which parts of the dataflow remain stable across repeats
- Actual effect: candidate counts stayed constant, edge counts stayed constant, and only accepted node counts drifted modestly across domains
- Status: fixed

#### ISSUE-003

- Problem: the round artifacts still needed to be compiled into a paper-ready reporting surface
- Root cause: even after the main runs were frozen, the project still lacked final Round 5 docs and a fixed-structure five-round summary report
- Modified area: `experiments/reporting.py`, `tests/test_reporting_framework.py`, `docs/ROUND_05.md`, `docs/FIVE_ROUND_OPTIMIZATION_REPORT.md`
- Expected effect: one final reporting path that reflects the actual run manifests and round artifacts instead of scattered notes
- Actual effect: the five-round compiler now emits the required fixed structure and Round 5 is documented as the final freeze pass
- Status: fixed

### Dataflow Audit

#### 1. Raw Input

- Input document count: `9`
- Input policy:
- reuse the aligned 9-document scope from Round 4
- rerun from fresh preprocessing rather than recycling old working outputs
- keep the no-fallback path unchanged
- Raw input stability conclusion:
- the scope and alignment were frozen correctly; the remaining variation in Round 5 is not due to input drift

#### 2. Extraction Output

- Full preprocessing succeeded again on all `9` documents
- Evidence outputs were written to `artifacts/optimization_rounds/round_05/evidence_records/`
- Because Round 5 restaged the corpus from scratch, extraction success confirms that the frozen configuration is runnable end to end and not dependent on leftover Round 4 state

#### 3. EvidenceRecord

- Evidence unit count: `9`
- Evidence record format stayed domain-split and round-scoped
- Round 5 did not add new fallback fields or sidecar caches; it reused the Round 4 mainline design and tested it under replay
- Evidence-level conclusion:
- the replay variance seen later is downstream of evidence generation, not a sign that evidence serialization is unstable

#### 4. SchemaCandidate

- Candidate counts were identical across the two replays:
- battery: `166 -> 166`
- cnc: `143 -> 143`
- nev: `142 -> 142`
- This is one of the most important Round 5 findings because it shows the replay variance is not coming from candidate creation volume

#### 5. Attachment / Filtering

- Reject reason distributions changed only modestly between the two runs:
- battery: `33` rejects -> `30` rejects
- cnc: `27` rejects -> `20` rejects
- nev: `25` rejects -> `22` rejects
- Dominant reject reasons stayed the same:
- `low_graph_value`
- `observation_like_not_grounded`
- small `weak_relation_support` tail in battery and CNC
- Interpretation:
- filtering behavior is directionally stable, but attachment decisions still move some borderline concepts across the accepted / rejected boundary

#### 6. Final Graph

- Domain graph totals were stable in edges and slightly variable in nodes:
- battery: nodes `133 -> 136`, edges `43 -> 43`
- cnc: nodes `116 -> 123`, edges `56 -> 56`
- nev: nodes `117 -> 120`, edges `47 -> 47`
- Total graph drift:
- run 1: `366` nodes, `146` edges
- run 2: `379` nodes, `146` edges
- Final-graph conclusion:
- relation structure is effectively frozen, while concept admission still shows small stochastic movement

#### 7. Metrics

- Replay metric diff:
- concept F1 `0.7070 -> 0.7253`
- anchor accuracy `0.9539 -> 0.9530`
- relation F1 `0.5222 -> 0.5218`
- This is stable enough to trust the main relation behavior, but not stable enough to claim exact deterministic concept sets
- Persistent problem documents:
- `battery_BATOM_001.json` remains constrained by annotation mismatch
- several documents still miss the most specific structural locus labels expected by gold

### Logic Audit

- Main logic issue 1: the final system still needed proof that replay variance was not coming from hidden branches or fallback behavior.
- Resolution: Round 5 reran the exact frozen mainline twice from fresh preprocessing and confirmed that candidate counts and edge counts stay fixed.

- Main logic issue 2: the remaining nondeterminism needed to be localized precisely.
- Resolution: Round 5 audit shows that the main moving part is accepted node count after attachment / filtering, not upstream extraction volume or final edge structure.

- Main logic issue 3: the final report path needed to reflect the real run artifacts instead of a manually curated summary only.
- Resolution: the reporting layer now compiles the five-round report directly from round manifests, metrics, audits, and markdown records.

- Edge cases checked this round:
- repeated `full_llm` replay on the same aligned scope
- domain-level node / edge stability
- reject-reason stability between runs

- Remaining risks:
- `BATOM_001` gold mismatch is still unresolved and remains the highest evaluation-integrity risk.
- LLM attachment still introduces modest node-count variation, so the final paper should not describe the system as deterministic.
- Structural specificity remains the main semantic gap against human gold in battery and some CNC / NEV boundary concepts.

### Code Quality Audit

- Naming / responsibility:
- Round 5 keeps the architecture honest by treating replay stability, reporting, and artifact freeze as first-class deliverables rather than implicit side effects
- the final-report compiler now belongs in `experiments/reporting.py`, which is a clearer ownership boundary than scattering summary logic across docs or shell history

- Redundancy:
- the round-based artifact layout prevents the generic `working/` directory from becoming the permanent store for experiment evidence
- final freeze evaluation reuses the same config and report contract instead of introducing a separate final-only code path

- Artifact cleanliness:
- `artifacts/optimization_rounds/round_05/` now contains the full final-freeze evidence: prepared inputs, configs, evidence records, two run roots, metrics, audits, and docs
- this is the right level of packaging for a top-tier open-source research repository because the evidence for claims is inspectable in one place

- Open-source quality judgment:
- Positive: mainline remains explicit, there is no fallback logic, and final outputs are reproducible from saved artifacts and commands
- Still improvable: attachment determinism is not fully solved, and some structural normalization still relies on targeted domain observations instead of a more general typed representation

### Test Report

- Tests run:
- full Round 5 preprocessing on all `9` documents
- first frozen `full_llm` replay plus evaluation
- second frozen `full_llm` replay plus evaluation
- reporting-layer regression tests after final compiler updates

- Failures encountered:
- no replay-blocking runtime failures occurred
- the only meaningful instability observed was expected LLM attachment variance in accepted node counts

- Regression tests added or updated:
- final reporting-framework expectations for the fixed 15-section five-round report
- round-level documentation and manifest integration through the compiled report path

- Final status:
- Round 5 final freeze replay passed
- stability audit completed
- final reporting path is wired to real round artifacts rather than placeholder templates

## 9. Five-Round Metrics Change Table

| Round | Concept F1 | Anchor Acc | Anchor Macro-F1 | Relation F1 |
|---|---:|---:|---:|---:|
| Round 1 | 0.8696 | 1.0000 | 1.0000 | 0.6957 |
| Round 2 | 0.9556 | 1.0000 | 1.0000 | 0.8649 |
| Round 3 | 0.8183 | 0.9800 | 0.9147 | 0.6073 |
| Round 4 | 0.6818 | 0.9410 | 0.8412 | 0.5049 |
| Round 5 | 0.7253 | 0.9530 | 0.8375 | 0.5218 |

## 10. Five-Round Dataflow Change Table

| Round | Input Scope | Dataflow Change |
|---|---|---|
| Round 1 | BATOM_002 | Kept the single-document extraction scope fixed, rewrote contextual structural heads into stable parents, and reduced the final graph from 52/37 to 45/28 nodes/edges without adding fallback logic. |
| Round 2 | BATOM_002 | Tightened upstream extraction semantics and downstream candidate admission so BATOM_002 removed generic extras and kept only 43 concepts / 19 relations in the final graph. |
| Round 3 | BATOM_002, CNCOM_002, EVMAN_002 | Introduced explicit CNC content-to-gold alignment so the three-domain regression could be evaluated on semantically matching staged inputs instead of misleading raw filenames. |
| Round 4 | BATOM_001, BATOM_002, BATOM_003, CNCOM_001, CNCOM_002, CNCOM_003, EVMAN_001, EVMAN_002, EVMAN_003 | Scaled the runbook to all 9 gold files, preserved the CNC alignment map, normalized label variants at evidence load time, and reduced full-corpus predictions from 425/195 to 415/179 concepts/relations. Post-audit totals were 455 candidates, 371 nodes, and 175 edges. |
| Round 5 | BATOM_001, BATOM_002, BATOM_003, CNCOM_001, CNCOM_002, CNCOM_003, EVMAN_001, EVMAN_002, EVMAN_003 | Restaged the same 9 aligned documents, reran preprocessing from scratch, and replayed the frozen full_llm variant twice; candidate counts stayed fixed while node counts drifted modestly and edges stayed constant. Run 1 totals were 451 candidates / 366 nodes / 146 edges; run 2 totals were 451 candidates / 379 nodes / 146 edges. |

## 11. Five-Round Code Logic And Architecture Change Table

| Round | Logic / Architecture Change | Code Paths | Effect |
|---|---|---|---|
| Round 1 | Separated semantic-safe alias handling from graph filtering so structural cleanup happened in the mainline EvidenceRecord -> candidate -> graph path. | preprocessing/processor.py; rules/filtering.py; preprocessing contract tests | Relation denoising and structural contraction on BATOM_002 |
| Round 2 | Aligned prompt-level concept typing with filtering-time anchor rescue, eliminating the earlier split between semantic hints and final anchor decisions. | config/prompts/preprocessing_extraction_om.txt; rules/filtering.py; semantic regression tests | Semantic boundary refinement for Signal / Fault / State |
| Round 3 | Moved cross-domain correctness from implicit filename assumptions into explicit round-preparation artifacts, keeping the core pipeline shared across battery, CNC, and NEV. | round staging / alignment inputs; shared canonicalization path; multi-domain evaluation flow | Three-domain mini-regression and alignment repair |
| Round 4 | Made round execution reproducible with dedicated configs, manifests, metrics diffs, and ablation outputs under artifacts/optimization_rounds/round_04 instead of ad-hoc working-directory state. | pipeline/evidence.py; rules/filtering.py; experiments/metrics/core.py; experiments/metrics/evaluate.py; experiments/rounds.py; scripts/prepare_round_run.py; scripts/evaluate_variant_run.py | Full 9-document human-gold validation and ablation |
| Round 5 | Froze the recommended configuration and artifact structure under round_05, exposing the remaining source of nondeterminism as LLM attachment variance rather than hidden branch logic or fallback behavior. | round freeze configs; reporting / packaging path; final artifact layout | Frozen full-corpus replay and stability audit |

## 12. Ablation Study Conclusion

| Variant | Concept F1 | Anchor Acc | Anchor Macro-F1 | Relation F1 | Predicted Concepts | Predicted Relations |
|---|---:|---:|---:|---:|---:|---:|
| full_llm | 0.6881 | 0.9412 | 0.8412 | 0.5049 | 416 | 179 |
| no_memory_bank | 0.6795 | 0.9431 | 0.8416 | 0.5057 | 408 | 179 |
| no_rule_filter | 0.6683 | 0.9102 | 0.8071 | 0.4673 | 463 | 204 |
| no_embedding_routing | 0.6919 | 0.9417 | 0.8415 | 0.5043 | 419 | 180 |
| embedding_top1 | 0.6904 | 0.9404 | 0.8405 | 0.5043 | 451 | 180 |
| deterministic | 0.6904 | 0.9404 | 0.8405 | 0.5043 | 451 | 180 |

- `no_rule_filter` is the only ablation that clearly degrades all major metrics at once, so rule filtering is the strongest demonstrated contributor on the 9-document human-gold set.
- `no_memory_bank` is slightly worse on concept F1 but effectively tied on relation F1, which means the current corpus is too small to claim a strong memory-bank advantage.
- `no_embedding_routing`, `embedding_top1`, and `deterministic` stay very close to `full_llm`, so LLM attachment should be described as marginally helpful rather than decisively superior on the current benchmark.
- These results support the pipeline as a whole, but they do not support an aggressive claim that the LLM attachment component is the main source of gains.

## 13. Final Frozen Architecture

- Frozen mainline: staged markdown -> preprocessing extraction -> step-scoped EvidenceRecord -> SchemaCandidate aggregation -> attachment/routing -> rule filtering -> final graph -> human-gold metrics and ablation.
- Evidence records stay domain-split under round-scoped artifact roots, and the pipeline does not fall back to alternate paths when extraction or attachment is weak.
- Evaluation is driven only by human gold for paper-facing metrics; silver or auto-generated artifacts remain diagnostic only.
- Round preparation, run manifests, baseline/post metrics, metrics diff files, audit snapshots, and ablation outputs now live under `artifacts/optimization_rounds/round_xx/`, which keeps `working/` from becoming the primary evidence source.

## 14. Current Remaining Risks

| Round | Open / Closed Status | Evidence |
|---|---|---|
| Round 1 | completed: Alias over-collapse and structural over-expansion closed; semantic boundary errors carried into Round 2. | Still missing access panels / operating state / geometry signals; T3 signal-to-fault communication edges remain noisy and need Round 2 semantic boundary cleanup. |
| Round 2 | completed: Battery single-doc semantic boundary largely closed; cross-domain robustness moved to Round 3. | Still missing access panels, inlet tube bead, burrs, corrosion, plus one propagation edge and one fresh-wetting communication edge. Ready for cross-domain Round 3 validation. |
| Round 3 | completed: CNC alignment failure closed; NEV/CNC domain misses remained open for Round 4 full-gold validation. | NEV still over-predicts generic leak-boundary concepts; CNC still misses several leak-evidence signals and side-load relations. These become the main targets for Round 4 full-gold validation. |
| Round 4 | completed: Full-gold execution and ablation closed; BATOM_001 annotation mismatch and weak structural specificity remained open. | BATOM_001 gold still annotates only 6 of the 8 staged steps; structural specificity is still weak for front-manifold and quick-coupler boundary concepts; LLM attachment advantage over deterministic routing remains marginal on this 9-document set. |
| Round 5 | completed: Final freeze and repeatability audit closed; residual attachment variance and BATOM_001 gold risk remain open. | BATOM_001 annotation mismatch persists; concept counts still vary between repeated full_llm runs because attachment decisions are not perfectly deterministic; several domains still miss the most specific structural locus labels expected by gold. |

- The most serious remaining risk is still BATOM_001 annotation mismatch. This should be fixed in the gold, not hidden in the evaluator.
- Structural specificity is still incomplete for several gold concepts such as front-manifold and quick-coupler boundary labels.
- Repeated `full_llm` runs still show modest concept-count drift, so the final paper should describe stability honestly and avoid claiming strict determinism.

## 15. Next Recommendations

- Repair BATOM_001 human gold so every staged step is represented before using the corpus as a final paper benchmark.
- Expand human-gold coverage or repeated-run sampling if the paper wants to claim stronger evidence for memory-bank or LLM-attachment benefits.
- Continue tightening structural locus labeling so concepts such as manifold face, quick connector, outlet boundary, and clamp stack map to the same specificity as gold.
- Keep new experiment or paper tables routed through the round-manifest / metrics-diff / ablation-report path instead of adding new ad-hoc scripts or output folders.
