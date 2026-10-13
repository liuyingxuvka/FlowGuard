# Modeling Protocol

FlowGuard keeps one current map of the software it describes in
`.flowguard/map.json`: components, owned files, entrypoints, side effects,
dependencies, and the tests and models bound to each component. Git is its
history. This document defines the public operation boundary; detailed subject
material lives in the selected capability guide.

## Public operations

The daily lifecycle operations are `read`, `change`, and `release`. Starter
model files come from `template`, and every lower-level map command lives under
`python -m flowguard map <command>`.

### `read`

Use `read` to understand the software before touching it:

```powershell
python -m flowguard read --root <target-project>
python -m flowguard read --root <target-project> --component <id>
python -m flowguard read --root <target-project> --find <words>
```

`read` writes nothing. It prints the map as compact text, one component in
detail, or the component that already owns a responsibility. A component marked
`STALE` has owned files that changed since its description was last confirmed;
treat its description as unverified until you re-read the code.

### `change`

Use `change` after editing source, models, or tests:

```powershell
python -m flowguard change --root <target-project>
python -m flowguard change --root <target-project> --base <git-ref> <files...>
```

It checks the map against the code and lists the directly affected components,
their dependents, and exactly the models and tests to run. Run what it lists;
the listing is a plan, not a result. When it reports `REVIEW <component>`, re-read
the owned files, update the description if behavior changed, then
`python -m flowguard map confirm <component>`.

Per-element good, bad, and draft evidence is required only when the work is an
explicit architecture reduction or a candidate comparison. State the protected
failures, current implementation, oracle, and inputs used by the selected
checks.

### `release`

Use `release` as the release gate:

```powershell
python -m flowguard release --root <target-project>
```

It runs the strict map check (stale or draft components become errors), the
architecture review errors, and every model. It does not turn a missing result
into pass and it does not publish a Git tag or GitHub release.

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

Every check reports `pass`, `fail`, `blocked`, `not_run`, `skipped`, stale, or
scoped states. A checkbox, directory listing, source summary, package version,
or parent summary is not evidence that a model or test ran. A failed or
incomplete run cannot become pass because a later summary looks clean.

Proof is running the models and tests: `python -m flowguard map models` runs the
executable models, and the test command printed by `change` runs the affected
tests. When a covered source file, model, or test changes, the earlier result is
stale; `map check` shows which component descriptions no longer match their
fingerprint, and `change` shows what to rerun.

## Selecting subject material

Start with `python -m flowguard read` and
`.agents/skills/flowguard/references/route_index.md`. After the task names a
subject, load only its guide and explicitly named dependencies:

- `architecture-reduction/protocol.md` for an explicit contraction or retirement;
- `behavior-commitment-ledger/protocol.md` for observable promises and owners;
- `code-structure-recommendation/protocol.md` for a requested structure proposal;
- `contract-exhaustion-mesh/protocol.md` for declared finite boundary coverage;
- `development-process-flow/protocol.md` for staged lifecycle and release order;
- `existing-model-preflight/protocol.md` for finding the model that already covers a behavior;
- `field-lifecycle-mesh/protocol.md` for field/schema/payload lifecycle;
- `model-mesh/protocol.md` for parent/child model topology;
- `model-miss-review/protocol.md` for a post-green behavior miss;
- `model-test-alignment/protocol.md` for model/code/test bindings;
- `model-topology-hazard-review/protocol.md` for explicit topology hazards;
- `structure-mesh/protocol.md` for existing structure ownership;
- `test-mesh/protocol.md` for large or layered validation ownership;
- `ui-flow-structure/protocol.md` for UI interaction behavior.

These guides live under `.agents/skills/flowguard/references/domains/`. They
are subject references used inside the three operations, not extra public
skills or commands. `python -m flowguard template --list` shows the starter
model files that go with them. If the subject cannot be selected clearly, stop
and ask instead of guessing.

## Engine preflight

Before claiming executable evidence, connect the real check engine:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If this fails, record the selected operation as blocked or partial. Do not
create a local mini-framework or infer proof from prose. Keep the source root,
interpreter, and toolchain visible in the result.
