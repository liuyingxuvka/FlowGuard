## Why

FlowGuard already requires parent coverage, child disjointness, child
reattachment, leaf boundary evidence, same-class model-miss evidence, and final
risk-ledger consumption, but callers can still feed those routes with
self-declared `passed`/`current` fields. Recurring misses can therefore pass a
coverage map or child-path check without proving that the old route is
unreachable, repaired, or freshly verified.

## What Changes

- Add a proof-artifact reference contract for evidence consumed by layered
  boundary proof, recurring defect-family gates, risk evidence ledger,
  model-test alignment, and development-process evidence.
- Add strict evidence binding checks that reject passed/current claims when
  there is no current proof artifact, exit/result evidence, command identity,
  or artifact fingerprint metadata.
- Add legacy-path disposition for parent/child model miss closure so a repaired
  child path is not enough when an old path can still be reached.
- Change helper defaults that can imply success without proof toward
  `not_run` or strict-mode blockers.
- Update FlowGuard skills, docs, templates, and tests so agents treat matrices
  as obligation maps and proof artifacts as the only source of closure status.
- Preserve backward compatibility for routine non-strict helper construction,
  but make strict closure the documented and tested path for full confidence.

## Capabilities

### New Capabilities

- `proof-artifact-bound-evidence`: FlowGuard evidence consumers require
  artifact-backed proof before full confidence.
- `legacy-path-disposition`: Model-miss closure must prove old paths are
  deleted, blocked, delegated, or repaired to the same contract.

### Modified Capabilities

- `layered-boundary-proof`: Parent confidence requires strict proof artifact
  binding for child evidence, reattachment, and leaf boundary cells.
- `risk-evidence-ledger`: Final full-confidence rows reject declaration-only
  proof evidence.
- `model-miss-test-evidence-closure`: Recurring or high-risk misses require
  artifact-backed same-class and defect-family proof.
- `development-process-flow`: Done/release evidence freshness can consume
  proof artifact metadata instead of relying on caller-set flags.

## Impact

- Core package modules: `flowguard/proof_artifact.py`,
  `flowguard/layered_proof.py`, `flowguard/risk_evidence_ledger.py`,
  `flowguard/recurring_model_miss.py`, `flowguard/model_test_alignment.py`,
  `flowguard/development_process_flow.py`, and public exports.
- Tests for layered proof, risk ledger, recurring model misses,
  model-test alignment, and development process flow.
- Skill files under `.agents/skills/` and installed user skills under
  `$CODEX_HOME/skills` after synchronization.
- FlowPilot known-friction and confidence-gate adoption paths that currently
  use static `passed/current` rows.
