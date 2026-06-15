## Context

FlowGuard already checks model execution, conformance, progress, runtime
binding, topology hazards, model similarity, maintenance routing, and risk
evidence. The missing piece is not a new workflow. The missing piece is a
small, shared description of a business path so the existing checks can tell
whether two modeled routes are doing the same job, competing for the same
input, leaving an old route alive without disposition, or claiming confidence
without a real-code path binding.

The current source checkout has active local work, including self-model runner
hardening. This change must stay narrow: extend existing data structures,
templates, prompts, and tests without replacing the runner or creating a new
route family.

## Goals / Non-Goals

**Goals:**

- Capture business-path identity in model topology, similarity, and runtime
  path evidence.
- Reuse Model Topology Hazard Review as the primary owner for duplicate,
  conflicting, unproven, and legacy business-path hazards.
- Reuse Model Similarity, Runtime Path Evidence, Maintenance Scan, and Risk
  Evidence Ledger as downstream consumers.
- Update prompts, templates, docs, exports, and focused tests so future
  FlowGuard models collect path identity by default.
- Keep the feature deterministic and dependency-free.

**Non-Goals:**

- Do not add a new standalone FlowGuard workflow route.
- Do not infer arbitrary business equivalence from prose alone. The model must
  provide path identity, trigger, terminal, state write, side-effect, or
  equivalence/exclusion metadata for deterministic checks.
- Do not rewrite active self-model runner work.
- Do not claim broad release confidence from docs or metadata alone; current
  executable evidence is still required.

## Decisions

1. **Add a small business-path identity object to topology review.**

   `BusinessPathIdentity` will live with topology hazard review because that
   route already owns future-use hazard inference. The object records path id,
   business intent, trigger, preconditions, expected terminal, state writes,
   side effects, source labels, equivalent paths, exclusive paths, superseded
   old paths, compatibility disposition, and evidence ids.

   Alternative considered: create a separate BusinessPath route. Rejected
   because the user explicitly wants the current workflow strengthened rather
   than a parallel process.

2. **Treat business paths as topology anchors, not only free text.**

   A business path will become an anchor in the topology digest so hazard
   candidates can point at stable ids such as `business_path:renewal_submit`.
   This keeps reports, evidence rows, and candidate actions traceable.

   Alternative considered: store path metadata only in report prose. Rejected
   because unanchored prose cannot drive deterministic checks or maintenance
   routing.

3. **Infer four path-level hazard families inside existing topology review.**

   The existing topology review will add landmarks for duplicate paths,
   conflicting paths, unproven paths, and old/new disposition gaps. These map
   to existing required routes: model maturation, model-test alignment,
   architecture reduction, model similarity, development process flow, and risk
   evidence.

   Alternative considered: fail every duplicate-looking path. Rejected because
   some duplicates are intentional compatibility surfaces; the correct action
   is to require disposition and evidence.

4. **Share the same identity through similarity and runtime evidence.**

   Model signatures will compare business path ids, intents, and terminals so
   sibling models can expose duplicate or false-friend risk. Runtime contracts
   and observations will bind real-code evidence to the expected business path
   so a test does not accidentally prove the wrong path.

   Alternative considered: keep runtime checks at node id only. Rejected
   because the user's failure mode is specifically "the model runs, but it may
   run the wrong useful route."

5. **Route unresolved signals through the existing maintenance scan.**

   Maintenance scan will gain business-path signal names and map them to
   existing owner routes. This makes unresolved path hazards visible during
   normal maintenance without creating a second checklist.

   Alternative considered: require every FlowGuard route to scan every path
   issue itself. Rejected because that would duplicate ownership and increase
   process load.

6. **Synchronize version and local installs after verification.**

   After implementation and tests pass, bump the package version, install the
   editable source, verify import source and exported symbols, sync the shadow
   workspace, and record the adoption evidence. Git synchronization means the
   local Git checkout reflects the upgraded files; committing will only happen
   if it can avoid mixing unrelated pre-existing dirty work.

## Risks / Trade-offs

- **Explicit metadata is required** -> Prompts and templates must ask for path
  identity at model time; the checker will not pretend to understand unstated
  business semantics.
- **False positives for intentional compatibility routes** -> Compatibility
  disposition, `exclusive_with`, `equivalent_to`, and evidence ids let the model
  declare why a duplicate-looking path is acceptable.
- **Existing dirty checkout can blur ownership** -> Keep patches narrow, inspect
  touched files before editing, and avoid committing unrelated existing changes.
- **Runtime path adoption may be gradual** -> Business path fields are optional,
  but when present they participate in alignment review and can block a broad
  confidence claim if mismatched.

## Migration Plan

1. Add data fields and deterministic checks in package code.
2. Update templates, prompts, docs, and API exports.
3. Add focused tests for duplicate, conflict, unproven, legacy disposition,
   model similarity, runtime path mismatch, and maintenance scan routing.
4. Run targeted tests, API/template tests, OpenSpec checks, project audit, and
   FlowGuard package import/version checks.
5. Bump package version, reinstall editable local package, sync the shadow
   workspace, and verify both source and shadow import the same version and
   symbols.
6. Record FlowGuard adoption evidence and final Git status.

## Open Questions

None for implementation. The first version deliberately uses explicit
business-path metadata; deeper semantic inference can be proposed later if real
project evidence shows it is worth the added complexity.
