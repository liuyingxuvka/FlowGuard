"""FlowGuard model for AI guidance compression.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the prompt/skill hot-path compression before and after
implementation. It guards against shrinking the first-read guidance while
dropping hard gates, hiding route detail without references, or claiming local
installed behavior before editable install, installed skills, shadow workspace,
and git evidence are aligned.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/guidance_compression/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.architecture_reduction import (
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionTrigger,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from flowguard.development_process_flow import (
    PROCESS_ARTIFACT_DESIGN,
    PROCESS_ARTIFACT_DOC,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_RELEASE,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_ROUTINE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


@dataclass(frozen=True)
class GuidanceAction:
    action_type: str


@dataclass(frozen=True)
class GuidanceOutput:
    status: str


@dataclass(frozen=True)
class GuidanceState:
    hot_path_compressed: bool = False
    hard_gates_preserved: bool = False
    reference_handoffs_available: bool = False
    duplicate_reference_detail_folded: bool = False
    long_prompt_templates_lazy_loaded: bool = False
    budget_tests_added: bool = False
    validations_passed: bool = False
    editable_install_synced: bool = False
    installed_skills_synced: bool = False
    shadow_workspace_synced: bool = False
    version_and_git_evidence_aligned: bool = False
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.hot_path_compressed
            and self.hard_gates_preserved
            and self.reference_handoffs_available
            and self.duplicate_reference_detail_folded
            and self.long_prompt_templates_lazy_loaded
            and self.budget_tests_added
            and self.validations_passed
            and self.editable_install_synced
            and self.installed_skills_synced
            and self.shadow_workspace_synced
            and self.version_and_git_evidence_aligned
        )


class CorrectGuidanceCompression:
    name = "CorrectGuidanceCompression"
    reads = (
        "hot_path_compressed",
        "hard_gates_preserved",
        "reference_handoffs_available",
        "duplicate_reference_detail_folded",
        "long_prompt_templates_lazy_loaded",
        "budget_tests_added",
        "validations_passed",
        "editable_install_synced",
        "installed_skills_synced",
        "shadow_workspace_synced",
        "version_and_git_evidence_aligned",
        "done_claim",
    )
    writes = reads
    accepted_input_type = GuidanceAction
    input_description = "guidance compression lifecycle action"
    output_description = "guidance compression state or claim decision"
    idempotency = "Done claims require prompt compression plus current validation, install, shadow, and git evidence."

    def apply(self, input_obj: GuidanceAction, state: GuidanceState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "compress_guidance":
            yield FunctionResult(
                GuidanceOutput("guidance_compressed"),
                replace(
                    state,
                    hot_path_compressed=True,
                    hard_gates_preserved=True,
                    reference_handoffs_available=True,
                    duplicate_reference_detail_folded=True,
                    long_prompt_templates_lazy_loaded=True,
                ),
                label="guidance_compressed",
            )
        elif action == "add_budget_tests":
            yield FunctionResult(
                GuidanceOutput("budget_tests_added"),
                replace(state, budget_tests_added=True),
                label="budget_tests_added",
            )
        elif action == "run_validations":
            yield FunctionResult(
                GuidanceOutput("validations_passed"),
                replace(state, validations_passed=True),
                label="validations_passed",
            )
        elif action == "sync_local_surfaces":
            yield FunctionResult(
                GuidanceOutput("local_surfaces_synced"),
                replace(
                    state,
                    editable_install_synced=True,
                    installed_skills_synced=True,
                    shadow_workspace_synced=True,
                    version_and_git_evidence_aligned=True,
                ),
                label="local_surfaces_synced",
            )
        elif action == "claim_done":
            claim = "accepted" if state.ready_for_done() else "rejected"
            yield FunctionResult(
                GuidanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )


class BrokenPromptOnlyCompletion(CorrectGuidanceCompression):
    name = "BrokenPromptOnlyCompletion"
    idempotency = "Broken variant accepts done after compression and tests only."

    def apply(self, input_obj: GuidanceAction, state: GuidanceState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            claim = "accepted" if state.hot_path_compressed and state.validations_passed else "rejected"
            yield FunctionResult(
                GuidanceOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, GuidanceOutput) and current_output.status.startswith("done_")


def no_done_without_full_sync(state: GuidanceState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "done accepted before compressed prompts, hard gates, folded references, lazy templates, validation, install, shadow, and git evidence aligned"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_full_sync",
        "Guidance compression completion requires folded references, lazy templates, current validation, editable install, installed skill, shadow workspace, and git evidence.",
        no_done_without_full_sync,
    ),
)

EXTERNAL_INPUTS = (
    GuidanceAction("compress_guidance"),
    GuidanceAction("add_budget_tests"),
    GuidanceAction("run_validations"),
    GuidanceAction("sync_local_surfaces"),
    GuidanceAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> GuidanceState:
    return GuidanceState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectGuidanceCompression(),), name="guidance_compression_correct")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenPromptOnlyCompletion(),), name="guidance_compression_broken")


def architecture_reduction_report():
    plan = ArchitectureReductionPlan(
        "compress-flowguard-ai-guidance/prompt-hot-path",
        observable_contract=ObservableArchitectureContract(
            source_model_id="openspec:compress-flowguard-ai-guidance",
            source_code_boundary_id="FlowGuard AI guidance hot path",
            public_entrypoints=(
                ".agents/skills/flowguard/SKILL.md",
                ".agents/skills/flowguard-*/SKILL.md",
                "docs/agents_snippet.md",
            ),
            observable_outputs=(
                "same FlowGuard hard gates remain visible",
                "same direct route discoverability remains visible",
                "same detailed protocols remain reachable through satellite-owned references and lazy templates",
            ),
            observable_state=("installed Codex skill content", "shadow workspace package content"),
            observable_side_effects=("editable install refresh", "local git commit/tag evidence"),
            validation_boundaries=(
                "tests/test_skill_docs.py",
                ".flowguard/guidance_compression/run_checks.py",
                "installed skill content verification",
                "shadow workspace import verification",
            ),
            rationale="Prompt contraction changes agent behavior surfaces while preserving hard gates and route discoverability.",
        ),
        candidates=(
            ArchitectureReductionCandidate(
                candidate_id="collapse-duplicated-satellite-protocol-detail",
                candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                code_node_id=".agents/skills/flowguard-*/SKILL.md",
                source_model_element="Satellite skills use concise route shells",
                target_action=TARGET_ACTION_COLLAPSE,
                proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="Keep satellite entrypoints but collapse repeated workflow detail into references.",
                evidence_refs=("tests/test_skill_docs.py", ".flowguard/behavior_commitment_ledger/ledger.json"),
                business_intent_id="intent:flowguard-agent-guidance-route",
                behavior_commitment_id="commitment:flowguard-agent-guidance-route",
                primary_path_id="path:flowguard:plane-first-route-selection",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_primary_path_id="path:flowguard:plane-first-route-selection",
                delegation_evidence_id="proof:flowguard-agent-guidance-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
            ),
            ArchitectureReductionCandidate(
                candidate_id="remove-duplicated-hot-path-route-inventory",
                candidate_type=CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
                code_node_id="docs/agents_snippet.md and flowguard/SKILL.md",
                source_model_element="Global routing uses a compact canonical decision table",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="Keep one compact route table and move helper inventories to references.",
                evidence_refs=("tests/test_skill_docs.py", ".flowguard/behavior_commitment_ledger/ledger.json"),
                business_intent_id="intent:flowguard-agent-guidance-route",
                behavior_commitment_id="commitment:flowguard-agent-guidance-route",
                primary_path_id="path:flowguard:plane-first-route-selection",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_primary_path_id="path:flowguard:plane-first-route-selection",
                delegation_evidence_id="proof:flowguard-agent-guidance-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
            ),
            ArchitectureReductionCandidate(
                candidate_id="fold-duplicated-kernel-reference-protocols",
                candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                code_node_id=".agents/skills/flowguard/references/*_protocol.md",
                source_model_element="Kernel-owned reference paths are compatibility handoff stubs",
                target_action=TARGET_ACTION_COLLAPSE,
                proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="Keep legacy kernel reference paths while moving detailed ownership to direct satellite references.",
                evidence_refs=("tests/test_skill_docs.py", ".flowguard/behavior_commitment_ledger/ledger.json"),
                business_intent_id="intent:flowguard-agent-guidance-route",
                behavior_commitment_id="commitment:flowguard-agent-guidance-route",
                primary_path_id="path:flowguard:plane-first-route-selection",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_primary_path_id="path:flowguard:plane-first-route-selection",
                delegation_evidence_id="proof:flowguard-agent-guidance-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
            ),
            ArchitectureReductionCandidate(
                candidate_id="split-long-agent-prompt-templates",
                candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                code_node_id=".agents/skills/flowguard-*/references/templates/*.md",
                source_model_element="Long delegation prompts are lazy-loaded templates",
                target_action=TARGET_ACTION_COLLAPSE,
                proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="Keep detailed scaffolding prompts reachable without loading them in ordinary protocol reads.",
                evidence_refs=("tests/test_skill_docs.py", ".flowguard/behavior_commitment_ledger/ledger.json"),
                business_intent_id="intent:flowguard-agent-guidance-route",
                behavior_commitment_id="commitment:flowguard-agent-guidance-route",
                primary_path_id="path:flowguard:plane-first-route-selection",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_code_contract_id="contract:flowguard:route-guidance",
                delegates_to_primary_path_id="path:flowguard:plane-first-route-selection",
                delegation_evidence_id="proof:flowguard-agent-guidance-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
            ),
        ),
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                route_id=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                trigger_reason="Prompt compression touches source, tests, installed skills, shadow workspace, and git evidence.",
                complexity_signal="same guidance repeated across multiple hot paths",
                recommended_timing="before implementation and before done claim",
                required=True,
            ),
        ),
        rationale="Shrink repeated AI-facing guidance while preserving observable route and evidence behavior.",
    )
    return review_architecture_reduction(plan)


def development_process_report():
    plan = DevelopmentProcessPlan(
        "compress-flowguard-ai-guidance/lifecycle",
        decision_scope=PROCESS_SCOPE_ROUTINE,
        artifacts=(
            ProcessArtifact("openspec.compress-guidance", PROCESS_ARTIFACT_REQUIREMENT, "1"),
            ProcessArtifact("design.compress-guidance", PROCESS_ARTIFACT_DESIGN, "1"),
            ProcessArtifact("model.guidance-compression", PROCESS_ARTIFACT_MODEL, "1"),
            ProcessArtifact("skill-hot-paths", PROCESS_ARTIFACT_DOC, "2"),
            ProcessArtifact("skill-doc-tests", PROCESS_ARTIFACT_TEST, "2"),
            ProcessArtifact("editable-install", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("installed-skills", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("shadow-workspace", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("local-git-evidence", PROCESS_ARTIFACT_RELEASE, "1"),
        ),
        actions=(
            ProcessAction(
                "create-openspec-and-model",
                writes_artifacts=("openspec.compress-guidance", "design.compress-guidance", "model.guidance-compression"),
            ),
            ProcessAction("compress-prompt-hot-paths", writes_artifacts=("skill-hot-paths", "skill-doc-tests")),
            ProcessAction("run-guidance-validation", produced_evidence_ids=("evidence:guidance-validation",)),
            ProcessAction(
                "sync-local-surfaces",
                writes_artifacts=("editable-install", "installed-skills", "shadow-workspace", "local-git-evidence"),
                produced_evidence_ids=("evidence:local-sync",),
            ),
        ),
        evidence=(
            ProcessEvidence(
                "evidence:guidance-validation",
                evidence_kind="skill-docs-and-model",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("model.guidance-compression", "skill-hot-paths", "skill-doc-tests"),
                covered_versions={
                    "model.guidance-compression": "1",
                    "skill-hot-paths": "2",
                    "skill-doc-tests": "2",
                },
                validation_requirement_ids=("require-guidance-validation",),
                produced_by_action_id="run-guidance-validation",
                command="python .flowguard/guidance_compression/run_checks.py; python -m unittest tests.test_skill_docs -v",
            ),
            ProcessEvidence(
                "evidence:local-sync",
                evidence_kind="install-shadow-git-sync",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("editable-install", "installed-skills", "shadow-workspace", "local-git-evidence"),
                covered_versions={
                    "editable-install": "1",
                    "installed-skills": "1",
                    "shadow-workspace": "1",
                    "local-git-evidence": "1",
                },
                validation_requirement_ids=("require-local-sync",),
                produced_by_action_id="sync-local-surfaces",
                command="editable install, installed skill sync, shadow import check, git commit/tag check",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "require-guidance-validation",
                required_artifact_ids=("model.guidance-compression", "skill-hot-paths", "skill-doc-tests"),
                required_evidence_kinds=("skill-docs-and-model",),
                evidence_ids=("evidence:guidance-validation",),
            ),
            ValidationRequirement(
                "require-local-sync",
                required_artifact_ids=("editable-install", "installed-skills", "shadow-workspace", "local-git-evidence"),
                required_evidence_kinds=("install-shadow-git-sync",),
                evidence_ids=("evidence:local-sync",),
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "skill-hot-path-edits-stale-installed-skills",
                upstream_artifact_id="skill-hot-paths",
                invalidates_evidence_kinds=("install-shadow-git-sync",),
                description="Prompt edits stale installed skill, shadow workspace, and git completion evidence.",
            ),
        ),
    )
    return review_development_process_flow(plan)


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "GuidanceAction",
    "GuidanceOutput",
    "GuidanceState",
    "architecture_reduction_report",
    "build_broken_workflow",
    "build_correct_workflow",
    "development_process_report",
    "initial_state",
    "terminal_predicate",
]
