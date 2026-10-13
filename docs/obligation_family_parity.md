# Obligation Family Parity

Obligation Family Parity prevents a narrow proof from being promoted into a
family-level claim. Use it when several model obligations are the same kind of
promise, but one member already has a stronger mechanism or provenance than the
others.

Typical examples:

- one workflow persists a durable reconciliation record while a sibling only
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

This catches the class of failure where one route had durable reconciliation
evidence,
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
-> review_model_test_alignment(...) with the family rows in the same plan
-> run the models and tests that `python -m flowguard change` lists
```

ContractExhaustionMesh defines the stable observed and same-class case ids and
their executable oracles. It expands only declared
family members and current canonical affected relations. A suspected related
surface with no current relation remains an explicit model/relation gap; it
does not start a second repository-wide scan or a parallel completion gate.

## Freshness

Family evidence is only current while the files it exercised are unchanged.
`python -m flowguard map check` reports mapped models whose files drifted since
the map was confirmed, and `python -m flowguard change` lists which models and
tests an edit requires rerunning. Mark rows for those members stale (or rerun
them) before reporting the family as covered.

## Boundary

This helper is not the canonical bad-case generator. It defines the family and
checks family evidence parity; ContractExhaustionMesh creates the stable
bad-case ids and executable oracles. It also does not replace Model-Miss
Review, Model-Test Alignment, or TestMesh.
