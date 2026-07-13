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

When a route gains a new required contract object, case generator, receipt,
gate, or downstream handoff, update the route profile at the same time as the
runtime helper. The profile is the AI-facing checklist after route selection.
For ContractExhaustionMesh, that checklist must mention model axes,
interaction groups, generated combination cases, coverage shards, coverage
receipts, coverage universes, actionable oracle feedback, observed-problem
backfeed, generic fault profiles, and the MTA/TestMesh/ModelMesh/RiskLedger
handoffs that consume them. The compact `ROUTE_STARTER_API` should stay small;
detailed objects belong in route profiles, advanced APIs, docs, and skill
references.

## Field Layers

Field-heavy work should first use `default_field_layer_profiles()`:

- `core`: id, status, decision, current, and route owner fields stay visible.
- `route_owned`: specialist route fields expand only when that route runs.
- `shared_evidence`: proof/freshness/scope/test reuse objects are summarized
  first, then expanded for claim evidence.
- `metadata_display`: display and metadata fields are accounted but scoped out
  of high-level behavior models unless they affect behavior.
- `replacement_disposition`: old fields, aliases, wrappers, and alternate
  success paths require delete, migrate, block, delegate, repair, replace, or
  scope-out evidence.

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
  registry, internal helper inventory, advanced API grouping, and replacement
  disposition supplement.

Any future split should keep exactly one public entrypoint as the active path
after StructureMesh parity evidence and focused API tests pass.

## Validation Boundary

The parent self-maintenance model checks only that the route graph, AI entry
profiles, field layers, child reports, install/shadow sync, and git boundary
are current enough for the self-maintenance claim. It does not replace the
specialist route checks or full release evidence.

The model uses the exact 17 canonical skill identities when rehearsing its own
child-report gate, but it does not execute SkillGuard or copy a provider's
verification contract. The SkillGuard parent owner verifies real skill
receipts, while DevelopmentProcessFlow and the Spec Work Package own provider
session, receipt freshness, and archive closure. Unrelated child identities or
wrong-plane completion authority cannot satisfy the self-maintenance gate.

This is a gate-semantics check, not the child evidence itself:

```text
self-maintenance model green
!= SkillGuard, Spec Work Package, or release evidence is current
```

The final DevelopmentProcessFlow/TestMesh claim consumes the real terminal
owner receipts through the Spec Work Package. A cross-change-safe full check
runs once for one frozen execution identity; each downstream change receives a
consumer-local portable reference and a light aggregate receipt, not a copied
receipt or a second execution. In a shadow workspace without `.git`, an empty
mutation list is not proof that files stayed unchanged; use an explicit
before/after source hash manifest and rerun only a child made stale by a later
functional input change.
