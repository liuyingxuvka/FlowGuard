"""Claim-scope completeness for runnable UI implementation evidence.

This module is the leaf owner for deciding whether a runnable UI claim is
complete or intentionally scoped.  It deliberately depends only on primitive
evidence-presence inputs so :mod:`flowguard.ui_structure` can remain the public
facade and orchestration owner without creating a reverse import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


UI_IMPLEMENTATION_CLAIM_COMPLETE = "complete"
UI_IMPLEMENTATION_CLAIM_SCOPED = "scoped"
UI_IMPLEMENTATION_CLAIM_SCOPES = (
    UI_IMPLEMENTATION_CLAIM_COMPLETE,
    UI_IMPLEMENTATION_CLAIM_SCOPED,
)

UI_IMPLEMENTATION_EVIDENCE_CAPABILITY_COVERAGE = "capability_coverage"
UI_IMPLEMENTATION_EVIDENCE_OBSERVED_INVENTORY = "observed_inventory"
UI_IMPLEMENTATION_EVIDENCE_VISIBLE_SURFACE = "visible_surface"
UI_IMPLEMENTATION_EVIDENCE_CONTENT_VISIBILITY_PLAN = "content_visibility_plan"
UI_IMPLEMENTATION_EVIDENCE_RUN_EVIDENCE = "implementation_run_evidence"
UI_IMPLEMENTATION_EVIDENCE_BLINDSPOTS = "implementation_blindspots"
UI_IMPLEMENTATION_EVIDENCE_CLASSES = (
    UI_IMPLEMENTATION_EVIDENCE_CAPABILITY_COVERAGE,
    UI_IMPLEMENTATION_EVIDENCE_OBSERVED_INVENTORY,
    UI_IMPLEMENTATION_EVIDENCE_VISIBLE_SURFACE,
    UI_IMPLEMENTATION_EVIDENCE_CONTENT_VISIBILITY_PLAN,
    UI_IMPLEMENTATION_EVIDENCE_RUN_EVIDENCE,
    UI_IMPLEMENTATION_EVIDENCE_BLINDSPOTS,
)


@dataclass(frozen=True)
class UIImplementationClaimScopeFinding:
    """One fail-closed claim-scope finding without UI facade dependencies."""

    code: str
    message: str
    evidence_class: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "evidence_class", str(self.evidence_class))


@dataclass(frozen=True)
class UIImplementationClaimScopeDecision:
    """Pure complete/scoped decision for the six runnable-UI evidence classes."""

    ok: bool
    claim_scope: str
    declared_omitted_evidence_classes: tuple[str, ...] = ()
    actual_omitted_evidence_classes: tuple[str, ...] = ()
    findings: tuple[UIImplementationClaimScopeFinding, ...] = ()
    broad_confidence_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(
            self,
            "declared_omitted_evidence_classes",
            tuple(str(value) for value in self.declared_omitted_evidence_classes),
        )
        object.__setattr__(
            self,
            "actual_omitted_evidence_classes",
            tuple(str(value) for value in self.actual_omitted_evidence_classes),
        )
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "broad_confidence_eligible",
            bool(self.broad_confidence_eligible),
        )

    def finding_codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "claim_scope": self.claim_scope,
            "declared_omitted_evidence_classes": list(
                self.declared_omitted_evidence_classes
            ),
            "actual_omitted_evidence_classes": list(
                self.actual_omitted_evidence_classes
            ),
            "findings": [
                {
                    "code": finding.code,
                    "message": finding.message,
                    "evidence_class": finding.evidence_class,
                }
                for finding in self.findings
            ],
            "broad_confidence_eligible": self.broad_confidence_eligible,
        }


def review_ui_implementation_claim_scope(
    *,
    claim_scope: str,
    omitted_evidence_classes: Sequence[str] = (),
    capability_coverage_present: bool,
    observed_inventory_present: bool,
    visible_surface_present: bool,
    content_visibility_plan_present: bool,
    run_evidence_present: bool,
    blindspot_input_present: bool,
) -> UIImplementationClaimScopeDecision:
    """Decide complete/scoped eligibility from explicit evidence presence."""

    normalized_scope = str(claim_scope)
    declared = tuple(str(value) for value in omitted_evidence_classes)
    declared_set = set(declared)
    presence = {
        UI_IMPLEMENTATION_EVIDENCE_CAPABILITY_COVERAGE: bool(
            capability_coverage_present
        ),
        UI_IMPLEMENTATION_EVIDENCE_OBSERVED_INVENTORY: bool(
            observed_inventory_present
        ),
        UI_IMPLEMENTATION_EVIDENCE_VISIBLE_SURFACE: bool(visible_surface_present),
        UI_IMPLEMENTATION_EVIDENCE_CONTENT_VISIBILITY_PLAN: bool(
            content_visibility_plan_present
        ),
        UI_IMPLEMENTATION_EVIDENCE_RUN_EVIDENCE: bool(run_evidence_present),
        UI_IMPLEMENTATION_EVIDENCE_BLINDSPOTS: bool(blindspot_input_present),
    }
    actual_omitted = tuple(
        evidence_class
        for evidence_class in UI_IMPLEMENTATION_EVIDENCE_CLASSES
        if not presence[evidence_class]
    )
    actual_omitted_set = set(actual_omitted)
    findings: list[UIImplementationClaimScopeFinding] = []

    seen: set[str] = set()
    for evidence_class in declared:
        if evidence_class in seen:
            findings.append(
                UIImplementationClaimScopeFinding(
                    "duplicate_ui_implementation_evidence_omission",
                    "UI implementation claim lists the same omitted evidence class more than once",
                    evidence_class,
                )
            )
        seen.add(evidence_class)
        if evidence_class not in UI_IMPLEMENTATION_EVIDENCE_CLASSES:
            findings.append(
                UIImplementationClaimScopeFinding(
                    "unknown_ui_implementation_evidence_omission",
                    "UI implementation claim lists an unknown omitted evidence class",
                    evidence_class,
                )
            )

    if normalized_scope not in UI_IMPLEMENTATION_CLAIM_SCOPES:
        findings.append(
            UIImplementationClaimScopeFinding(
                "missing_or_unknown_ui_implementation_claim_scope",
                "Runnable UI validation must declare complete or scoped claim scope",
            )
        )
    elif normalized_scope == UI_IMPLEMENTATION_CLAIM_COMPLETE:
        for evidence_class in declared:
            if evidence_class in UI_IMPLEMENTATION_EVIDENCE_CLASSES:
                findings.append(
                    UIImplementationClaimScopeFinding(
                        "complete_ui_claim_declares_evidence_omission",
                        "A complete runnable UI claim cannot declare omitted evidence",
                        evidence_class,
                    )
                )
        for evidence_class in actual_omitted:
            findings.append(
                UIImplementationClaimScopeFinding(
                    "complete_ui_claim_missing_evidence_class",
                    "A complete runnable UI claim is missing a required evidence class",
                    evidence_class,
                )
            )
    else:
        for evidence_class in UI_IMPLEMENTATION_EVIDENCE_CLASSES:
            if evidence_class in actual_omitted_set and evidence_class not in declared_set:
                findings.append(
                    UIImplementationClaimScopeFinding(
                        "scoped_ui_claim_omission_not_declared",
                        "A scoped runnable UI claim must name every omitted evidence class",
                        evidence_class,
                    )
                )
            elif evidence_class in declared_set and evidence_class not in actual_omitted_set:
                findings.append(
                    UIImplementationClaimScopeFinding(
                        "scoped_ui_claim_declares_present_evidence_omitted",
                        "A scoped runnable UI claim may list only evidence classes it actually omits",
                        evidence_class,
                    )
                )

    ok = not findings
    return UIImplementationClaimScopeDecision(
        ok=ok,
        claim_scope=normalized_scope,
        declared_omitted_evidence_classes=declared,
        actual_omitted_evidence_classes=actual_omitted,
        findings=tuple(findings),
        broad_confidence_eligible=(
            ok and normalized_scope == UI_IMPLEMENTATION_CLAIM_COMPLETE
        ),
    )


__all__ = [
    "UIImplementationClaimScopeDecision",
    "UIImplementationClaimScopeFinding",
    "UI_IMPLEMENTATION_CLAIM_COMPLETE",
    "UI_IMPLEMENTATION_CLAIM_SCOPED",
    "UI_IMPLEMENTATION_CLAIM_SCOPES",
    "UI_IMPLEMENTATION_EVIDENCE_BLINDSPOTS",
    "UI_IMPLEMENTATION_EVIDENCE_CAPABILITY_COVERAGE",
    "UI_IMPLEMENTATION_EVIDENCE_CLASSES",
    "UI_IMPLEMENTATION_EVIDENCE_CONTENT_VISIBILITY_PLAN",
    "UI_IMPLEMENTATION_EVIDENCE_OBSERVED_INVENTORY",
    "UI_IMPLEMENTATION_EVIDENCE_RUN_EVIDENCE",
    "UI_IMPLEMENTATION_EVIDENCE_VISIBLE_SURFACE",
    "review_ui_implementation_claim_scope",
]
