# Obligation Family Parity

Obligation Family Parity prevents a narrow proof from being promoted into a
family-level claim. Use it when several model obligations are the same kind of
promise, but one member already has a stronger mechanism or provenance than the
others.

Typical examples:

- one workflow persists a durable reconciliation receipt while a sibling only
  records a controller handoff;
- one route has observed-regression and same-class proof while a sibling only
  has the point regression;
- one public surface has external-contract evidence while a sibling only has an
  internal helper test.

The helper asks one concrete question: for every member in the family, does
every required mechanism have current passing evidence from an allowed
provenance source?

## Public API

- `ObligationFamilyMember`: one sibling obligation in the family.
- `ObligationFamily`: the family definition, required mechanisms, allowed
  provenance, and whether external evidence or proof artifacts are required.
- `ObligationFamilyEvidence`: one evidence row for a family member/mechanism.
- `ObligationFamilyParityReport`: the matrix and findings.
- `review_obligation_family_parity(...)`: the executable checker.
- `FamilyBadCaseSeed` and `derive_same_class_bad_cases(...)`: derive sibling
  bad cases from one observed miss so the family can be tested uniformly. For
  canonical coverage, feed the seed through
  `family_bad_case_seed_to_contract_cases(...)` and use the resulting
  ContractExhaustionMesh case ids downstream.
- `AnalogousDefectCandidate` and `review_analogous_defect_scan(...)`: after a
  real miss, scan where the same failure shape may recur and record whether
  each candidate is covered, repair-now, model-upgrade-needed, separate-change,
  or excluded with a reason.

## Evidence Rules

Evidence is not interchangeable just because it passed. A row can be rejected
when it is:

- missing for a required family member/mechanism cell;
- stale, skipped, failed, not run, running, progress-only, or errored;
- internal-path-only while the family requires external evidence;
- produced from a provenance source the family does not allow, such as a manual
  event trying to prove durable reconciliation;
- missing required proof artifacts when the family requires artifact-bound
  proof;
- attached to an unknown family member or mechanism.

Exempt members stay visible in the coverage matrix. They do not need evidence,
but the report still shows that the family confidence is scoped rather than
silently complete when a member is deliberately outside the current claim.

## Model-Test Alignment

`ModelTestAlignmentPlan` can include `obligation_families` and
`family_evidence`. The normal alignment review still checks obligations,
contracts, tests, and boundary observations. The family layer adds one more
gate: related obligations cannot be reported as aligned family coverage unless
the family matrix passes.

This catches the class of failure where one route had durable receipt evidence,
a sibling route had only a manual or controller-level event, and both were
still being treated as the same class of closed work.

## Analogous Defect Scan

Family parity answers whether the declared family is covered now. Analogous
defect scan answers the next model-miss question: after a real bug, where else
could the same failure shape happen?

The scan has three radii:

- `must_scan`: same family, same mechanism, same failure shape. Open candidates
  block broad closure.
- `should_scan`: related surface or adjacent mechanism. Open candidates keep the
  claim scoped unless they are assigned to a separate change or excluded with a
  concrete reason.
- `record_only`: useful risk note that should stay visible but should not pull
  unrelated work into the current repair.

Use this after model misses so a repair does not close on the observed bug
alone. The usual pattern is:

```text
observed miss -> FamilyBadCaseSeed
-> family_bad_case_seed_to_contract_cases(...)
-> review_contract_exhaustion(...)
-> review_analogous_defect_scan(...) for scan disposition
-> repair/cover required canonical cases
-> feed scan confidence into the Risk Evidence Ledger
```

## Risk Evidence Ledger

`RiskEvidenceRow` can require a family gate by adding
`RiskEvidenceGate(RISK_GATE_FAMILY, "family:...")` to its `gates` list. The
gate carries the evidence id, current flag, confidence, and scoped reasons.

The ledger blocks missing, stale, or blocked family gates. A scoped family gate
downgrades the final ledger decision unless scoped confidence is explicitly
allowed.

`RiskEvidenceRow` can also require an analogous defect scan with
`RiskEvidenceGate(RISK_GATE_ANALOGOUS_SCAN, "analogous:...")`.

This is the final-claim hook for the bug-repair case: if the same-shape risk
radius is still unreviewed or blocked, the ledger cannot return full
confidence.

## Boundary

This helper is not the canonical bad-case generator. It defines the family and
checks family evidence parity; ContractExhaustionMesh creates the stable
bad-case ids. It also does not replace Model-Miss Review, Model-Test
Alignment, TestMesh, or the Risk Evidence Ledger.
