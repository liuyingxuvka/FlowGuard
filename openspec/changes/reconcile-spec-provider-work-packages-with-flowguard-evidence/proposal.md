## Why

OpenSpec and FlowGuard currently connect through manually authored verification commands, but they do not reconcile specification tasks with FlowGuard obligations or share current evidence across active changes. This causes duplicated full regressions, permits broad watch patterns to mix canonical inputs with derived result files, and can produce a report that becomes stale immediately when a verification command mutates a watched input.

## What Changes

- Add a provider-neutral Spec Work Package boundary that reads OpenSpec and Spec Kit artifacts within the declared project root without replacing either provider's task, strict-validation, or archive authority.
- Reconcile in-scope provider tasks bidirectionally with FlowGuard obligations/checks or typed scoped-out reasons; preserve stable provider/change/task/check identities and behavior-plane ownership.
- Add canonical governed-input versus derived-output classification, same-session begin/post snapshots, and a hard failure when verification mutates canonical inputs.
- Add immutable terminal check receipts and exact reuse tickets so one execution can fan out to several tasks/obligations or explicitly cross-change-safe consumers without copying evidence or accepting progress-only output.
- Add a cached-check CLI and provider audit/reporting surface with canonical language-neutral JSON; keep human projection separate from product UI rules.
- Extend DevelopmentProcessFlow, PlanDetailing, TestMesh, ExistingModelPreflight, public APIs/templates, and maintained skills to consume the new work-package and receipt evidence instead of creating a parallel process engine.
- Make all seventeen managed FlowGuard skills declare the lifecycle of their former V1 runtime surfaces honestly. V2 remains the only runtime authority; former V1 files are migration evidence only until official content-addressed calibration and atomic retirement can prove `v2-only`.
- Update the two current product-language/execution-plane verification contracts to exclude derived results from freshness inputs and reuse identical current full-regression receipts where the execution boundary is explicitly safe.

## Capabilities

### New Capabilities

- `spec-provider-work-packages`: Provider discovery, task/obligation reconciliation, canonical input snapshots, immutable check receipts, explicit cross-change reuse, and provider-authority boundaries.

### Modified Capabilities

- `development-process-flow`: Consume provider work packages, begin/post snapshots, peer-write invalidation, and shared receipt fan-out before done/archive claims.
- `test-evidence-mesh`: Treat deduplicated spec checks as TestMesh children and reject unsafe, stale, incomplete, or implicitly cross-change reuse.
- `plan-detailing-compiler`: Preserve provider/change/task identities and bidirectional task-to-obligation mappings when a specification plan is projected into development steps.
- `existing-model-preflight`: Include provider work-package context after plane-first commitment lookup without letting specification tasks take over behavior ownership.
- `proof-artifact-bound-evidence`: Bind spec-check receipts to exact inputs, commands, tools, environments, coverage, terminal status, and post-snapshot identity.
- `flowguard-api-registry`: Export the new data structures, reviews, cached-check runner, and provider audit CLI without duplicate public owners.
- `flowguard-codex-skill-satellites`: Update native skill guidance and V2 contract bindings for the existing DevelopmentProcessFlow, TestMesh, PlanDetailing, and preflight owners.
- `flowguard-skill-suite-distribution`: Preserve explicit V2-migration authority, generated-contract parity, installed-layout parity, and the official later retirement gate for all managed skills.

## Impact

- New FlowGuard model and Python implementation for provider work packages and receipt execution.
- Additive CLI/API/template/documentation surfaces plus focused and known-bad tests.
- Narrow updates to existing process, test-mesh, plan-detail, preflight, self-maintenance, release verification, skill contracts, and current OpenSpec verification contracts.
- No OpenSpec or Spec Kit fork, no whole-computer scan, no product UI presentation change, and no transfer of product-runtime commitment ownership to the development-process bridge.
