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
  ContractExhaustionMesh case ids downstream. The declared family members,
  mechanism, exclusions, and current canonical relations form the finite
  denominator; this helper does not search for additional surfaces.

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

## Finite Same-Class Cases

Family parity answers whether a declared shared claim is covered now. After a
real miss, related coverage follows one bounded path:

```text
observed miss -> FamilyBadCaseSeed
-> family_bad_case_seed_to_contract_cases(...)
-> review_contract_exhaustion(...)
-> repair/cover every required canonical case
-> ModelMaturation and model-code-test alignment
-> feed the one current maturation result into the Risk Evidence Ledger
```

ContractExhaustionMesh is the sole current owner of the stable observed and
same-class case ids and their executable oracles. It expands only declared
family members and current canonical affected relations. A suspected related
surface with no current relation remains an explicit model/relation gap; it
does not start a second repository-wide scan or a parallel completion gate.

## Risk Evidence Ledger

`RiskEvidenceRow` can require a family gate by adding
`RiskEvidenceGate(RISK_GATE_FAMILY, "family:...")` to its `gates` list. The
gate carries the evidence id, current flag, confidence, and scoped reasons.

The ledger blocks missing, stale, or blocked family gates. A scoped family gate
downgrades the final ledger decision unless scoped confidence is explicitly
allowed.

For a bug-repair claim, the ledger consumes the one current ModelMaturation
result together with the exact ContractExhaustionMesh case ids, model-code-test
bindings, affected-topology replay, and any scoped gaps. There is no additional
same-shape scan receipt to reconcile.

## Boundary

This helper is not the canonical bad-case generator. It defines the family and
checks family evidence parity; ContractExhaustionMesh creates the stable
bad-case ids and executable oracles. It also does not replace Model-Miss
Review, ModelMaturation, Model-Test Alignment, TestMesh, or the Risk Evidence
Ledger.
