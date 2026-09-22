# Modeling Protocol

FlowGuard keeps one current information map for the software it describes. The
map records behavior, state, ownership, relations, code and test bindings, and
the evidence that is current for each declared boundary. This document defines
the public operation boundary; detailed subject material lives in the selected
domain protocol.

## Public operations

The only public lifecycle operations are `read`, `change`, and `release`.

### `read`

Use `read` to inspect an accepted current model and one selected subject or
page:

```powershell
python -m flowguard read --root <target-project> --request read.json --json
```

The request must identify the target, selected subject, accepted identity, and
page budget. `read` creates zero producers and zero writes. It does not refresh
the current pointer, execute a native owner, install a projection, or publish.
A missing, ambiguous, stale, or contradictory input is a typed rejection.

### `change`

Use `change` for an explicit source, model, contract, or workflow change:

```powershell
python -m flowguard change --root <target-project> --request change.json --json
```

Freeze the affected owner closure before execution. An ordinary change runs the
real protected-failure native checks and program-derived structure coverage
owned by the selected model. It does not create an additional evidence bundle
merely because the route is non-trivial.

Per-element good, bad, and draft evidence is required only when the request
explicitly declares an architecture reduction or a candidate comparison. The
request must state the protected failures, current implementation, oracle,
inputs, owner, and acceptance boundary used by the selected checks.

### `release`

Use `release` to verify an already accepted current and its declared projection:

```powershell
python -m flowguard release --root <target-project> --request release.json --json
```

`release` consumes exact current evidence and reports source, model,
installation, privacy, platform, and not-run boundaries. It does not turn a
missing result into pass and it does not publish a Git tag or GitHub release.

## Minimal model

For a finite behavioral boundary, use:

```text
Input x State -> Set(Output x State)
```

Declare the relevant inputs, states, outputs, side effects, terminal results,
invariants, and protected failures. Keep the model inside the real boundary;
an unknown or omitted behavior remains an explicit gap. A model result supports
only the scope and evidence it actually covers.

## Evidence rules

Every operation reports `pass`, `fail`, `blocked`, `not_run`, `skipped`, stale,
or scoped states with the owner and identity that produced it. A checkbox,
directory listing, source summary, package version, or parent summary is not
leaf evidence. A failed or incomplete process cannot become pass because a
later summary looks clean.

Changing a route name, admission condition, or obligation requires fresh
admission and plan identity. If the concrete check, input, dependency,
toolchain, and environment are unchanged, the leaf execution key remains
reusable within the same maintenance unit; a route rename must not create a
duplicate producer.

Performance and installation facts belong in one acceptance result with two
sections. Both sections reference the same frozen source identity and retain
their own exact details, counters or transaction facts, privacy checks, and
platform boundaries.

## Selecting subject material

Start with the accepted current model and
`.agents/skills/flowguard/references/route_index.md`. After the request names a
subject, load only its protocol and explicitly named dependencies:

- `architecture-reduction/protocol.md` for an explicit contraction or retirement;
- `behavior-commitment-ledger/protocol.md` for observable promises and owners;
- `code-structure-recommendation/protocol.md` for a requested structure proposal;
- `contract-exhaustion-mesh/protocol.md` for declared finite boundary coverage;
- `development-process-flow/protocol.md` for staged lifecycle and release order;
- `existing-model-preflight/protocol.md` for current model ownership;
- `field-lifecycle-mesh/protocol.md` for field/schema/payload lifecycle;
- `model-mesh/protocol.md` for parent/child model topology;
- `model-miss-review/protocol.md` for a post-green behavior miss;
- `model-test-alignment/protocol.md` for model/code/test bindings;
- `model-topology-hazard-review/protocol.md` for explicit topology hazards;
- `structure-mesh/protocol.md` for existing structure ownership;
- `test-mesh/protocol.md` for large or layered validation ownership;
- `ui-flow-structure/protocol.md` for UI interaction behavior.

These are subject references inside the three operations. They are not extra
public skills, route commands, execution profiles, compatibility readers,
aliases, migration paths, or fallback routes. If the subject or required
identity cannot be selected exactly, stop with a blocker and zero writes.

## Engine preflight

Before claiming executable evidence, connect the real check engine:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If this fails, record the selected operation as blocked or partial. Do not
create a local mini-framework or infer proof from prose. Keep the source root,
interpreter, toolchain, and evidence identity visible in the result.
