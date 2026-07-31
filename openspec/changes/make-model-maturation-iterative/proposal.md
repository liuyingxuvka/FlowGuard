## Why

FlowGuard already has a kernel-owned `model_maturation_loop`, but it is primarily a one-shot diagnostic: it can return an action list or allow a scoped claim without proving that addressable actions were executed and rechecked. This lets a first model stop before its task-relevant behavior, predictions, counterexamples, and code boundaries are closed.

## What Changes

- **BREAKING** Make maturation actions for in-scope model/evidence gaps required continuation work, not optional recommendations.
- Add task purpose, independent coverage-universe, model fingerprint, iteration, candidate, and terminal-reason fields to the existing maturation records.
- Add explicit terminal states for task closure, external input, justified scope exclusion, stalled progress, and safety-limit blocking.
- Add a read-only CLI review of a persisted maturation session.
- Update FlowGuard prompts and native tests so self-reported understanding, a prose TODO, or a matching single prediction cannot close a non-trivial task.

## Capabilities

### New Capabilities
- None. This change extends the existing kernel-owned maturation capability.

### Modified Capabilities
- `model-maturation-loop`: require iterative action, revalidation, progress, and explicit terminal reasons.

## Impact

- `flowguard/model_maturation.py`, `flowguard/__main__.py`, model-maturation tests, FlowGuard model/evidence protocol references, and affected satellite prompts.
- No new Guard, central learner, online core-rule mutation, compatibility reader, or cross-Guard receipt authority.
