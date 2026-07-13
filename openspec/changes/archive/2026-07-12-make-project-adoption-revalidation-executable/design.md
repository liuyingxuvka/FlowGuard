## Context

`project-audit` already calls the package-owned `validate_skill_suite()` path and reports its result. Its generated revalidation list nevertheless adds `python scripts/verify_skill_suite_markers.py`, a repository-internal wrapper around the same validator. That command happens to work inside the FlowGuard source repository but fails in normal adopted projects that do not contain FlowGuard's `scripts/` tree.

The previous portability change made both commands relative and removed absolute-path leakage, but its tests asserted command text without executing it from a realistic target. The resulting report therefore looked portable while remaining unusable.

## Goals / Non-Goals

**Goals:**

- Emit one executable package-owned audit command for adopted projects.
- Preserve the existing suite validation already performed by `project-audit`.
- Add target-context execution evidence so future source-layout-only commands cannot pass by string inspection alone.
- Keep historical reports and repository-internal maintenance helpers intact.

**Non-Goals:**

- Do not add another CLI command or copy FlowGuard source scripts into target projects.
- Do not remove `scripts/verify_skill_suite_markers.py` from the FlowGuard repository.
- Do not rewrite archived OpenSpec artifacts or historical adoption logs.
- Do not broaden this repair into unrelated project-adoption, mixed-root, or behavior-plane work already present in the dirty worktree.

## Decisions

### 1. Keep `project-audit` as the single target entrypoint

The generated executable command remains `python -m flowguard project-audit --root . --json`. It is installed-package-owned and already returns project adoption status plus skill-suite status, findings, and inventory identity. Adding a second CLI would duplicate authority; copying a source script would create a deployment obligation in every adopted project.

### 2. Remove only the redundant generated command

`_minimum_revalidation()` will stop emitting `python scripts/verify_skill_suite_markers.py --root . --json`. The internal script remains available for FlowGuard source maintenance, but it is no longer advertised as a target-project requirement.

### 3. Test behavior from a real target working directory

The regression will create a valid adopted temporary project that has no FlowGuard source `scripts/` directory, execute the generated package-owned command from that directory, and require a zero exit plus passing suite status. It will also reject any generated executable command beginning with a project-local `python scripts/` path.

### 4. Extend the existing project-adoption owner

The repair extends the existing project-adoption version-gate model/spec and `flowguard.project_adoption` owner. It does not introduce a new model, runner, ledger, or package route.

## Risks / Trade-offs

- **[Consumers expected two command rows]** Removing the redundant row changes report and log content. → Keep the remaining command and human revalidation guidance stable; tests assert the new exact tuple.
- **[Package under test differs from subprocess import]** A subprocess could import another installed FlowGuard. → Run with the current test environment and assert the returned schema/suite shape; installation parity remains a separate release gate.
- **[Dirty worktree overlap]** The owner files already contain unrelated peer changes. → Apply only a local tuple/test/spec/model delta and review the scoped diff before validation.

## Migration Plan

1. Extend the current project-adoption requirement and model with executable-target semantics.
2. Remove the redundant generated command and update the focused tests.
3. Run the focused project-adoption tests and model gate.
4. Verify the OpenSpec change; do not run the full FlowGuard suite for this local repair.

Rollback restores the removed tuple item and the old assertions. No persisted data migration is required; future reports and logs simply emit the corrected guidance.

## Open Questions

None.
