## Context

`flowguard.__init__` is the public compatibility facade for the package. It already declares the public API in four groups through `API_SURFACE`, but it also maintains a long explicit `__all__` list that repeats nearly all grouped names plus a small set of metadata and compatibility constants. This duplicates ownership of the same public surface and creates avoidable review burden for every new model, helper, or release route.

The first reduction pass targets that duplicate declaration only. The package facade stays in place, imports remain eager, and public names are not removed.

## Goals / Non-Goals

**Goals:**

- Replace the hand-maintained bulk `__all__` declaration with a derived declaration from `API_SURFACE` and a small explicit supplement.
- Preserve every existing `flowguard.__all__` name, package attribute, CLI command, template command, schema version, and package metadata version.
- Capture FlowGuard Architecture Reduction, StructureMesh, DevelopmentProcessFlow, and TestMesh evidence before claiming the contraction complete.
- Sync the shadow workspace and editable install after implementation.

**Non-Goals:**

- Splitting `flowguard/templates.py` in this pass.
- Removing the broad public `flowguard` facade.
- Changing command names, JSON template envelopes, generated template file paths, OpenSpec archive contents, or package version.
- Reclassifying the exported names between `CORE_API`, `MODELING_HELPER_API`, `REPORTING_HELPER_API`, and `EVIDENCE_API`.

## Decisions

1. **Derive `__all__` from the existing grouped API.**
   `API_SURFACE` is already tested as the canonical grouped public API. The implementation should keep the four groups and derive `__all__` by de-duplicating those group tuples plus an explicit metadata/export supplement.

2. **Keep a small explicit supplement for compatibility names outside API groups.**
   Current `__all__` has a small number of names that are intentionally public but not part of the grouped API contract, including `API_SURFACE`, group tuple names, selected proof-artifact constants, legacy-path constants, and `RISK_INTENT_FIELDS`. These should remain explicit so their compatibility intent stays visible.

3. **Use before/after parity instead of semantic rewrites.**
   The contraction does not change behavior; it removes duplicate declaration. The direct proof is a before/after public name snapshot, targeted API tests, import checks, and broad regression evidence.

4. **Defer larger file splits.**
   `flowguard/templates.py` is large, but splitting it changes module loading and template fixture risk. It should be a later StructureMesh pass after this facade contraction proves the safe pattern.

## Risks / Trade-offs

- Public name accidentally drops from `__all__` -> compare before/after export snapshots and run `tests/test_api_surface.py`.
- API groups and `__all__` order change unexpectedly -> keep stable group order and de-duplication order; add a test for supplement names.
- Refactor overclaims release readiness -> record broad regression artifacts and keep package version unchanged.
- Shadow workspace drifts -> copy the changed source set to the shadow workspace and verify imports/targeted tests there.
