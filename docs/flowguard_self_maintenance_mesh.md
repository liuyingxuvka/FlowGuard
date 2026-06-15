# FlowGuard Self-Maintenance Mesh

FlowGuard self-maintenance is the parent route for keeping FlowGuard usable by
AI agents without flattening every helper, field, and proof object into the
first-read surface.

## Route Chain

The intended AI path is:

```text
user intent
-> ExistingModelPreflight consumes model-angle or similarity evidence when needed
-> FlowGuard self-maintenance route profile
-> DevelopmentProcessFlow consumes post-change scan signals
-> owning specialist route evidence
-> Risk Evidence Ledger
-> Closure Contract
```

`FLOWGUARD_ROUTE_API` remains the public-owner route group registry.
`default_flowguard_self_maintenance_plan()` is the first-read helper: it fills
route profiles, public API route group ids, AI entry profiles, and field layer
defaults before review. `default_flowguard_route_profiles()` remains the
compact explanation layer above the registry for specialist overrides. It names
the route trigger, minimal inputs, outputs, evidence owner, template, skill,
role, entry policy, canonical owner, absorption route, cleanup disposition, and
next route.

## Field Layers

Field-heavy work should first use `default_field_layer_profiles()`:

- `core`: id, status, decision, current, and route owner fields stay visible.
- `route_owned`: specialist route fields expand only when that route runs.
- `shared_evidence`: proof/freshness/scope/test reuse objects are summarized
  first, then expanded for claim evidence.
- `metadata_display`: display and metadata fields are accounted but scoped out
  of high-level behavior models unless they affect behavior.
- `compatibility_disposition`: old fields, aliases, wrappers, and fallbacks
  require delete, migrate, block, delegate, repair, preserve, or scope evidence.

## StructureMesh Candidates

This change keeps public owner facades explicit and records split candidates instead of
rewriting large modules immediately:

- `flowguard/ui_structure.py`: candidate child owners are interaction model,
  journey coverage, implementation validation, structure derivation, and text
  hierarchy.
- `flowguard/model_test_alignment.py`: candidate child owners are obligations,
  code contracts, source audit, transition coverage, and binding rows.
- `flowguard/risk_evidence_ledger.py`: candidate child owners are proof rows,
  maintenance obligations, confidence claims, and final ledger findings.
- `flowguard/__init__.py`: candidate child owners are public owner route
  registry, internal helper inventory, advanced API grouping, and compatibility
  supplement.

Any future split should keep the existing public entrypoint as facade until
StructureMesh parity evidence and focused API tests pass.

## Validation Boundary

The parent self-maintenance model checks only that the route graph, AI entry
profiles, field layers, child reports, install/shadow sync, and git boundary
are current enough for the self-maintenance claim. It does not replace the
specialist route checks or full release evidence.
