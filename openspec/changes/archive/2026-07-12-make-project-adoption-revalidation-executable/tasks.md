## 1. Model-miss closure

- [x] 1.1 Extend the existing project-adoption FlowGuard model with package-owned executable revalidation state and a source-layout-only known-bad path.
- [x] 1.2 Run the focused FlowGuard project-adoption model and confirm the known-bad path fails while the package-owned path closes.

## 2. Runtime and regression repair

- [x] 2.1 Remove the redundant source-repository marker command from `_minimum_revalidation()` without changing the existing package-owned audit entrypoint.
- [x] 2.2 Update the portable-command assertions and add a temporary adopted-project regression that executes the generated command from a project without FlowGuard source scripts.
- [x] 2.3 Run `python -m pytest tests/test_project_adoption.py -q` and repair every focused failure.

## 3. Contract and closure evidence

- [x] 3.1 Update the canonical project-adoption requirement with executable-target semantics while preserving unrelated peer spec changes.
- [x] 3.2 Review the scoped diff for overlap with existing dirty work and prepare the current contract for final OpenSpec verification with failures, skipped checks, residual risk, and claim boundary kept visible.
