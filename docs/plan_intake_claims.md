# Plan Intake And Claim Chain

Plan intake and claim-chain helpers guard the boundary before existing
FlowGuard reports are promoted into broad completion or production-confidence
claims. They exist for the failure mode where ModelMesh, TestMesh,
Model-Test Alignment, or Risk Evidence Ledger pass honestly over the structured
rows they were given, but the upstream plan omitted a repeated failure class,
lost adapter evidence, or later overclaimed what a narrow report proved.

These helpers do not parse project files, run tests, or replace the existing
routes. Project adapters still collect raw runtime, log, test, code, and history
facts. FlowGuard checks the structured rows.

```text
plan sources -> intake surfaces -> adapter mappings -> miss backpropagation -> mutation probes -> typed claim chain
```

When the starting point is only a rough idea or short AI-generated plan, first
build `PlanDetail` rows and run `review_plan_detail(...)`. Then use
`plan_detail_to_plan_intake(...)` so source evidence, reviewed risk surfaces,
scoped omissions, and recurring/high-risk history flow into PlanIntake without
being retyped from prose. A green plan-detail review still means "the plan is
structured enough to check"; PlanIntake owns the plan-valid claim.

## Public API

- `PlanIntakeRiskSurface`, `PlanIntakeCompletenessPlan`,
  `PlanIntakeCompletenessReport`, and
  `review_plan_intake_completeness(plan)`: checks that the plan declares current
  source evidence, reviewed in-scope risk surfaces, omitted/out-of-scope
  reasons, and observed/same-class/holdout history for recurring or high-risk
  cases.
- `EvidenceAdapterMapping`, `EvidenceAdapterConformancePlan`,
  `EvidenceAdapterConformanceReport`, and
  `review_evidence_adapter_conformance(plan)`: checks that raw artifacts keep
  identity, freshness, and failure/stale/progress classifications after
  adapter mapping. Known-bad fixture rejection belongs in a dedicated negative
  test or conformance scenario, not in every normal mapping row.
- `FalseNegativeCase`, `FalseNegativeBackpropagationPlan`,
  `FalseNegativeBackpropagationReport`, and
  `review_false_negative_backpropagation(plan)`: checks that a post-green miss
  names the old passing claim, observed failure, cause, would-have-failed-if
  condition, new plan/model item, and closure evidence before closure.
- `PlanMutationCase`, `PlanMutationReviewPlan`,
  `PlanMutationReviewReport`, and `review_plan_mutations(plan)`: checks that
  known-bad mutations fail instead of being accepted by a too-wide plan/model
  path.
- `FlowGuardClaimDependency`, `FlowGuardClaimChainPlan`,
  `FlowGuardClaimChainReport`, and `review_flowguard_claim_chain(plan)`: checks
  that a target scope such as `production_confidence` has current typed support
  from plan intake, runtime replay, risk evidence, adapter conformance,
  false-negative backpropagation, and mutation review when those supports are
  required.

## Minimal Example

```python
from flowguard import (
    CLAIM_SCOPE_PLAN_VALID_ONLY,
    CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
    CLAIM_SCOPE_RISK_EVIDENCE_VALID,
    CLAIM_SCOPE_RUNTIME_REPLAY_VALID,
    FlowGuardClaimChainPlan,
    FlowGuardClaimDependency,
    PlanIntakeCompletenessPlan,
    PlanIntakeRiskSurface,
    review_flowguard_claim_chain,
    review_plan_intake_completeness,
)

intake = review_plan_intake_completeness(
    PlanIntakeCompletenessPlan(
        "submit-plan",
        source_evidence_ids=("runtime:submit", "history:duplicate-submit"),
        risk_surfaces=(
            PlanIntakeRiskSurface(
                "duplicate_submit",
                source_ids=("history:duplicate-submit",),
                evidence_ids=("test:duplicate-submit",),
                recurring=True,
                observed_failure_ids=("obs:duplicate-submit",),
                same_class_case_ids=("same-class:duplicate-submit",),
                historical_holdout_ids=("holdout:duplicate-submit",),
            ),
        ),
    )
)

claim = review_flowguard_claim_chain(
    FlowGuardClaimChainPlan(
        "submit-production-confidence",
        CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
        dependencies=(
            FlowGuardClaimDependency("plan", CLAIM_SCOPE_PLAN_VALID_ONLY),
            FlowGuardClaimDependency("runtime", CLAIM_SCOPE_RUNTIME_REPLAY_VALID),
            FlowGuardClaimDependency("risk", CLAIM_SCOPE_RISK_EVIDENCE_VALID),
        ),
    )
)
```

If runtime replay or risk evidence is missing, the claim-chain report blocks
`production_confidence` even when model-only or plan-only evidence is green.

## Claim Boundary

- `plan_valid_only` means the plan input surface is declared. It is not a
  runtime or production proof.
- `model_valid` means the model path passed for its declared inputs. It is not
  proof that adapters supplied all needed inputs.
- `runtime_replay_valid` and `risk_evidence_valid` are separate dependencies for
  production confidence.
- Scoped dependencies downgrade broad claims to scoped confidence when allowed.
  Stale, missing, not-run, or blocked dependencies block.
