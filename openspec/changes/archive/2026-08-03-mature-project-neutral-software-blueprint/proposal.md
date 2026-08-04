## Why

FlowGuard can already inventory and export its own implementation blueprint, but its current self-builder still derives too much of the claimed model, semantic description, and code binding from the same Python source scan. That proves traceability, not independent understanding: the same defect can be copied into all three layers, broad fallback owners and broad oracles can hide unresolved surfaces, and another Python project cannot yet ask FlowGuard to build the same depth report through a project-neutral entrypoint.

This change matures the existing blueprint into a reusable, honest software-blueprint capability: one living model lineage can absorb current implementation observations and future-intent contributions, every qualified obligation can be traced to independent semantics, concrete code, and current tests, and ordinary work remains lightweight without reconstruction.

## What Changes

- Replace the FlowGuard-only blueprint assembly path with one project-neutral Python blueprint builder plus a thin FlowGuard preset; unsupported languages and unresolved surfaces remain explicit blockers rather than silently falling back to FlowGuard's authoritative model.
- Separate inventory, traceability, independent semantic, model-code-test, resource/oracle, and optional empirical-reconstruction qualification states. Source-derived observations can support discovery and traceability but cannot independently prove intended semantics.
- Introduce a project test inventory and exact obligation-to-CodeContract-to-code-to-test-evidence bindings, including assertion quality, source and execution identities, freshness, and explicit orphan/unresolved dispositions. A broad green pytest result remains parent evidence, not a substitute for row-level coverage.
- Record WorkContext, OpenSpec, declared Spark/OpenSpark material, changelog/history, and user decisions as typed intent contributions to the same model lineage. ModelRevisionSet remains the sole acceptance and activation owner and must expose contribution conflicts, supersession, rejection, deferral, and unresolved targets.
- Make the blueprint's self-assessment readable to AI: it reports the deepest proven layer, the exact missing owner/evidence, and whether implementation admission is ready, scoped, stale, or blocked. User authorization to write code remains separate from understanding sufficiency.
- Keep empirical reconstruction optional and `not_run` by default. Inventory, audit, export, install, regression, release, and normal maintenance never trigger reconstruction automatically.
- Upgrade the current FlowGuard model, public API/CLI, executable models, tests, prompts, and affected skills only after the underlying capability is real; no new `DNA` skill, no second model authority, and no target-application role catalog are added.
- Use FlowGuard's resulting self-blueprint to audit duplicate paths, helpers, adapters, validation routes, and public facades. Apply only behavior-preserving, evidence-ready contractions and preserve every uncertain candidate as a typed obligation.
- Add the self-blueprint qualification and current architecture-reduction review as explicit release evidence, then synchronize source, editable package, installed consumer skills, Git identity, tag, and GitHub Release under one patch version.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `authoritative-model-system`: Makes project-neutral blueprint qualification consume independent semantic, implementation, test, resource, oracle, and intent-lineage evidence without creating a second authority.
- `work-context`: Projects declared requirement, design, plan, history, Spark/OpenSpark, changelog, and user-decision material into typed, project-bounded intent contributions rather than execution evidence.
- `model-revision-set`: Accounts for accepted, superseded, rejected, deferred, conflicting, and unresolved intent contributions during one atomic model revision.
- `model-test-alignment`: Requires exact project test inventory and row-level model-semantic-code-test bindings for deep blueprint qualification.
- `test-evidence-mesh`: Preserves test source identity, executable node identity, assertion quality, receipts, and freshness without letting one broad parent result fill missing obligation rows.
- `flowguard-api-registry`: Registers the project-neutral blueprint and test-inventory APIs under the existing kernel owner.
- `flowguard-validation-command-surface`: Adds read-only project blueprint audit/check surfaces that never reconstruct automatically.
- `flowguard-ai-entry-simplification`: Makes AI report proven understanding depth and missing evidence while preserving lightweight affected-only use and explicit user execution choice.
- `development-process-flow`: Orders project-blueprint, self-audit, safe reduction, affected validation, installation, final frozen validation, and release while preserving peers and keeping reconstruction optional.
- `architecture-reduction`: Consumes current blueprint/code/test evidence for candidate completeness and allows only equivalence- or facade-proven contractions.
- `flowguard-self-maintenance-mesh`: Requires FlowGuard to qualify itself through the same project-neutral path it exposes to other Python projects.
- `flowguard-skill-suite-distribution`: Synchronizes the affected author skills and clean consumer projection only after target-owned checks and SkillGuard supervision pass.

## Impact

The change affects implementation-blueprint data structures and qualification, Python implementation and test discovery, self-blueprint assembly, WorkContext and ModelRevisionSet lineage records, Model-Test Alignment and TestMesh evidence, API/CLI registration, executable FlowGuard models and regression manifests, selected FlowGuard skill prompts, documentation, installation projection, release validation, and patch-version metadata. It does not add a compatibility reader, alternate model head, automatic reconstruction workflow, new public route, or non-Python deep-discovery claim.
