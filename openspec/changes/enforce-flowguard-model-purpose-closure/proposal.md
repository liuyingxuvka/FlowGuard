## Why

FlowGuard currently has a complete 59-model regression inventory, but most model entries do not carry a machine-checkable answer to the basic question: “Which concrete failure class is this model meant to prevent?” A model can therefore be connected to a runner and pass without proving that its candidate, known-good case, known-bad cases, oracle, and evidence all serve one frozen purpose.

This change upgrades the existing model manifest, regression runner, SkillGuard-supervised skill contracts, and installation flow in place. It does not introduce a parallel modeling framework and it does not make SkillGuard decide FlowGuard domain semantics.

## What Changes

- Add one mandatory, machine-readable purpose declaration for every concrete FlowGuard model instance. A reusable model type or checked-in template is not limited to one permanent purpose; every new or materially changed instance declares the one-or-many failures it is intended to block for the current task before candidate construction.
- Require every current instance declaration to name a stable model-instance id, task-specific guarded purpose, finite protected-failure ids, model-to-failure mapping, known-good case, one known-bad case per protected failure, native oracle, claim boundary, and current candidate/evidence/test binding.
- Make the existing regression manifest and runner reject missing, stale, duplicate, prose-only, or disconnected purpose records before model success can support a protection claim.
- Extend all seventeen FlowGuard skills so FlowGuard itself requires the purpose loop before AI creates or materially changes a model; keep exactly one non-optional route and preserve native FlowGuard ownership.
- Keep SkillGuard generic: it verifies the FlowGuard-declared contract and receipts but does not invent failure classes, require this loop from ordinary non-Guard skills, or interpret the FlowGuard oracle.
- Fix the current readiness checker to consume the canonical `.skillguard/check-manifest.json` authority and reuse the existing source/install parity process.
- Add focused model, manifest, regression, skill-contract, negative-case, and installation-projection checks before the single frozen final validation owner runs.

## Capabilities

### New Capabilities

- `flowguard-model-purpose-closure`: Defines the mandatory per-model purpose, finite failure, fixture, native-oracle, evidence, and claim-boundary closure for the existing model inventory.

### Modified Capabilities

- `flowguard-codex-skill-satellites`: Requires each FlowGuard skill entrypoint to invoke the same non-optional FlowGuard-owned purpose loop when creating or materially changing models.
- `flowguard-skill-contract-governance`: Preserves SkillGuard as the generic contract supervisor while binding FlowGuard native checks and receipts to the FlowGuard-declared purpose loop.

## Impact

- Model authority: `.flowguard/model-regression-manifest.json`, a shared FlowGuard purpose-closure module, current instance-purpose records, existing runners, and model-regression receipts. The checked-in inventory directly adopts its current 59 instances into the new contract; those records describe the current regression candidates and do not restrict later task-specific uses of the same model types.
- Skill authority: seventeen `.agents/skills/*` source contracts, generated SkillGuard contracts, FlowGuard native checks, and current installed projections.
- Validation: readiness, model-manifest, regression-orchestrator, skill-suite, installer/parity, OpenSpec, and final frozen TestMesh evidence.
- Compatibility: no selectable mode, fallback reader, dual manifest, compatibility alias, or alternate authority is added; current records are upgraded directly.
