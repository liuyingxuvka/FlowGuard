## 1. Contract Asset

- [x] Add `assets/guard_closure_contract.py`.
- [x] Update model-first skill guidance to require child Guard reports.

## 2. Validation

- [x] Run the contract checker on at least one passing and one non-passing sample report.
- [x] Run FlowGuard project audit after edits.

## 3. Sync

- [x] Sync installed `model-first-function-flow` skill from source.
- [x] Record verification evidence and remaining gaps.

## Verification Evidence

- `python -m pytest tests -q`: passed, 754 tests and 137 subtests.
- Guard closure contract samples: valid passed/blocked reports accepted; invalid passed report rejected.
- `python .flowguard/guard_closure_contract/run_checks.py`: passed.
- `python -m flowguard project-audit --root .`: passed with FlowGuard 0.40.12.
- Installed skill hash check: source and local `.codex/skills` copies match.
