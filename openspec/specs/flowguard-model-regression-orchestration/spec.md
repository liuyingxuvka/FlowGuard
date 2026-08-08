# flowguard-model-regression-orchestration Specification

## Purpose
Define complete, observable, fail-closed model regression execution with exact per-model freshness and reusable terminal evidence.
## Requirements
### Requirement: Explicit Model Regression Manifest
The repository SHALL maintain a versioned regression manifest that accounts for every discovered FlowGuard model directory and executable model entry. Each record SHALL declare model id, runner command, tier, timeout, shard-safety, mutation policy, watched inputs, expected artifacts, and either execution status or an explicit evidence-backed exclusion.

#### Scenario: Model has executable main but no run_checks file
- **WHEN** discovery finds an executable model entry absent from the manifest
- **THEN** inventory validation fails even if `rglob("run_checks.py")` would omit it

#### Scenario: Manifest names missing model
- **WHEN** a manifest record points to a model that no longer exists
- **THEN** inventory validation fails with a missing-model finding

### Requirement: Tiered And Selectable Regression Execution
The regression orchestrator SHALL support fast, focused, and full tiers plus model filters and deterministic shards. Only the full tier with all required manifest records terminal and current MAY support release validation.

#### Scenario: Fast tier passes
- **WHEN** the fast tier completes successfully
- **THEN** output claims fast-tier confidence only and does not imply full model closure

#### Scenario: Full tier skips required runner
- **WHEN** a required full-tier model is skipped or not run
- **THEN** full regression status is not pass and names the missing terminal

### Requirement: Bounded Observable Runner Execution
Every runner SHALL have a configured timeout, progress events, output isolation, captured stdout/stderr, cancellation behavior, and a terminal evidence receipt. Background or parallel execution SHALL be permitted only for manifest entries declared shard-safe and output-isolated.

#### Scenario: Runner exceeds timeout
- **WHEN** a runner exceeds its declared timeout
- **THEN** the orchestrator terminates it, emits a timeout terminal receipt, and continues or blocks according to tier policy

#### Scenario: Unsafe runner is scheduled in parallel
- **WHEN** a runner is not shard-safe or shares an output path
- **THEN** the scheduler serializes or rejects that execution rather than racing it

### Requirement: Non-Mutating Default
Default regression execution MUST NOT modify tracked repository files. A mutating runner SHALL require explicit authorization and an isolated output or worktree policy; mutation discovered in default mode MUST fail the run.

#### Scenario: Runner rewrites result json in default mode
- **WHEN** a runner modifies a tracked `result.json` during default execution
- **THEN** the orchestrator marks a mutation-policy failure and full validation is blocked

### Requirement: Exact-Current Per-Model Reuse
The model regression orchestrator SHALL independently resolve and verify one
terminal receipt per required model against the model's own declared content,
runner, local inputs, purpose, dependencies, toolchain, environment, inventory,
and obligations. A model with an exact-current receipt SHALL be reused without
starting its runner.

#### Scenario: Identical full model request repeats
- **WHEN** every required model has an independently verified exact-current terminal-success receipt
- **THEN** the parent model result composes those receipts and starts zero model runners

#### Scenario: One model input changes
- **WHEN** one model's declared local input changes and no declared relation or shared dependency expands the affected closure
- **THEN** only that model executes and unrelated model receipt ids remain reusable

### Requirement: Local Model Instance Identity
A model instance fingerprint SHALL contain only that model's logical id, model
content, runner, declared local inputs, purpose binding, and consumed
schema/tool identities. The model-system source revision and Git revision SHALL
remain snapshot-level provenance and SHALL NOT alter unrelated instance
fingerprints.

#### Scenario: Unrelated model changes
- **WHEN** model A changes and model B's local functional inputs are identical
- **THEN** model B retains the same instance fingerprint while the candidate snapshot fingerprint changes

### Requirement: Fail-Closed Model Impact Planning
Before execution, every changed functional input SHALL map to an exact model,
relation, shared dependency, or explicit snapshot-only owner. Missing,
ambiguous, or conflicting mappings MUST block the model plan and MUST NOT fall
back to running all models.

#### Scenario: Unknown model input appears
- **WHEN** a governed source path has no declared impact owner
- **THEN** plan status is blocked, no model producer starts, and the missing mapping is reported

### Requirement: Model Receipt Preservation After Parent Failure
Terminal-success model receipts SHALL remain independently reusable when a
sibling model or parent composition fails, provided their exact functional
identities remain current.

#### Scenario: One model fails then is repaired
- **WHEN** a full model parent records one failed model and later only that model's inputs change
- **THEN** successful sibling receipts are reused and only the repaired model executes

### Requirement: Retired regression owners require replacement-case accounting
Model regression orchestration SHALL remove an intentionally retired child only after every still-required failure obligation and native case has either moved to one current child with an executable oracle or received an explicit product-behavior retirement disposition.

#### Scenario: Historical model child is redundant
- **WHEN** its protections are fully mapped to current children or intentionally retired behavior
- **THEN** the manifest, purpose closure, model inventory, parent aggregation, and release plan use the reduced current child set

#### Scenario: Failure obligation is orphaned
- **WHEN** a retired child's current failure or known-bad obligation has neither a replacement owner nor an approved behavior-retirement disposition
- **THEN** manifest validation blocks removal and identifies the orphaned obligation

### Requirement: Runtime validation inputs have exact model owners
Every ordinary runtime source input in the model-regression manifest SHALL map to its exact current model owner set through the authoritative software-blueprint ownership map or an equally exact reviewed declaration. A broad package-wide source glob SHALL NOT make every current model stale merely because one bounded runtime module changed. A truly package-global metadata or toolchain input MAY affect every model only when its global ownership is explicit and independently reviewable.

#### Scenario: One runtime module serves one model owner
- **WHEN** that module changes and no package-global input changes
- **THEN** affected planning SHALL invalidate only its exact model owner and any models reached through declared dependency edges
- **AND** unrelated sibling models SHALL remain eligible for exact-current evidence reuse

#### Scenario: An ordinary runtime module has no exact owner mapping
- **WHEN** manifest compilation finds a runtime source that is neither directly mapped nor covered by one exact reviewed owner group
- **THEN** manifest validation SHALL fail with the unmapped source
- **AND** it SHALL NOT fall back to a package-wide run-all group

#### Scenario: Package metadata is globally consumed
- **WHEN** a declared package-metadata or toolchain input changes and every current model genuinely consumes it
- **THEN** the manifest MAY invalidate the complete current model set
- **AND** that global edge SHALL remain separately named from ordinary runtime source ownership

### Requirement: Every logical model has one canonical regression evidence identity
Each current model-regression manifest row SHALL declare exactly one native evidence identity equal to `check:model-regression:<logical-model-id>`. Additional independently owned diagnostic checks MAY remain beside it, but a hyphenated alias, display label, historical spelling, or another model's identity SHALL NOT replace or duplicate the canonical logical-model evidence id.

#### Scenario: One evidence id uses a display-name spelling
- **WHEN** a manifest row's logical model id uses one canonical spelling but its model-regression evidence id uses a hyphenated, aliased, or historical spelling
- **THEN** manifest validation SHALL fail before the inconsistency can expand across every implementation surface owned by that model
- **AND** the producer SHALL replace the identity directly rather than adding an alias or compatibility reader

#### Scenario: One model also owns a separate diagnostic check
- **WHEN** the purpose closure declares its exact canonical model-regression evidence id and one separately named diagnostic projection
- **THEN** both evidence members MAY remain when each has a distinct current purpose
- **AND** only the exact `check:model-regression:<logical-model-id>` row SHALL satisfy the logical model-regression identity

### Requirement: Full model composition shares one frozen validation observation
A bounded full-model planning, execution, or parent-composition operation SHALL resolve the complete repository input manifest, receipt inventory, owner contexts, and exact-current child receipt set once for its initial frozen observation. Every sibling child decision and parent row in that operation SHALL consume those same exact identities rather than rebuilding the complete observation per child, per row, or per aggregate.

#### Scenario: Fifty-one model children compose one parent
- **WHEN** one full-model operation plans or composes all required model children from unchanged repository and receipt-store inputs
- **THEN** instrumentation SHALL show one complete initial validation observation shared by every child decision
- **AND** the parent SHALL name the exact observation identity it consumed

#### Scenario: One child identity changes during composition
- **WHEN** the final freshness observation differs from the frozen observation for any consumed model input, owner context, receipt, or required child identity
- **THEN** parent publication SHALL be blocked as stale
- **AND** the operation SHALL NOT silently rebuild selected rows against the newer state or fall back to a full rerun

### Requirement: Final parent freshness comparison does not repeat semantic execution
Before publishing a current full-model parent, the orchestrator SHALL perform one fresh repository-and-receipt identity observation and compare it with the frozen observation. When the identities match, the comparison SHALL NOT rerun already terminal child producers or repeat their native semantic verifiers; when an identity differs, the parent SHALL fail closed and require a separately planned affected operation.

#### Scenario: Frozen inputs remain unchanged
- **WHEN** every final manifest, receipt inventory, owner, and child identity matches the frozen observation
- **THEN** the parent MAY become current without a second complete child-verification pass
- **AND** executed and reused child counts SHALL remain unchanged

#### Scenario: Receipt store changes after child verification
- **WHEN** a receipt is added, removed, replaced, or becomes ambiguous before parent publication
- **THEN** the final comparison SHALL reject the parent
- **AND** no earlier in-memory success or persistent cache SHALL override the drift

#### Scenario: Several executed leaves require publication
- **WHEN** several selected native model runners terminate against one frozen operation
- **THEN** the orchestrator SHALL make one final complete repository observation before publishing their validation-owner receipts
- **AND** every executed leaf SHALL use its owner context from that final observation instead of rebuilding current source identity per leaf
- **AND** one post-publication receipt reconciliation SHALL verify the exact newly supplied receipt identities without a third complete repository observation

### Requirement: Full-model timing reports separate useful work and observation overhead
The canonical full-model result SHALL report producer execution time, exact-current reuse count, initial observation time, final freshness-comparison time, and parent-composition time as distinct bounded measurements. Timing fields are diagnostic only and SHALL NOT become evidence authority.

#### Scenario: All child receipts are reused
- **WHEN** a full-model request starts zero child producers
- **THEN** the result SHALL distinguish zero producer execution from the time spent observing and composing current evidence
- **AND** it SHALL NOT report observation time as model execution time
