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
- ambiguous freshness policy for declared upstream/downstream artifacts;
- progress-only background evidence, hidden skipped validation, failed
  evidence, and not-run evidence;
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
