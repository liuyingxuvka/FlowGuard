# Read-only OpenSpec Context

FlowGuard can read one official OpenSpec change as planning context. This is a
small boundary on purpose: OpenSpec remains independent, and FlowGuard does
not become an OpenSpec controller.

## What FlowGuard reads

For a safe change directory under the declared project root, FlowGuard reads:

- `proposal.md`;
- `design.md`;
- `tasks.md`;
- Markdown specifications under `specs/`;
- task checkbox counts and the derived status `proposed`, `in-progress`, or
  `complete`.

Every physical artifact has a stable project-relative identity and content
hash. Derived status has its own deterministic identity. Reading and review do
not write any file.

## What FlowGuard never owns

`SpecContext` carries no:

- OpenSpec write or implementation authority;
- provider command or check execution;
- session, cache, snapshot, or receipt;
- check owner, dependency owner, or consumer fan-out;
- task-to-FlowGuard obligation reconciliation;
- validation, completion, or archive-readiness decision.

If OpenSpec material implies a FlowGuard model or test is needed, that
FlowGuard check has its own native owner and evidence. An OpenSpec checkbox or
derived status is context, never proof that a FlowGuard check ran.

## Commands

Read and review one change:

```powershell
python -m flowguard spec-context --root . --change <change-id> --json
```

Write the reusable FlowGuard model template:

```powershell
python -m flowguard spec-context-template --destination .
```

Requests for Spec Kit or another provider fail closed. Unsafe, nested, or
path-traversing change ids also fail before any out-of-root read.

## Claim boundary

A passing context review proves only that the supported official OpenSpec
authoring material was present, project-bounded, read-only, and fingerprinted
at the time of reading. It does not prove OpenSpec validation, FlowGuard
validation, implementation completion, archive readiness, or future agent
behavior.
