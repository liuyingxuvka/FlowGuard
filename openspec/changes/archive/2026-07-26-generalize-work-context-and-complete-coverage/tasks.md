## 1. Authority and Planning Baseline

- [x] 1.1 Confirm the authoritative checkout, installed package identity, `main` head, tag, remote, project-audit result, and model-authority audit baseline without changing the older dirty checkout
- [x] 1.2 Run same-plane existing-model preflights for `product_runtime` and `development_process` and record the existing primary owners to reuse
- [x] 1.3 Archive the completed consumer-skill separation change without projecting its stale delta into current specs
- [x] 1.4 Create and strictly validate this proposal, design, and complete cross-capability delta-spec set
- [x] 1.5 Freeze the final touched-artifact, validation-owner, installation, Git, tag, and release plan after implementation sources stop changing

## 2. Provider-Neutral WorkContext

- [x] 2.1 Replace `SpecContext` directly with the generic `WorkContext`, `WorkContextArtifact`, review, registry, discovery, and read contracts
- [x] 2.2 Split OpenSpec and declared-files implementations into peer adapter modules so the core contains no provider-specific branch or convenience API
- [x] 2.3 Register the two built-in adapters explicitly and reject duplicate or unknown adapter ids without fallback
- [x] 2.4 Preserve native work, native owner, bounded root, artifact role, artifact content fingerprint, context fingerprint, subject lane, and behavior-source identities
- [x] 2.5 Reject path escape, missing required roles, duplicate identities, stale content, mutating authority, provider execution/check/session/cache/receipt/completion/archive metadata, and unbounded discovery
- [x] 2.6 Support zero, one, or many contexts and declared-file profiles for Spec Kit, Superpowers, and other planning sources without adding provider-specific core fields
- [x] 2.7 Add project-manifest declarations for required and optional WorkContext sources and exact required-source discovery accounting
- [x] 2.8 Replace the CLI, API registry, templates, examples, and tests with generic `work-context` names and prove retired `spec-context` surfaces are absent

## 3. Existing Owner Integration

- [x] 3.1 Upgrade ExistingModelPreflight to consume a tuple of WorkContexts only after same-plane commitment lookup
- [x] 3.2 Preserve product-runtime, agent-operation, and development-process planes without forcing a plane from the provider type
- [x] 3.3 Preserve observed, normative, and counterfactual lanes without allowing target or experiment context to become observed authority
- [x] 3.4 Add WorkContext adapter and fingerprint identities to PlanDetail sources, steps, validations, and their DevelopmentProcessFlow projection
- [x] 3.5 Add WorkContext adapter and fingerprint identities to DevelopmentProcessFlow artifacts and actions and block native-provider writes
- [x] 3.6 Generalize maintenance-scan, self-maintenance, project-adoption, and generated project guidance from OpenSpec wording to WorkContext semantics
- [x] 3.7 Remove the retired provider work-package session/cache/receipt/reconciliation/archive authority from current runtime and guidance

## 4. Exact Behavior-Source Coverage

- [x] 4.1 Extend every BehaviorSourceSurface with stable source-system, native-artifact, content, semantic, inventory-revision, discovery-evidence, and authority-role identities
- [x] 4.2 Add ledger-level subject lane, expected source-surface ids, inventory revision, discovery evidence, and complete-inventory requirement
- [x] 4.3 Change source freshness from optimistic-current by default to unchecked until current evidence proves it
- [x] 4.4 Reconcile the independently derived expected source set exactly against modeled, delegated, or explicitly scoped dispositions
- [x] 4.5 Block missing, unexpected, duplicate, unmapped, stale, and ambiguously disposed source surfaces
- [x] 4.6 Permit semantically identical promises from multiple sources to reuse one commitment while blocking incompatible normative promises for the same exact intent
- [x] 4.7 Prevent supporting or historical sources from displacing the normative promise or primary model owner
- [x] 4.8 Upgrade the repository's canonical behavior ledger into the exact current schema and rerun its native model and tests

## 5. UI and Field Completeness

- [x] 5.1 Derive a stable observed UI inventory for every visible control, interaction, transition, recovery/error branch, on-demand reveal, and terminal result
- [x] 5.2 Require every observed UI item to be modeled, delegated to one existing behavior/path owner, or explicitly scoped with evidence
- [x] 5.3 Project behavior-bearing UI promises into the shared source inventory without making presentation-only elements independent commitments
- [x] 5.4 Derive a stable leaf-field inventory covering owner, reader, writer, projection, lifecycle, replacement, default/absence, serialization, and privacy semantics
- [x] 5.5 Require every discovered field to be modeled, delegated to one lifecycle owner, or explicitly scoped with evidence
- [x] 5.6 Project behavior-bearing field promises into the shared source inventory while keeping leaf bookkeeping in FieldLifecycleMesh
- [x] 5.7 Add omission, duplicate, stale-inventory, and unstable-identity tests for UI and field exact-set reconciliation

## 6. Live Model Authority and Revision Closure

- [x] 6.1 Build the current ModelSystemInventory from the live manifest, canonical ledger, source inventories, UI inventory, field inventory, model files, code contracts, and test evidence
- [x] 6.2 Make model-authority audit compare the stored observed snapshot and head against the current live inventory instead of trusting a historically green snapshot
- [x] 6.3 Report exact added, removed, changed, and stale model/source dimensions when the observed authority is behind the live checkout
- [x] 6.4 Add changed source-surface ids to ModelRevisionSet identity and atomic activation
- [x] 6.5 Derive changed source, commitment, field, side-effect, contract, test, model, and relation sets from actual base/candidate snapshot differences
- [x] 6.6 Reject under-declared or over-declared revision closure and require the exact affected transitive closure before activation
- [x] 6.7 Refresh the authoritative observed snapshot atomically only after all changed-owner evidence is current

## 7. TestMesh and Claim Boundaries

- [x] 7.1 Add required source-inventory revision and discovery-evidence identities to TestMesh planning
- [x] 7.2 Shard exact coverage checks for WorkContext, behavior sources, UI, fields, model inventory, revision closure, API retirement, and provider-authority rejection
- [x] 7.3 Prove provider status, task checkboxes, native validation, and WorkContext currentness never count as FlowGuard test/model/release evidence
- [x] 7.4 Add negative tests for omitted objects, provider preference, aliases, fallback readers, alternate success paths, and stale snapshots
- [x] 7.5 Run focused affected tests after each stable repair group and inspect every failure before proceeding
- [ ] 7.6 Freeze and run exactly one full repository regression owner on the final source identity, retaining stdout, stderr, exit code, result artifact, and source fingerprint
- [ ] 7.7 Rerun project audit, model-system audit, model scenarios, conformance replay, loop/stuck, progress/fairness, contract/refinement, UI, field, and OpenSpec strict verification on the frozen snapshot

## 8. Maintained Skill and Project Guidance Upgrade

- [x] 8.1 Update the unified FlowGuard skill to route provider-neutral WorkContext and exact modeled/delegated/scoped completeness
- [x] 8.2 Update Behavior Commitment Ledger skill prompts and native checks for independent expected-source inventory
- [x] 8.3 Update ExistingModelPreflight skill prompts and native checks for multiple WorkContexts after plane-first lookup
- [x] 8.4 Update DevelopmentProcessFlow and internal plan-detailing/agent-workflow prompts for provider-neutral context and freshness
- [x] 8.5 Update TestMesh prompts and native checks for source-inventory revisions and non-evidence provider state
- [x] 8.6 Update project adoption rules, AGENTS projection, docs, examples, templates, changelog, and version surfaces with no retired aliases
- [ ] 8.7 Use SkillGuard to freeze the maintained unit inventory, compile contracts, run affected checks, run one final unit validation, and prove a clean consumer projection

## 9. Installation and Parity

- [x] 9.1 Bump FlowGuard to the next breaking-feature version and regenerate all governed version projections
- [x] 9.2 Install the authoritative checkout as the active editable Python package and prove `flowguard.__file__`, schema, and metadata version point to it outside the repository cwd
- [x] 9.3 Install the complete consumer skill suite transactionally and prove installed/source inventory and hashes match without SkillGuard maintainer artifacts
- [ ] 9.4 Verify the authoritative local repository, tracked source tree, installed package, installed skills, generated project guidance, and release candidate all have exact intended parity
- [x] 9.5 Preserve the older dirty checkout and every unrelated parallel change without reset, checkout-overwrite, broad cleanup, or accidental staging

## 10. Main-Only Publication and Closure

- [x] 10.1 Reconcile and sync all delta specs to current main specs, strictly validate OpenSpec, and archive this completed change
- [ ] 10.2 Perform the final post-change owner scan and close or explicitly scope every stale evidence, skipped route, open obligation, split pressure, and reduction candidate
- [x] 10.3 Confirm local and remote branch inventory and retain only `main` as the active publication branch
- [ ] 10.4 Stage only owned authoritative-checkout paths, review the exact diff, commit on `main`, and push `origin/main`
- [ ] 10.5 Create the annotated version tag and source-only GitHub Release with release notes and no unrequested assets
- [ ] 10.6 Verify clean-clone source, tag, release, package, installed skill, authoritative snapshot, and mirror parity using explicit evidence paths
- [ ] 10.7 Run the predictive-KB postflight, record any reusable route or coverage lesson, and report final completion with exact evidence and any honestly preserved non-authoritative dirty worktree
