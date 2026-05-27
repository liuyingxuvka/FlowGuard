# DevelopmentProcessFlow

DevelopmentProcessFlow reviews a staged development lifecycle as a stateful
process: which steps run, which artifacts changed, which validation evidence
covered which versions, and whether the agent can safely continue or claim
done. It also checks whether a release, archive, or publish claim still has
current evidence.

It is a sibling helper route. It can reference evidence ids produced by
ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or
Conformance Adoption, but it does not inspect or supervise those route
internals.

## Public API

```python
from flowguard import (
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)

plan = DevelopmentProcessPlan(
    "checkout-lifecycle",
    artifacts=(
        ProcessArtifact("requirements.checkout", "requirement", "2"),
        ProcessArtifact("code.checkout", "code", "4"),
        ProcessArtifact("tests.checkout", "test", "1"),
    ),
    actions=(
        ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
        ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
        ProcessAction("claim-release", action_type="claim_release", required_evidence_ids=("unit-pass",)),
    ),
    evidence=(
        ProcessEvidence(
            "unit-pass",
            evidence_kind="unit",
            producer_route="test_mesh_maintenance",
            status="passed",
            covers_artifacts=("code.checkout",),
            verifier_artifacts=("tests.checkout",),
            covered_versions={"code.checkout": "3", "tests.checkout": "1"},
            produced_by_action_id="run-unit",
        ),
    ),
    validation_requirements=(
        ValidationRequirement(
            "unit-current",
            required_artifact_ids=("code.checkout",),
            required_evidence_kinds=("unit",),
            evidence_ids=("unit-pass",),
        ),
    ),
)

report = review_development_process_flow(plan)
print(report.format_text())
```

The report flags stale evidence because `unit-pass` covered `code.checkout@3`
while the current artifact is `code.checkout@4`.

## What It Checks

- non-trivial staged development or modification sequences such as plan, edit,
  test, fix, and verify;
- unknown artifact, evidence, validation, and action references;
- out-of-order process dependencies;
- stale evidence after code, test, model, requirement, or direct invalidation;
- verifier changes after validation, such as tests or model files changing;
- explicit upstream freshness rules, such as requirement changes invalidating
  downstream code and validation evidence;
- model-miss repair changes that invalidate earlier alignment evidence, such
  as a new miss classification, same-class generalized case, closure evidence
  role, or test row used to prove closure;
- ambiguous freshness policy for declared upstream/downstream artifacts;
- progress-only background evidence, hidden skipped validation, failed
  evidence, and not-run evidence;
- final done, archive, publish, or release claims that have no current Risk
  Evidence Ledger decision;
- missing V-style validation pairs;
- release-required evidence under routine and release scopes;
- minimum revalidation recommendations.

## Template

Use the starter template in another project:

```powershell
python -m flowguard development-process-flow-template --output .
```

The template writes:

- `.flowguard/development_process_flow/model.py`
- `.flowguard/development_process_flow/run_checks.py`
- `docs/flowguard_development_process_flow.md`

The generated model includes one green lifecycle and one broken lifecycle where
a release claim reuses stale validation evidence after code and requirement
changes.

## Boundary

Use DevelopmentProcessFlow when non-trivial staged development or modification
work has validation, or when development ordering and evidence freshness are the
risk. Skip only for truly single-step work with no meaningful validation or
artifact freshness risk, such as a tiny typo fix, pure explanation, or
formatting-only change. Use TestMesh when the validation hierarchy itself needs
a parent/child split. Use StructureMesh when code structure is being split. Use
Model-Test Alignment when model obligations and test or code-contract evidence
need direct comparison. Use Conformance Adoption when production traces or
install/runtime sync determine confidence.

For final completion claims, DevelopmentProcessFlow should reference the Risk
Evidence Ledger decision as one evidence boundary. If the ledger reports
`risk_evidence_full_confidence`, the process may consume that evidence subject
to freshness rules. If it reports scoped confidence, stale proof,
internal-path-only evidence, progress-only evidence, or a missing route handoff,
the process claim remains scoped or blocked until the owning route supplies
current proof.

When the final claim depends on layered parent/child model confidence,
DevelopmentProcessFlow should reference the layered proof report as a sibling
evidence id. Parent coverage edits, child ownership or contract edits, child
evidence-id changes, and leaf code/test/observation edits stale the related
layered proof rows until they are rerun and reattached.

When the final claim closes a model miss, DevelopmentProcessFlow should include
Model-Test Alignment as a required validation pair for the repaired model
obligation and the observed/same-class test rows. If the same-class evidence is
large, slow, background, layered, or release-only, it should also include
TestMesh evidence and keep routine confidence scoped until current release
evidence exists.

Before done, release, archive, publish, or production-confidence claims,
DevelopmentProcessFlow should review direct model/test evidence with
`review_auto_mesh_splits()` when size, pending states, slow duration, broad
obligation coverage, background progress-only logs, or release-only scope could
hide the need for ModelMesh or TestMesh. A required split keeps the lifecycle
claim blocked or scoped until the owning mesh route supplies current evidence.

When a lifecycle claim depends on an AI-built plan, a project-specific evidence
adapter, a post-green false-negative repair, or known-bad mutation probes,
DevelopmentProcessFlow should also consume the plan-intake and typed claim-chain
reports as current evidence. `review_plan_intake_completeness(...)`,
`review_evidence_adapter_conformance(...)`,
`review_false_negative_backpropagation(...)`, `review_plan_mutations(...)`, and
`review_flowguard_claim_chain(...)` keep plan-only, model-only, or alignment-only
results from being reported as production confidence.
