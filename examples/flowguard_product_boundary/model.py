"""Self-review model for FlowGuard's public/internal product boundary.

The model checks that a future public GitHub surface remains small and useful
while internal maintenance evidence stays internal.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    OracleCheckResult,
    Scenario,
    ScenarioExpectation,
    ScenarioRun,
    Workflow,
)


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    layer: str
    kind: str
    required_public: bool = False
    contains_private_evidence: bool = False
    maintenance_only: bool = False
    default_enabled: bool = True
    user_manual_required: bool = False


@dataclass(frozen=True)
class ArtifactClassification:
    artifact: ArtifactSpec
    target_layer: str
    reason: str


@dataclass(frozen=True)
class ReleasePlacement:
    artifact_name: str
    target_layer: str
    included: bool
    default_enabled: bool
    user_manual_required: bool
    reason: str


@dataclass(frozen=True)
class PlacementRecord:
    artifact_name: str
    target_layer: str
    included: bool


@dataclass(frozen=True)
class State:
    required_public_seen: tuple[str, ...] = ()
    public_artifacts: tuple[str, ...] = ()
    internal_artifacts: tuple[str, ...] = ()
    private_public_leaks: tuple[str, ...] = ()
    maintenance_public_leaks: tuple[str, ...] = ()
    heavy_public_adoption_logs: tuple[str, ...] = ()
    optional_public_omissions: tuple[str, ...] = ()

    def with_required(self, name: str) -> "State":
        if name in self.required_public_seen:
            return self
        return replace(self, required_public_seen=self.required_public_seen + (name,))

    def with_public(self, artifact: ArtifactSpec, placement: ReleasePlacement) -> "State":
        public = self.public_artifacts
        if placement.included and artifact.name not in public:
            public = public + (artifact.name,)

        private_leaks = self.private_public_leaks
        if placement.included and artifact.contains_private_evidence and artifact.name not in private_leaks:
            private_leaks = private_leaks + (artifact.name,)

        maintenance_leaks = self.maintenance_public_leaks
        if placement.included and artifact.maintenance_only and artifact.name not in maintenance_leaks:
            maintenance_leaks = maintenance_leaks + (artifact.name,)

        heavy_logs = self.heavy_public_adoption_logs
        if (
            placement.included
            and artifact.kind == "adoption_log"
            and (not placement.default_enabled or placement.user_manual_required)
            and artifact.name not in heavy_logs
        ):
            heavy_logs = heavy_logs + (artifact.name,)

        return replace(
            self,
            public_artifacts=public,
            private_public_leaks=private_leaks,
            maintenance_public_leaks=maintenance_leaks,
            heavy_public_adoption_logs=heavy_logs,
        )

    def with_internal(self, artifact: ArtifactSpec) -> "State":
        if artifact.name in self.internal_artifacts:
            return self
        return replace(self, internal_artifacts=self.internal_artifacts + (artifact.name,))

    def with_optional_omission(self, artifact: ArtifactSpec) -> "State":
        if artifact.name in self.optional_public_omissions:
            return self
        return replace(self, optional_public_omissions=self.optional_public_omissions + (artifact.name,))


def _dedup_append(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return values + (value,)


class ClassifyProductArtifact:
    name = "ClassifyProductArtifact"
    reads = ("required_public_seen",)
    writes = ("required_public_seen",)
    input_description = "ArtifactSpec"
    output_description = "ArtifactClassification"
    idempotency = "same artifact classification is stable"
    accepted_input_type = ArtifactSpec

    def apply(self, input_obj: ArtifactSpec, state: State) -> Iterable[FunctionResult]:
        state = state.with_required(input_obj.name) if input_obj.required_public else state
        if input_obj.required_public:
            target = "public"
            label = "artifact_public_required"
            reason = "required public surface artifact"
        elif input_obj.layer == "public" and not input_obj.maintenance_only:
            target = "public_optional"
            label = "artifact_public_optional"
            reason = "optional public artifact"
        else:
            target = "internal"
            label = "artifact_internal"
            reason = "maintenance-only or private artifact stays internal"
        yield FunctionResult(
            ArtifactClassification(input_obj, target, reason),
            state,
            label=label,
            reason=reason,
        )


class DecideReleasePlacement:
    name = "DecideReleasePlacement"
    reads = ("required_public_seen",)
    writes = ()
    input_description = "ArtifactClassification"
    output_description = "ReleasePlacement"
    idempotency = "same classification yields same release placement"
    accepted_input_type = ArtifactClassification

    def apply(self, input_obj: ArtifactClassification, state: State) -> Iterable[FunctionResult]:
        artifact = input_obj.artifact
        if input_obj.target_layer == "public":
            yield FunctionResult(
                ReleasePlacement(
                    artifact.name,
                    "public",
                    True,
                    artifact.default_enabled,
                    artifact.user_manual_required,
                    "required artifact included in public minimal system",
                ),
                state,
                label="public_included",
                reason="required public artifact included",
            )
            return
        if input_obj.target_layer == "public_optional":
            yield FunctionResult(
                ReleasePlacement(
                    artifact.name,
                    "internal",
                    False,
                    artifact.default_enabled,
                    artifact.user_manual_required,
                    "optional public artifact can wait until product value is proven",
                ),
                state,
                label="optional_not_released",
                reason="optional public artifact is not part of the minimal release",
            )
            return
        yield FunctionResult(
            ReleasePlacement(
                artifact.name,
                "internal",
                True,
                artifact.default_enabled,
                artifact.user_manual_required,
                "internal maintenance artifact retained outside public release",
            ),
            state,
            label="internal_retained",
            reason="internal maintenance artifact stays internal",
        )


class RecordReleasePlacement:
    name = "RecordReleasePlacement"
    reads = ("public_artifacts", "internal_artifacts")
    writes = (
        "public_artifacts",
        "internal_artifacts",
        "private_public_leaks",
        "maintenance_public_leaks",
        "heavy_public_adoption_logs",
        "optional_public_omissions",
    )
    input_description = "ReleasePlacement"
    output_description = "PlacementRecord"
    idempotency = "same artifact is recorded once per release surface"
    accepted_input_type = ReleasePlacement

    def apply(self, input_obj: ReleasePlacement, state: State) -> Iterable[FunctionResult]:
        artifact = _artifact_by_name(input_obj.artifact_name)
        if input_obj.target_layer == "public":
            new_state = state.with_public(artifact, input_obj)
            label = "public_recorded"
            reason = "public release surface recorded"
        elif input_obj.included:
            new_state = state.with_internal(artifact)
            label = "internal_recorded"
            reason = "internal maintenance artifact recorded outside public surface"
        else:
            new_state = state.with_optional_omission(artifact)
            label = "optional_omitted"
            reason = "optional artifact omitted from minimal release"
        yield FunctionResult(
            PlacementRecord(input_obj.artifact_name, input_obj.target_layer, input_obj.included),
            new_state,
            label=label,
            reason=reason,
        )


class BrokenExposeInternalMaintenance(DecideReleasePlacement):
    name = "DecideReleasePlacement"

    def apply(self, input_obj: ArtifactClassification, state: State) -> Iterable[FunctionResult]:
        artifact = input_obj.artifact
        yield FunctionResult(
            ReleasePlacement(
                artifact.name,
                "public",
                True,
                artifact.default_enabled,
                artifact.user_manual_required,
                "broken release exposes all artifacts publicly",
            ),
            state,
            label="broken_public_included",
            reason="broken placement leaks internal maintenance artifacts",
        )


class BrokenOmitSkillFromPublicRelease(DecideReleasePlacement):
    name = "DecideReleasePlacement"

    def apply(self, input_obj: ArtifactClassification, state: State) -> Iterable[FunctionResult]:
        artifact = input_obj.artifact
        if artifact.name == "codex_skill":
            yield FunctionResult(
                ReleasePlacement(
                    artifact.name,
                    "internal",
                    False,
                    artifact.default_enabled,
                    artifact.user_manual_required,
                    "broken release omits the trigger mechanism",
                ),
                state,
                label="broken_skill_omitted",
                reason="public package lacks the model-first Skill trigger",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenManualAdoptionLog(DecideReleasePlacement):
    name = "DecideReleasePlacement"

    def apply(self, input_obj: ArtifactClassification, state: State) -> Iterable[FunctionResult]:
        artifact = input_obj.artifact
        if artifact.kind == "adoption_log":
            yield FunctionResult(
                ReleasePlacement(
                    artifact.name,
                    "public",
                    True,
                    False,
                    True,
                    "broken public log requires manual user maintenance",
                ),
                state,
                label="broken_heavy_log",
                reason="adoption logging became a user burden",
            )
            return
        yield from super().apply(input_obj, state)


def _artifact_by_name(name: str) -> ArtifactSpec:
    for artifact in ALL_ARTIFACTS:
        if artifact.name == name:
            return artifact
    raise KeyError(name)


def public_required_artifacts_are_included() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        missing = tuple(
            name for name in state.required_public_seen if name not in state.public_artifacts
        )
        if missing:
            return InvariantResult.fail(f"required public artifacts missing: {missing!r}")
        return InvariantResult.pass_()

    return Invariant(
        "public_required_artifacts_are_included",
        "Every required public artifact that appears in the release plan must be included publicly.",
        predicate,
    )


def public_release_must_not_include_private_or_internal_evidence() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        leaks = state.private_public_leaks + state.maintenance_public_leaks
        if leaks:
            return InvariantResult.fail(f"internal/private artifacts leaked to public release: {leaks!r}")
        return InvariantResult.pass_()

    return Invariant(
        "public_release_must_not_include_private_or_internal_evidence",
        "Public release must not include internal KB, private pilots, or maintenance-only artifacts.",
        predicate,
    )


def adoption_log_must_be_default_low_burden() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        if state.heavy_public_adoption_logs:
            return InvariantResult.fail(
                f"adoption logs became manual public burden: {state.heavy_public_adoption_logs!r}"
            )
        return InvariantResult.pass_()

    return Invariant(
        "adoption_log_must_be_default_low_burden",
        "Public adoption logging should be default and lightweight, not a manual user burden.",
        predicate,
    )


INVARIANTS = (
    public_required_artifacts_are_included(),
    public_release_must_not_include_private_or_internal_evidence(),
    adoption_log_must_be_default_low_burden(),
)


CORE_PACKAGE = ArtifactSpec("flowguard_package", "public", "package", required_public=True)
MINIMAL_TEMPLATE = ArtifactSpec("minimal_model_template", "public", "template", required_public=True)
MODELING_PROTOCOL = ArtifactSpec("modeling_protocol", "public", "docs", required_public=True)
INVARIANT_COOKBOOK = ArtifactSpec("invariant_cookbook", "public", "docs", required_public=True)
CODEX_SKILL = ArtifactSpec("codex_skill", "public", "skill", required_public=True)
AGENTS_SNIPPET = ArtifactSpec("agents_snippet", "public", "docs", required_public=True)
ADOPTION_LOG = ArtifactSpec("adoption_log", "public", "adoption_log", required_public=True)
JOB_MATCHING_EXAMPLE = ArtifactSpec("job_matching_example", "public", "example", required_public=True)
CLI_WRAPPER = ArtifactSpec("future_cli_wrapper", "public", "cli", required_public=False)

INTERNAL_KB = ArtifactSpec(
    "internal_kb_feedback",
    "internal",
    "maintenance",
    contains_private_evidence=True,
    maintenance_only=True,
)
PRIVATE_PILOTS = ArtifactSpec(
    "private_pilot_logs",
    "internal",
    "maintenance",
    contains_private_evidence=True,
    maintenance_only=True,
)
FULL_CORPUS = ArtifactSpec(
    "internal_2100_case_corpus",
    "internal",
    "benchmark",
    maintenance_only=True,
)
DAILY_REVIEW = ArtifactSpec(
    "daily_maintenance_review",
    "internal",
    "automation",
    maintenance_only=True,
)

ALL_ARTIFACTS = (
    CORE_PACKAGE,
    MINIMAL_TEMPLATE,
    MODELING_PROTOCOL,
    INVARIANT_COOKBOOK,
    CODEX_SKILL,
    AGENTS_SNIPPET,
    ADOPTION_LOG,
    JOB_MATCHING_EXAMPLE,
    CLI_WRAPPER,
    INTERNAL_KB,
    PRIVATE_PILOTS,
    FULL_CORPUS,
    DAILY_REVIEW,
)

MINIMAL_PUBLIC_SEQUENCE = (
    CORE_PACKAGE,
    MINIMAL_TEMPLATE,
    MODELING_PROTOCOL,
    INVARIANT_COOKBOOK,
    CODEX_SKILL,
    AGENTS_SNIPPET,
    ADOPTION_LOG,
    JOB_MATCHING_EXAMPLE,
    INTERNAL_KB,
    PRIVATE_PILOTS,
    FULL_CORPUS,
)


def build_workflow(*, placement_block: object | None = None) -> Workflow:
    return Workflow(
        (
            ClassifyProductArtifact(),
            placement_block or DecideReleasePlacement(),
            RecordReleasePlacement(),
        ),
        name="flowguard_product_boundary",
    )


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=tuple(labels),
        summary=summary,
    )


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def required_public_present(required_names: Sequence[str]) -> object:
    def check(run: ScenarioRun) -> OracleCheckResult:
        missing = []
        for state in run.final_states:
            absent = tuple(name for name in required_names if name not in state.public_artifacts)
            if absent:
                missing.append(absent)
        return OracleCheckResult(
            ok=not missing,
            message="required public artifacts are missing",
            evidence=(f"required public artifacts present: {tuple(required_names)!r}",),
            violation_name="missing_required_public_artifacts",
        )

    return check


def no_internal_public_leaks() -> object:
    def check(run: ScenarioRun) -> OracleCheckResult:
        leaked = tuple(
            state.private_public_leaks + state.maintenance_public_leaks
            for state in run.final_states
            if state.private_public_leaks or state.maintenance_public_leaks
        )
        return OracleCheckResult(
            ok=not leaked,
            message="internal artifacts leaked to public surface",
            evidence=("internal maintenance artifacts stayed internal",),
            violation_name="internal_artifact_public_leak",
        )

    return check


def scenario(
    name: str,
    description: str,
    sequence: Sequence[ArtifactSpec],
    expected: ScenarioExpectation,
    *,
    workflow: Workflow | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=tuple(sequence),
        expected=expected,
        workflow=workflow or build_workflow(),
        invariants=INVARIANTS,
    )


def product_boundary_scenarios() -> tuple[Scenario, ...]:
    required_names = tuple(artifact.name for artifact in MINIMAL_PUBLIC_SEQUENCE if artifact.required_public)
    return (
        scenario(
            "PBS01_minimal_public_surface_keeps_internal_private",
            "The public release includes required minimal artifacts and keeps maintenance evidence internal.",
            MINIMAL_PUBLIC_SEQUENCE,
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("public_included", "internal_retained"),
                custom_checks=(required_public_present(required_names), no_internal_public_leaks()),
                summary="OK; public minimal system is complete and internal maintenance stays internal",
            ),
        ),
        scenario(
            "PBS02_optional_cli_can_wait",
            "Optional CLI wrappers are not required before public value is proven.",
            (CORE_PACKAGE, MINIMAL_TEMPLATE, CLI_WRAPPER),
            _expect_ok(
                "OK; optional CLI can stay out of the minimal release",
                labels=("optional_not_released", "optional_omitted"),
            ),
        ),
        scenario(
            "PBS03_broken_exposes_internal_maintenance",
            "Broken release planning leaks private pilots and internal KB to the public surface.",
            (CORE_PACKAGE, INTERNAL_KB, PRIVATE_PILOTS),
            _expect_violation(
                "VIOLATION public_release_must_not_include_private_or_internal_evidence",
                ("public_release_must_not_include_private_or_internal_evidence",),
            ),
            workflow=build_workflow(placement_block=BrokenExposeInternalMaintenance()),
        ),
        scenario(
            "PBS04_broken_omits_codex_skill",
            "Broken release omits the Skill that makes agents remember model-first checks.",
            (CODEX_SKILL,),
            _expect_violation(
                "VIOLATION public_required_artifacts_are_included",
                ("public_required_artifacts_are_included",),
            ),
            workflow=build_workflow(placement_block=BrokenOmitSkillFromPublicRelease()),
        ),
        scenario(
            "PBS05_broken_manual_log_burdens_user",
            "Broken public adoption log requires manual user maintenance instead of lightweight default logging.",
            (ADOPTION_LOG,),
            _expect_violation(
                "VIOLATION adoption_log_must_be_default_low_burden",
                ("adoption_log_must_be_default_low_burden",),
            ),
            workflow=build_workflow(placement_block=BrokenManualAdoptionLog()),
        ),
    )


def run_product_boundary_review():
    from flowguard.review import review_scenarios

    return review_scenarios(product_boundary_scenarios())


__all__ = [
    "ArtifactSpec",
    "State",
    "build_workflow",
    "product_boundary_scenarios",
    "run_product_boundary_review",
]
