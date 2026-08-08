## Why

FlowGuard's release validation distinguishes author-source skill trees from clean consumer installations, but the current synchronization command can only create the consumer projection and therefore cannot safely make the shadow author tree current. The model-revision builder also validates an intent inventory's internal fingerprints without proving that its declared source files are still current, leaving a stale-but-self-consistent authority gap.

The self-blueprint currently projects only the intent contributions admitted by the latest accepted revision. Those contributions correctly describe one change, but they are not the cumulative current intent of the whole target system. A small latest delta can therefore look internally complete while most current model owners and behavior blocks have no current intent binding. FlowGuard needs one direct-current cumulative intent view inside the accepted revision, with coverage measured against independently observed model and behavior denominators.

## What Changes

- Add one direct author-source synchronization operation that moves an installer-owned FlowGuard consumer tree to the current author projection without copying the surrounding repository or touching co-located non-FlowGuard work.
- Make the author synchronization ownership-aware, fail closed on modified or unowned collisions, remove only exact installer-owned consumer artifacts during the explicit role transition, and support dry-run plus idempotent currentness checks.
- Require model-revision construction to recompute every intent contribution's declared source identity from the current project files before writing any candidate authority artifact.
- Require every active direct project-file intent source to be declared as an exact input of its one logical model owner, so source changes invalidate the correct model instead of only producing a system-wide stale warning; keep WorkContext sources on their exact external identity path.
- Compile one content-addressed cumulative current-intent view inside every accepted model revision, folding the prior current view and the new delta through explicit retain, supersede, or retire transitions.
- Require that view to bind every independently observed current model owner and require every current behavior block to consume the exact effective intent of its model owner.
- Directly migrate the existing revision ancestry once into the current schema with an evidence-bound bootstrap receipt; normal runtime never reads a legacy revision as current intent or guesses missing owners from the latest delta.
- Make one strict current-authority state owner validate the head, observed snapshot, accepted revision, activation-or-rollback transition receipt, exact predecessor binding, cumulative intent view, and current source identities before audit, build, activation, or rollback may treat the base as current.
- Make transition publication preserve unrelated peer manifest edits through a final re-read and authority-section compare-and-swap instead of replacing the manifest from an early cached copy.
- Make explicit legacy bootstrap follow the exact accepted activation/rollback head chain, ignore unrelated orphans, reject malformed historical wire data, and reject supersede/conflict references outside the audited intent graph.
- Remove redundant derived truth fields from authority wire where they can be recomputed, and require strict JSON primitive types for every remaining field before canonical fingerprinting.
- Keep author-source synchronization and consumer installation as separate, single-purpose routes; neither route may silently fall back to the other projection.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-skill-suite-distribution`: Define a safe, ownership-aware author-source shadow synchronization route distinct from consumer installation.
- `model-revision-set`: Require exact-current intent source identity before candidate revision construction.
- `model-revision-set`: Make the accepted revision the single owner of a complete cumulative current-intent view and its explicit lineage transitions.
- `software-blueprint-readiness`: Measure current intent completeness against independent model-owner and behavior-block denominators.
- `target-system-blueprint`: Advance the strict project-document identity when the embedded intent inventory becomes v5, and reject the former parent/child schema combination instead of reinterpreting it.

## Impact

- Distribution tooling and tests in `flowguard/distribution_sync.py`, `scripts/install_flowguard_skills.py`, and `tests/test_distribution_sync.py`.
- Model intent/revision validation, exact transition/current-state loading, strict wire parsing, peer-safe manifest CAS, and tests in `flowguard/model_intent.py`, `flowguard/model_intent_authority.py`, `flowguard/model_revision_builder.py`, `flowguard/model_revision_set.py`, `flowguard/model_authority_store.py`, and their test modules.
- Model-regression manifest identity, input resolution, and focused owner selection in `flowguard/model_regressions.py`, `flowguard/model_system_inventory.py`, the self-blueprint definition compiler, and their tests.
- Current revision loading, self-blueprint intent projection, strict blueprint loading, and behavior readiness in `flowguard/model_revision_set.py`, `flowguard/model_authority_store.py`, `flowguard/self_blueprint.py`, `flowguard/project_blueprint.py`, and `flowguard/software_blueprint_readiness.py`.
- The portable project-document schema advances once so one schema identity never denotes both the old optional-denominator shape and the new required model-owner denominator.
- Release validation can synchronize the FlowPilot shadow skill tree without overwriting its repository or accepting a consumer projection as author evidence.
