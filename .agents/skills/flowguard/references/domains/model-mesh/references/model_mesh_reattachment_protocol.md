# ModelMesh Reattachment Protocol

Load this file only when a child model or child evidence changes and a parent
or sibling still depends on that boundary.

## Exact reattachment

For each changed child record:

- child model id and exact current evidence/receipt id and fingerprint;
- accepted input classes and emitted output classes;
- state fields and side effects the child owns;
- outgoing guarantees or contract ids consumed by parent/siblings;
- current runtime-path evidence ids when the child represents real code;
- parent/sibling consumer ids and a rationale for the handoff.

Block when the child is locally green but a consumer did not consume its new
receipt, consumed an older receipt, or disagrees about inputs, outputs, state,
side effects, runtime paths, or outgoing guarantees. A green bug instance does
not prove the bug class: Model-Miss Review owns the observed miss and same-class
case; ModelMesh owns reattachment and affected siblings.

## Evidence semantics

Keep `candidate_only`, `abstract_green`, `hazard_green`,
`live_current_green`, `conformance_green`, and `mesh_green` distinct. Abstract
green is not live permission when runtime or conformance evidence is required.
Running/background progress is liveness only; consume final result, exit,
metadata, and freshness identity.

## Portable refinement

When a handoff crosses a process/tool boundary, consume one current
`flowguard.portable_refinement.v1` binding. It must map reachable child states,
transitions, initials, terminals, and legal stutters and show no stronger child
assumptions or weaker guarantees. A descriptive edge, matching label,
child-local receipt, or prompt statement is not refinement evidence.

For hierarchical interaction risk, emit a typed composite-candidate handoff
with exact child fingerprints, relations/changed roots, affected siblings, a
current property owner or `owner_missing`, and current system/slice receipt
references. Ordinary peer composition bypasses ModelMesh, and ModelMesh never
executes the joint portable graph.

Completion requires current parent-consumed child identity, stable handoff
contracts, affected-sibling review, current runtime/conformance evidence when
required, and explicit non-pass gaps. Load the closure protocol only for a
whole-flow parent claim.
