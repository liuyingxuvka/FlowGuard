## Why

FlowGuard can currently validate UI content, text hierarchy, behavior commitments, primary paths, similarity, and model-code-test evidence independently, but the existing owners do not yet share one stable business-intent identity or require complete same-intent surface inventories. This allows locally green models to miss cross-page UI drift, split one user intent across multiple commitments or runtime owners, omit duplicate candidates, or accept opaque handoff IDs that were never consumed.

## What Changes

- Extend the existing model preflight and similarity flow to inventory UI, API, CLI, alias, adapter, wrapper, and helper surfaces for the same stable business intent before admitting a new boundary.
- Require one active behavior commitment and one current green Primary Path Authority contract for each exact business intent; additional surfaces delegate to that path or declare a genuinely different intent with typed external differences.
- Keep UI content admission exactly `user_visible`, `user_on_demand`, or `internal`, while adding product-scope comparison of existing typography, component, navigation, interaction, feedback, recovery, and transition semantics inside `ui_flow_structure`.
- Bind business UI features, action grammars, functional chains, and transition projections to the existing commitment and primary path without making UI the runtime authority owner.
- Require ObligationFamily, Model-Test Alignment, RuntimePathEvidence, ArchitectureReduction, ContractExhaustionMesh, and TestMesh to consume complete inventories and materialized obligations rather than opaque or caller-selected IDs.
- Update the existing skills, prompts, protocols, templates, docs, self-models, tests, version/install workflow, shadow/formal parity, and local Git closure.
- **BREAKING**: path-sensitive runtime bindings accept and emit only one
  singular `primary_path_id`. Retired `primary_path_ids` is handled only by
  the exact historical BCL artifact upgrader and is never a runtime alias.
- Do not create a Product Design Language route, Functional Path Reuse route, intent ledger, second evidence engine, second runtime authority, audience/persona visibility taxonomy, or new CLI command.

## Capabilities

### New Capabilities

None. This change only upgrades existing capability owners and their handoffs.

### Modified Capabilities

- `existing-model-preflight`: require affected same-intent surface inventory, stable behavior identities, and a typed Behavior Commitment Ledger handoff.
- `model-similarity-consolidation`: compare stable commitment/intent/path identities, prove inventory completeness, and emit materialized downstream obligations.
- `behavior-commitment-ledger`: enforce one active commitment per exact business intent and verify semantic identity against PPA evidence.
- `primary-path-authority`: enforce one runtime authority per stable business intent, complete candidate accounting, and current RuntimePathEvidence.
- `flowguard-ui-flow-structure`: preserve three-class content admission while adding cross-surface typography/UI grammar review and commitment/path binding.
- `runtime-path-evidence`: carry stable business-intent, commitment, and selected-primary-path observations across declared surfaces.
- `obligation-family-parity-provenance`: prove expected family membership and bind evidence to every member obligation.
- `model-test-alignment`: require similarity obligations to materialize and verify shared intent/path authority across UI transitions and family mechanisms.
- `architecture-reduction`: require candidate inventory after duplicate/same-workflow handoffs and preserve only delegating facades.
- `contract-exhaustion-mesh`: generate missing-intent, wrong-path, parallel-success, stale-proof, omitted-member, and invalid-UI-exception cases.
- `test-evidence-mesh`: preserve background/full regression liveness separately from current passing receipts for the new matrices.
- `development-process-flow`: order OpenSpec, model, code, validation, install, shadow/formal synchronization, and local Git evidence without overwriting peer work.
- `flowguard-api-registry`: expose the new UI consistency helpers inside the existing `ui_flow_structure` API group without adding a route.

## Impact

- Core modules: `existing_model_preflight.py`, `model_similarity.py`, `behavior_commitment.py`, `primary_path_authority.py`, `runtime_path.py`, `ui_structure.py`, `transition_coverage.py`, `obligation_family.py`, `model_test_alignment.py`, and `architecture_reduction.py`.
- Public Python API: additive UI consistency types/helpers plus the singular behavior-path binding field migration; no new CLI or route ID.
- FlowGuard guidance: existing skill prompts, protocols, SkillGuard contract sources, templates, docs, self-models, and project guidance.
- Evidence and delivery: focused tests, ContractExhaustion cases, TestMesh/model regressions, project audit, installed-skill parity, editable-install parity, non-destructive formal-repository sync, and local Git version closure.
