## Context

`_minimum_revalidation(root_path)` currently formats the resolved target path into two copyable commands. The same tuple is projected into project-adoption reports and into `next_actions` in the Markdown adoption log, so a runtime-only filesystem location crosses into durable public evidence.

The existing `project_adoption_version_gate` remains the owner. This is a formatting-boundary repair, not a second privacy filter or a new adoption workflow.

## Goals / Non-Goals

**Goals:**

- Make every generated minimum-revalidation command runnable from the target repository with `--root .`.
- Prove the report projection and human Markdown log do not contain the temporary target's absolute path in those commands.
- Preserve all current adoption, audit, upgrade, and validation semantics.

**Non-Goals:**

- Redact intentional diagnostic path fields such as the report's `root`, proposed files, or written files.
- Rewrite historical adoption logs.
- Change command discovery, project layout, package versions, or the project-adoption state model.

## Decisions

1. **Make the command source independent of `root_path`.** `_minimum_revalidation` will take no target-path input and return canonical project-relative commands. Updating its call sites removes the data dependency that caused the leak instead of filtering strings later.
2. **Keep one owner for both projections.** Reports and Markdown logs continue consuming the same tuple, preventing drift between machine and human evidence.
3. **Test a nested temporary path.** Regression coverage will assert the exact portable commands in the report and the absence of the resolved temporary root in the Markdown log.
4. **Reuse the existing model boundary.** The project-adoption version-gate model will be rerun for unchanged lifecycle semantics; ordinary tests carry the new output-boundary obligation.

## Risks / Trade-offs

- **Commands assume execution from the target project root** → The generated text explicitly uses `--root .`, matching existing project guidance and copy/paste expectations.
- **Other report fields may intentionally remain absolute** → Tests scope the privacy guarantee to generated revalidation commands and public Markdown next actions, avoiding an unrelated report-schema change.
- **Historical logs retain earlier paths** → This change prevents new leakage; historical cleanup remains a separate repository-data decision.
