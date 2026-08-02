# ModelMesh Partition Protocol

Load this file only for oversized/incomplete models, parent-child partitioning,
or a changed boundary that can affect siblings. Raw model count is not a
partition signal.

## Inventory

Record each affected model's stable id, model/runner/result paths, protected
failure class, inputs, outputs, incoming/outgoing contracts, state and side
effect ownership, evidence id/tier/freshness, and known gaps. Start from the
observed authority snapshot; targets and experiments remain candidates.

## Target split

Derive the target child layout from a FlowGuard model or model-of-models before
accepting a caller-supplied partition. Name the source model, target child ids,
parent items covered, state and side-effect owner fields, and the reason each
boundary exists. Missing, source-less, prose-only, or coverage-incomplete
derivation blocks broad mesh confidence.

Classify every parent-space item as exactly one of:

- `child`: one child owns it;
- `parent`: the parent owns it;
- `read_only`: a child reads but does not own it;
- `shared_kernel`: one declared kernel owns deliberate sharing;
- `bridge`: one typed child-output/parent-input handoff;
- `out_of_scope`: excluded with rationale.

Unsafe overlapping writes, side effects, failure ownership, or core functional
areas block. Shared reads are allowed. A governed path without one exact owner
blocks before any runner starts; it never becomes a run-all fallback.

## Affected siblings

A sibling is affected when it owns, reads, depends on, or shares a changed
partition item, state write, side effect, invariant, failure mode, or outgoing
contract. Review those siblings and show why all others are unaffected. Child
boundary changes stale every parent/ancestor partition and reattachment record
that consumes the child.

## Split decisions

Review a split when state size is above the declared threshold, a budgeted group
is incomplete, the model carries unrelated responsibilities, direct evidence
is overly broad, or DevelopmentProcessFlow reports `model_too_thick`. The old
thick model remains source/compatibility evidence until the derived children
have current evidence and the parent consumes them.

Completion requires full parent-item disposition, legal ownership, an explicit
split decision, and current evidence or visible gaps. Then load the
reattachment protocol if a child changed, or the closure protocol if a parent
whole-flow claim is requested.
