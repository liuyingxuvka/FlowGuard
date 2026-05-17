## Why

The `model-first-function-flow` Skill has grown from an entrypoint into a long
combined policy, protocol, and reference document. It now mixes routing rules,
daily modeling rules, ModelMesh, TestMesh, StructureMesh, model-miss handling,
conformance replay, background logging, adoption logging, framework-upgrade
rules, and resource indexing in one file.

That shape makes future changes harder to review and increases the chance that
agents miss a route, duplicate guidance, or weaken a hard invariant while
editing unrelated sections.

## What Changes

- Reframe the Skill as a compact FlowGuard Skill Kernel: a routing entrypoint
  plus hard non-negotiable rules.
- Move detailed procedures into dedicated sub-protocol references for core
  modeling, mesh routes, model misses, conformance/adoption, long checks, and
  framework upgrades.
- Add a route map that clearly distinguishes agent sub-protocols from package
  helper APIs.
- Add a FlowGuard rollout model that rejects known-bad modularization outcomes,
  such as missing hard gates, missing sub-protocols, duplicated rule ownership,
  over-triggering heavy checks, or treating API helpers as independent skills.
- Update public docs, AGENTS snippet, README, changelog, OpenSpec artifacts,
  and focused tests.

## Capabilities

### New Capabilities

- `flowguard-skill-kernel`: Maintains the Skill as a compact router with
  delegated sub-protocols and explicit ownership of rules.

### Modified Capabilities

- `model-first-function-flow`: Uses the kernel route map to choose one or more
  sub-protocols while preserving standalone FlowGuard behavior.

## Impact

- Skill/docs: shorter main Skill, new reference protocols, updated
  documentation and tests.
- Runtime package: no schema change and no new dependency.
- Release: folds into the already prepared unreleased `v0.9.0` release.
