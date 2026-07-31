## 1. OpenSpec and contract

- [x] 1.1 Extend the existing `model-maturation-loop` spec with iterative closure requirements.
- [x] 1.2 Add current-schema signal resolution classes, coverage identity, and terminal-reason definitions.

## 2. Runtime owner

- [x] 2.1 Extend `ModelMaturationSignal`, `ModelMaturationPlan`, and `ModelMaturationReport` with task, coverage, resolution, and fingerprint fields.
- [x] 2.2 Add immutable `ModelMaturationIteration`/session serialization in `flowguard/model_maturation.py`.
- [x] 2.3 Change `review_model_maturation_loop()` so addressable gaps cannot be scoped away and empty shallow plans cannot pass.
- [x] 2.4 Add progress-stall, iteration-limit, external-blocker, and task-closure decisions.
- [x] 2.5 Add `model-maturation-review` to the existing FlowGuard CLI.

## 3. Prompts and tests

- [x] 3.1 Update the primary and affected satellite FlowGuard protocol prompts with the iterative rule and no-self-report rule.
- [x] 3.2 Add known-bad tests for shallow first models, prose-only recommendations, scope evasion, stale receipts, and no progress.
- [x] 3.3 Add known-good tests for candidate progress, new-gap continuation, exact external blockers, and task closure.

## 4. Verification and local projection

- [x] 4.1 Run affected FlowGuard unit/model checks and inspect counterexamples.
- [x] 4.2 Regenerate the maintained FlowGuard skill projection and verify source/install parity.
- [x] 4.3 Record local completion evidence and leave GitHub push/release untouched.
