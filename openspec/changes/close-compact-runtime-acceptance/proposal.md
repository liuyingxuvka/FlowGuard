## Why

The current FlowGuard source contains useful compact lifecycle and map work, but the released `0.69.5` state still has an incomplete closeout boundary: native case results can be inferred from process output, the accepted self-model is stale relative to current source, selected map reads and model evolution are not jointly proven, and the published checks cover only a narrow subset of the source. This change creates one current, auditable acceptance change for the remaining C00-C13 work instead of treating historical OpenSpec changes or narrow CI runs as full completion.

## What Changes

- Establish one frozen C00 starting identity and one ordered C04-C12 acceptance path for compact FlowGuard runtime, model, map, consumer, test, measurement, and delivery evidence.
- Make native model-case producers return explicit typed results, bind every retained producer to a current owner, and reject stdout/global-state inference and synthetic qualification paths.
- Make the two selected public map reads use the accepted writer-bound index and selected shards, with exact zero-producer/zero-write read behavior and bounded selected-slice cost.
- Reconcile current source inputs, model candidates, relations, recursive leaf identities, retired wrappers, and protection owners before accepting the self-model; preserve stale, unmapped, and pending states.
- Complete lazy domain routing, public exports, independent consumer staging/install/rollback, and current installation parity without compatibility or fallback routes.
- Migrate the retained test and protection inventory, repair CI collection/full-owner accounting, and add the six public operations, map-growth, recursive, and cross-Guard independence journeys.
- Freeze versions, source/test/config/toolchain identities, native/self evidence, and measurement fixtures only after current model acceptance; keep final pytest, packaging, and future patch release as separate gates.

## Capabilities

### New Capabilities

- `compact-runtime-acceptance`: Cross-cutting acceptance contract for C00-C13, covering current native evidence, self-model/map currentness, compact public behavior, protected test inventory, consumer independence, measurement, and delivery freeze.

### Modified Capabilities

No existing capability is replaced by this change. The new acceptance capability consumes the existing `flowguard-closure-contract`, `authoritative-model-system`, `model-test-alignment`, `test-evidence-mesh`, `flowguard-skill-suite-distribution`, and `development-process-flow` contracts; any requirement delta is recorded in the new capability so historical changes remain immutable.

## Impact

The implementation scope is limited to the FlowGuard repository's native runner, lifecycle/release verification, model authority and map reader/writer, recursive hierarchy, route/export/installation surfaces, retained protection tests, CI owner configuration, and delivery evidence. It does not alter the historical OpenSpec changes, the already published `v0.69.5` tag/release, the user's installed skill, or GitHub publication. SkillGuard integration is an external acceptance dependency and is coordinated by the same-named change in the SkillGuard repository.



## 2026-09-22 audit delta

The earlier checked receipts describe the historical v0.69.6 state and are not current proof for the next patch. This change remains open until the direct-current compact contract is revalidated after the final source edits. The current public surface is exactly `read`, `change`, and `release`; retired commands, route catalogs, migration metadata, aliases, compatibility readers, and fallback paths are removed rather than interpreted. The selected-read/owner evidence, current model or contract identity, one final Windows 3.12 full-suite owner, installation parity, and release identity must all be re-established on one frozen source revision. Documentation and CI are part of that frozen source identity.
