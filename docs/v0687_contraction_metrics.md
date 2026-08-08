# FlowGuard v0.68.7 contraction metrics

This note records one read-only comparison between immutable commit
`fa8a9a4d9280cea6128e9d23517fe67533424e5e` and the v0.68.7 candidate working
tree. It is a measurement artifact, not model authority, a contraction proof,
or a release receipt.

## Validation-orchestration contraction

Two full-tier, single-worker model-regression runs measured the validation
framework before and after invocation-local observation contraction. Both
runs selected all 51 current model owners and passed with no skipped model.
The optimized run executed 49 native model producers and reused only 2 exact
current receipts, compared with 44 executions and 7 reuses in the earlier
run, so the improvement was not produced by reducing semantic coverage or
increasing reuse.

| Metric | Earlier full run | Optimized full run | Change |
| --- | ---: | ---: | ---: |
| launcher wall time | 764.1 s | 604.9 s | -159.2 s (-20.83%) |
| report-owned elapsed time | 617.468 s | 550.465 s | -67.003 s (-10.85%) |
| native child-time sum | 398.875 s | 530.640 s | +131.765 s |
| initial complete source observation | 61.422 s | 23.484 s | -37.938 s |
| final complete source observation | 58.201 s | 19.016 s | -39.185 s |
| parent composition | 67.171 s | 12.766 s | -54.405 s |
| receipt reconciliation | 6.809 s | 8.347 s | +1.538 s |

The increase in native child time and receipt reconciliation is expected:
five more model producers executed and therefore five more fresh leaf receipts
needed reconciliation. The hard acceptance evidence is structural rather than
timing-only: the optimized report records exactly two complete repository
observations, zero per-leaf source-current rebuilds, zero per-leaf receipt-store
scans, and exactly one batch receipt reconciliation. Literal owner input paths
are projected by direct lookup; only actual glob patterns traverse the shared
manifest. This retains necessary native model work while preventing the
framework from rediscovering the same repository and evidence state for every
model.

The immutable optimized report is
`.flowguard/evidence/model-regressions/v0687-observation-prearchive-parent-optimized/report.json`
with result fingerprint
`sha256:fdf89ee0d05d95846a7735c3efc6e32725d2621962594128e65404197393e8c6`.
Timing remains diagnostic because machine load can vary; the operation counts
and exact current identities are the acceptance boundary.

## Boundary and method

The current-runtime corpus contains:

- every Python file in `flowguard/`;
- the `model.py` and `run_checks.py` files of every active entry in
  `.flowguard/model-regression-manifest.json`; and
- `scripts/run_flowguard_model_regressions.py` for the executable-file count.

Archived OpenSpec changes, old model snapshots, receipts, adoption logs,
tests, documentation, skills, and ignored `.flowguard/evidence` output are
immutable history or supporting material and are not counted as current
runtime. Lexical-token counts intentionally exclude the regression orchestrator
and use Python `tokenize` after removing comments and layout-only token kinds;
this reproduces the published baseline value of 867,087 exactly.

The current Python implementation provider observed every corpus file once.
That one observation was projected into the implementation inventory and then
consumed by `derive_self_reduction_universe`; no second optimizer or repository
scanner was introduced. `build_flowguard_self_path_quality_material` supplied
the current model state/transition and bounded-projection measurements.

State and transition counts use one additional isolated comparison boundary.
Commit `fa8a9a4` was materialized with `git archive` and imported with that
commit's own `flowguard` package, so all 65 historical models could use the
symbols that existed with them. The same provider-selection rules were then
applied independently to both sides: prefer non-broken executable `Workflow`
objects, otherwise use an explicit contract export, otherwise project the
native runner's reachable owner-call graph. The current-side replay reproduced
the canonical 166-state/114-transition result exactly. No historical manifest,
model, compatibility reader, or fallback was added to the current runtime.

The source identities for the successful comparison were:

| Side | Corpus identity |
| --- | --- |
| immutable baseline | `sha256:03a73dbf0fcaf13f221935c7fd1d8aec3ce80addee266964a898361df3a62253` |
| candidate working tree | `sha256:9c50d2ca7c933e0ebc31cfebf33f017ea33556f32aae1b079a35c67a6713694d` |

Any later change to a corpus member invalidates the candidate-side numbers and
requires the same measurement to be rerun. A docs-only change does not alter
this corpus identity.

## Comparable results

| Metric | `fa8a9a4` | candidate | Change | What it means |
| --- | ---: | ---: | ---: | --- |
| current executable corpus files | 303 | 283 | -20 (-6.600660%) | Fewer current runtime/self-model files |
| active model owners | 65 | 51 | -14 (-21.538462%) | Fewer independent current model paths |
| projected model states | 193 | 166 | -27 (-13.989637%) | Fewer current state positions across the same provider-selection rule |
| projected model transitions | 130 | 114 | -16 (-12.307692%) | Fewer current transition steps across the same provider-selection rule |
| significant Python lexical tokens | 867,087 | 1,055,846 | +188,759 (+21.769326%) | The remaining direct-current DNA became more detailed; this is not a whole-code shrink |
| implementation surfaces observed | 6,564 | 7,332 | +768 (+11.700183%) | More code behavior is explicitly visible to the current provider |
| `if` / `match` / `try` branch sites | 8,558 | 11,244 | +2,686 (+31.385838%) | The complete static branch denominator grew; fewer owners does not mean fewer internal decisions |
| unbound branch sites | 88 | 72 | -16 (-18.181818%) | A larger share of branch syntax is attached to an observed implementation surface |
| dynamic/reflection operations | 595 on 226 surfaces | 922 on 306 surfaces | +327 operations | Static cost increased and must remain governed by current selector contracts |
| validation-named surfaces | 358 | 414 | +56 (+15.642458%) | Validation coverage moved into the direct current owners; this is a review denominator, not proof of duplicate validation |
| repeated validation-shape groups | 2 groups / 9 surfaces | 2 groups / 9 surfaces | unchanged | Structural resemblance alone did not justify deletion |
| reducer signal operation estimate | 32,862 | 41,003 | +8,141 (+24.773294%) | Diagnostic static work estimate across all signalled surfaces |
| reducer signal payload estimate | 1,594,340 bytes | 1,800,096 bytes | +205,756 (+12.905403%) | Diagnostic analysis payload, not an AI prompt or runtime memory measurement |

The correct conclusion is therefore structural contraction, not blanket size
contraction: current owner/file paths became fewer, while the surviving DNA,
bindings, validation ownership, and visible branch surface became deeper.

The isolated state/transition pass covered all models on both sides with zero
load failures. The baseline provider mix was 45 workflow, 3 contract-export,
and 17 native-runner models; the candidate mix was 39 workflow, 3
contract-export, and 9 native-runner models. These counts are a reproducible
measurement of the two immutable source identities, not an authority migration
and not permission for the current runtime to read retired formats.

One local replacement remains a clean like-for-like contraction example. The
old `flowguard/model_similarity.py` was 2,468 lines and 16,359 significant
tokens. Its current internal `flowguard/canonical_relation.py` handoff is 256
lines and 1,174 tokens: -2,212 lines (-89.627229%) and -15,185 tokens
(-92.823522%). This comparison is local to that responsibility and does not
describe the whole package.

## Current model and token-facing projections

The current path-quality compiler closed all 51 current owners with no global
or material-review gap. Across those exact owners it projected 166 states, 114
transitions, 129 function blocks, 730 fields, 129 outputs, and 495 validation
bindings. Its direct-current v2 audit also materialized an exact 51-row typed
deep-trigger census: all 51 required model ids were present, zero were blocked,
and every explicit-request, declared-candidate, path-design-miss, high-cost,
and release-critical input was false or zero for this exact measurement. The
result therefore contained zero findings and zero deep triggers, and all 51
models closed as `single_clear_path`. This proves the trigger decision was made
for every current model rather than inferred from an empty global list. It does
not license a later caller to ignore a current trigger or reuse this result
after any bound identity changes.

For this same current material:

| Projection | Canonical JSON bytes | Boundary |
| --- | ---: | --- |
| full path-quality audit material | 3,043,369 | Includes every per-model fact, witness, typed trigger-census row, subject, and result |
| revision wire material | 129,098 | Subjects and results consumed by the revision path |
| compact material review | 10,602 | Counts, identities, verified owners, and gaps only |

The compact review is 99.651636% smaller than the full audit material
(287.056121 times smaller), while preserving the 51-owner denominator and
terminal gap result. This proves bounded emission size, not zero construction
cost: the measurement compiled the full current material before serializing
the compact review.

The earlier recorded `ModelRevisionPlan` sample remains a separate immutable
example: 364,497 characters in full form versus 2,604 in compact form
(-99.285591%). It was a pre-finalization read-only sample, not a universal token
claim and not the candidate identity above.

## Deliberately non-comparable or still pending

- The metric inventory intentionally did not supply the real self-blueprint's
  dynamic-selector declarations. Its inventory review is therefore blocked
  (226 historical and 306 candidate dynamic-surface findings). Branch and
  operation denominators remain useful static measurements, but this artifact
  cannot claim release cleanup readiness.
- `repeated_reference_bytes_avoided`, canonical shared-evidence physical size,
  and complete deep-detail load avoidance require the exact live
  self-blueprint/behavior report. They remain `not measured` here instead of
  being inferred from source size or tests.
- Validation-named surfaces and repeated shapes are candidates for review, not
  proof of equivalent observable behavior. Only the live Architecture
  Reduction audit plus current necessity/consumer/equivalence evidence may
  authorize retain, merge, delegate, remove, or explicit-on-demand actions.
- OpenSpec `retire-redundant-historical-routes` tasks 4.6-4.8 and
  `bound-self-audit-materialization` task 5.5 are not closed by this note alone.
  Task 4.6 may cite these measured costs. Tasks 4.7-4.8 and 5.5 still require
  the same candidate authority's complete live compact self-audit, terminal
  candidate/step dispositions, current proof-store results, and affected-owner
  regressions.

## Recalculation recipe

1. Materialize `fa8a9a4` with `git archive` into an isolated temporary
   directory; do not change or activate it.
2. Read each side's manifest only to obtain its active model and runner path
   denominator. The historical v3 manifest is measurement input only and does
   not become a runtime-readable format.
3. Build the exact corpus above and fingerprint the sorted
   `{path, source_file_fingerprint}` rows.
4. For the state/transition comparison, import each side in its own isolated
   source tree and apply the same current provider-selection order: executable
   workflow, explicit contract export, then reachable native-runner owner-call
   graph. Require complete model coverage and zero import failures on both
   sides; never load the historical manifest or models through the current
   runtime.
5. For every corpus file, call
   `discover_python_implementation_surfaces` once, then reuse that immutable
   observation through `project_python_implementation_observation` and
   `build_implementation_surface_inventory`.
6. Pass the resulting inventory to `derive_self_reduction_universe`; read its
   branch denominator and member cost fields. Derive dynamic and repeated
   validation-shape counts only from those same observed surfaces.
7. Count significant tokens with Python `tokenize`, excluding `ENCODING`,
   `ENDMARKER`, `NL`, `NEWLINE`, `INDENT`, `DEDENT`, and `COMMENT`.
8. On the current side, run
   `build_flowguard_self_path_quality_material` and serialize its full audit,
   revision material, and compact review with FlowGuard canonical JSON.
9. Recompute the candidate corpus fingerprint immediately before citing the
   result. A mismatch invalidates all candidate-side measurements.

This recipe performs no model execution, authority activation, repository
write, installation, or release action. The later live self-audit and release
validation remain their own foreground evidence owners.
