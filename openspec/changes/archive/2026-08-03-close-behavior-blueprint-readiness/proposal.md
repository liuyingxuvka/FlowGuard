## Why

FlowGuard can currently qualify a project-neutral static blueprint at model-owner granularity, but that result is too coarse for the stronger claim that the blueprint is a software-life "DNA": important behavior blocks do not yet have independent semantics, exact assertion-level model-code-test bindings, complete resource and intent denominators, or a read-only reconstruction-readiness verdict. The interrupted v0.68.6 release attempt also exposed lifecycle and parent/child evidence gaps that must be closed before publication.

## What Changes

- Split blueprint depth into owner-level structural closure, behavior-block closure, reconstruction readiness, and optional empirical reconstruction; reconstruction remains explicit-only and is never scheduled by ordinary work, audit, install, cleanup, or release.
- Add behavior-bearing surface contracts expressed as `Input x State -> Set(Output x State)` with exact input, output, state/effect, error, decision, order, retry, timeout, and completion applicability.
- Add assertion/case-level coverage bindings that distinguish test source, checker definition, and current terminal execution evidence; stop copying one owner's entire evidence set to every implementation surface.
- Add independently derived project resource and intent-lineage inventories, including terminal dispositions for absent, external, scoped-out, and blocked members.
- Add a read-only candidate-blueprint path for supported external projects. Inferred semantics remain unresolved until independently accepted; the path does not write target source or run reconstruction.
- Normalize and shard blueprint references so ordinary work loads only the affected owner and behavior neighborhood while explicit full qualification retains exact set closure.
- Turn FlowGuard's pre-release architecture-reduction review into machine-readable evidence bound to the exact self-blueprint fingerprint and frozen candidate denominator.
- Add typed external-interruption settlement, prevent child `CURRENT` pointers from being mistaken for a terminal parent pass, and make partial/interrupted evidence non-reusable.
- Expand regressions for coarse-semantics false positives, shared-test false coverage, unbound tests, omitted resources, empty intent lineage, same-source oracle circularity, native-checker-without-receipt, residual-lease recovery, and child/parent status confusion.
- Synchronize maintained FlowGuard skills, package/install projections, source, Git, tag, and GitHub Release only after one frozen final gate passes. This change does not add a standalone DNA skill or compatibility path.

## Capabilities

### New Capabilities

- `software-blueprint-readiness`: Defines behavior-block qualification, independent resource and intent denominators, candidate blueprint generation, normalized shards, and the read-only reconstruction-readiness decision.

### Modified Capabilities

- `authoritative-model-system`: Tightens the meaning of blueprint depth and binds behavior/readiness evidence to the sole observed authority.
- `model-test-alignment`: Requires exact behavior-surface, test-node, assertion/case, covered-dimension, oracle, execution-owner, and terminal-receipt rows for blueprint closure.
- `test-evidence-mesh`: Requires complete test-node dispositions and exact leaf execution evidence without parent-result substitution.
- `model-revision-set`: Requires non-trivial accepted revisions to account for current intent contributions or an explicit typed no-intent rationale.
- `development-process-flow`: Adds external-interruption settlement, parent/child current-pointer ownership, and final blueprint/reduction release ordering.
- `architecture-reduction`: Requires a machine-readable self-reduction denominator and proof report bound to the current blueprint.
- `flowguard-ai-entry-simplification`: Exposes the deepest proven understanding layer, reconstruction readiness, and first unresolved gap without loading the full blueprint.
- `flowguard-validation-command-surface`: Adds read-only candidate/readiness checks and correct parent/child terminal status semantics.
- `flowguard-self-maintenance-mesh`: Makes behavior closure and self-reduction evidence explicit release children.
- `flowguard-skill-suite-distribution`: Includes the new blueprint and self-reduction owners in the frozen source/install/release closure while preserving clean consumer projection.

## Impact

- Core blueprint and evidence modules: `implementation_blueprint.py`, `project_blueprint.py`, `self_blueprint.py`, `test_inventory.py`, `model_intent.py`, model revision and evidence lifecycle code, CLI surfaces, and self-model definitions.
- FlowGuard maintained skills and protocols for the kernel, existing-model preflight, code structure, model-test alignment, TestMesh, ModelMesh, ArchitectureReduction, ContractExhaustionMesh, and DevelopmentProcessFlow.
- OpenSpec main capabilities listed above, package/version metadata, documentation, model authority snapshots, regressions, installation projections, and the final source-only GitHub release workflow.
- Python remains the only deep discovery adapter in this patch. Additional language adapters and any empirical reconstruction exercise remain later, separately requested capabilities.
