# Round 06

## Scope

- Document: `BATOM_002`
- Objective: validate the new relation-repair logic on a real single-document end-to-end run
- Variant: `full_llm`

## What Changed

- Added stricter structural stable-head handling so contextual structural heads do not survive into the final graph.
- Added immediate-fault target repair for local-damage `indicates` relations such as `stress whitening -> cracked shell`.
- Re-ran preprocessing, pipeline construction, audit export, and human-gold evaluation on the staged `BATOM_002` input only.

## Outcome

- The targeted communication fixes were present in the exported graph:
- `stress whitening -> cracked shell`
- `latch-window distortion -> broken latch ear`
- `witness marks -> bracket side load`
- Structural edge semantics improved from the earlier `tube neck contains ...` pattern to `chiller-inlet connector contains ...`.
- However, overall BATOM_002 metrics did not improve over the Round 02 single-document reference.

## Metrics

- Baseline reference: `artifacts/optimization_rounds/round_02/post_metrics.json`
- Round 06 post metrics:
- concept F1 `0.9032`
- concept-label F1 `0.9462`
- anchor accuracy `0.9545`
- relation precision `0.7619`
- relation recall `0.8889`
- relation F1 `0.8205`

## Main Finding

- The new logic fixed the exact relation forms it was designed to fix, but BATOM_002 still over-generated several connector-level structural edges and two lifecycle transitions.
- This means Round 06 improved relation semantics locally, but did not yet improve the overall graph admission policy enough to raise aggregate precision.

## Next Step

- Tighten connector-level structural promotion.
- Stop over-promoting lifecycle transitions such as `dry -> fully latched -> naturally supported`.
- Revisit `Signal` versus `State` treatment for observation-style labels such as `operating state`.
