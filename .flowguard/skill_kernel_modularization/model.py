"""FlowGuard rollout model for Skill Kernel modularization.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the plan for making flowguard a compact Skill
Kernel with delegated sub-protocols. It guards against losing hard FlowGuard
gates, dropping route coverage, duplicating rule ownership, burying the thin
default AI path under advanced vocabulary, over-triggering heavy framework
checks for ordinary tasks, and classifying package helper APIs as standalone
sub-skills.

Run:
python .flowguard/skill_kernel_modularization/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow
from flowguard.review import review_scenarios


@dataclass(frozen=True)
class SkillKernelCase:
    name: str
    thin_default_path_visible: bool = True
    advanced_routes_are_escalation: bool = True
    public_internal_boundary_visible: bool = True
    current_satellite_topology_visible: bool = True
    compact_kernel: bool = True
    hard_gates_visible: bool = True
    all_subprotocol_routes: bool = True
    helper_apis_not_subskills: bool = True
    no_duplicate_rule_ownership: bool = True
    standalone_flowguard_preserved: bool = True
    ordinary_work_avoids_framework_suite: bool = True
    release_sync_route_visible: bool = True
    test_mesh_hierarchy_visible: bool = True
    soft_oversize_hint_visible: bool = True
    oversize_hint_not_gate: bool = True
    external_planner_generic: bool = True
    model_test_alignment_visible: bool = True
    model_test_alignment_independent: bool = True


@dataclass(frozen=True)
class SkillKernelState:
    case_name: str = ""
    thin_default_path_visible: bool = False
    advanced_routes_are_escalation: bool = False
    public_internal_boundary_visible: bool = False
    current_satellite_topology_visible: bool = False
    compact_kernel: bool = False
    hard_gates_visible: bool = False
    all_subprotocol_routes: bool = False
    helper_apis_not_subskills: bool = False
    no_duplicate_rule_ownership: bool = False
    standalone_flowguard_preserved: bool = False
    ordinary_work_avoids_framework_suite: bool = False
    release_sync_route_visible: bool = False
    test_mesh_hierarchy_visible: bool = False
    soft_oversize_hint_visible: bool = False
    oversize_hint_not_gate: bool = False
    external_planner_generic: bool = False
    model_test_alignment_visible: bool = False
    model_test_alignment_independent: bool = False


GOOD_KERNEL = SkillKernelCase("good_skill_kernel")
BROKEN_BURIED_DEFAULT_PATH = SkillKernelCase("broken_buried_default_path", thin_default_path_visible=False)
BROKEN_ADVANCED_ROUTES_DEFAULT = SkillKernelCase(
    "broken_advanced_routes_default",
    advanced_routes_are_escalation=False,
)
BROKEN_PUBLIC_INTERNAL_MIXED = SkillKernelCase(
    "broken_public_internal_mixed",
    public_internal_boundary_visible=False,
)
BROKEN_STALE_SATELLITE_TOPOLOGY = SkillKernelCase(
    "broken_stale_satellite_topology",
    current_satellite_topology_visible=False,
)
BROKEN_LONG_KERNEL = SkillKernelCase("broken_long_kernel", compact_kernel=False)
BROKEN_HARD_GATES = SkillKernelCase("broken_hard_gates", hard_gates_visible=False)
BROKEN_ROUTE_GAP = SkillKernelCase("broken_route_gap", all_subprotocol_routes=False)
BROKEN_HELPER_SUBSKILL = SkillKernelCase("broken_helper_subskill", helper_apis_not_subskills=False)
BROKEN_DUPLICATE_RULES = SkillKernelCase("broken_duplicate_rules", no_duplicate_rule_ownership=False)
BROKEN_STANDALONE_LOSS = SkillKernelCase("broken_standalone_loss", standalone_flowguard_preserved=False)
BROKEN_HEAVY_OVERTRIGGER = SkillKernelCase(
    "broken_heavy_overtrigger",
    ordinary_work_avoids_framework_suite=False,
)
BROKEN_RELEASE_SYNC_GAP = SkillKernelCase("broken_release_sync_gap", release_sync_route_visible=False)
BROKEN_TESTMESH_NARROWING = SkillKernelCase(
    "broken_testmesh_narrowing",
    test_mesh_hierarchy_visible=False,
)
BROKEN_MISSING_OVERSIZE_HINT = SkillKernelCase(
    "broken_missing_oversize_hint",
    soft_oversize_hint_visible=False,
)
BROKEN_OVERSIZE_GATE = SkillKernelCase(
    "broken_oversize_gate",
    oversize_hint_not_gate=False,
)
BROKEN_PLANNER_TOOL_DEPENDENCY = SkillKernelCase(
    "broken_planner_tool_dependency",
    external_planner_generic=False,
)
BROKEN_MISSING_MODEL_TEST_ALIGNMENT = SkillKernelCase(
    "broken_missing_model_test_alignment",
    model_test_alignment_visible=False,
)
BROKEN_MODEL_TEST_ALIGNMENT_MESH_DEPENDENCY = SkillKernelCase(
    "broken_model_test_alignment_mesh_dependency",
    model_test_alignment_independent=False,
)


class EvaluateSkillKernelPlan:
    name = "EvaluateSkillKernelPlan"
    reads = ("SkillKernelState",)
    writes = (
        "case_name",
        "thin_default_path_visible",
        "advanced_routes_are_escalation",
        "public_internal_boundary_visible",
        "current_satellite_topology_visible",
        "compact_kernel",
        "hard_gates_visible",
        "all_subprotocol_routes",
        "helper_apis_not_subskills",
        "no_duplicate_rule_ownership",
        "standalone_flowguard_preserved",
        "ordinary_work_avoids_framework_suite",
        "release_sync_route_visible",
        "test_mesh_hierarchy_visible",
        "soft_oversize_hint_visible",
        "oversize_hint_not_gate",
        "external_planner_generic",
        "model_test_alignment_visible",
        "model_test_alignment_independent",
    )
    accepted_input_type = SkillKernelCase
    input_description = "skill kernel modularization case"
    output_description = "skill kernel modularization state"
    idempotency = "same case produces one policy state"

    def apply(self, input_obj: SkillKernelCase, _state: SkillKernelState):
        new_state = SkillKernelState(
            case_name=input_obj.name,
            thin_default_path_visible=input_obj.thin_default_path_visible,
            advanced_routes_are_escalation=input_obj.advanced_routes_are_escalation,
            public_internal_boundary_visible=input_obj.public_internal_boundary_visible,
            current_satellite_topology_visible=input_obj.current_satellite_topology_visible,
            compact_kernel=input_obj.compact_kernel,
            hard_gates_visible=input_obj.hard_gates_visible,
            all_subprotocol_routes=input_obj.all_subprotocol_routes,
            helper_apis_not_subskills=input_obj.helper_apis_not_subskills,
            no_duplicate_rule_ownership=input_obj.no_duplicate_rule_ownership,
            standalone_flowguard_preserved=input_obj.standalone_flowguard_preserved,
            ordinary_work_avoids_framework_suite=input_obj.ordinary_work_avoids_framework_suite,
            release_sync_route_visible=input_obj.release_sync_route_visible,
            test_mesh_hierarchy_visible=input_obj.test_mesh_hierarchy_visible,
            soft_oversize_hint_visible=input_obj.soft_oversize_hint_visible,
            oversize_hint_not_gate=input_obj.oversize_hint_not_gate,
            external_planner_generic=input_obj.external_planner_generic,
            model_test_alignment_visible=input_obj.model_test_alignment_visible,
            model_test_alignment_independent=input_obj.model_test_alignment_independent,
        )
        return (
            FunctionResult(
                output=input_obj,
                new_state=new_state,
                label=input_obj.name,
                reason="projected Skill Kernel modularization into policy state",
            ),
        )


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def _empty(state: SkillKernelState) -> bool:
    return not state.case_name


def thin_default_path_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.thin_default_path_visible:
        return _fail(
            "thin_default_path_stays_visible",
            "the smallest useful FlowGuard path is buried behind advanced route vocabulary",
        )
    return _pass()


def advanced_routes_are_escalations(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.advanced_routes_are_escalation:
        return _fail(
            "advanced_routes_are_escalations",
            "advanced FlowGuard routes are presented as mandatory default reading",
        )
    return _pass()


def public_internal_boundary_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.public_internal_boundary_visible:
        return _fail(
            "public_internal_boundary_stays_visible",
            "ordinary public use is mixed with internal maintenance and release-hardening machinery",
        )
    return _pass()


def satellite_topology_stays_current(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.current_satellite_topology_visible:
        return _fail(
            "satellite_topology_stays_current",
            "satellite topology guidance uses stale fixed-count wording",
        )
    return _pass()


def kernel_stays_compact(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.compact_kernel:
        return _fail("kernel_stays_compact", "main Skill remains a long combined policy document")
    return _pass()


def hard_gates_remain_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.hard_gates_visible:
        return _fail("hard_gates_remain_visible", "real package, no-fake-framework, and skipped-check gates disappeared")
    return _pass()


def subprotocol_routes_are_complete(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.all_subprotocol_routes:
        return _fail("subprotocol_routes_are_complete", "required sub-protocol route is missing")
    return _pass()


def helper_apis_remain_helpers(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.helper_apis_not_subskills:
        return _fail("helper_apis_remain_helpers", "package helper APIs are described as standalone sub-skills")
    return _pass()


def rule_ownership_is_not_duplicated(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.no_duplicate_rule_ownership:
        return _fail("rule_ownership_is_not_duplicated", "one rule is owned by several protocol documents")
    return _pass()


def standalone_use_is_preserved(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.standalone_flowguard_preserved:
        return _fail("standalone_use_is_preserved", "FlowGuard now requires an upstream planner")
    return _pass()


def heavy_checks_are_scoped(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.ordinary_work_avoids_framework_suite:
        return _fail("heavy_checks_are_scoped", "ordinary project work is forced through framework evidence suites")
    return _pass()


def release_sync_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.release_sync_route_visible:
        return _fail("release_sync_stays_visible", "release/install/shadow/GitHub sync route is missing")
    return _pass()


def testmesh_hierarchy_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.test_mesh_hierarchy_visible:
        return _fail(
            "testmesh_hierarchy_stays_visible",
            "TestMesh is narrowed to slow/background evidence instead of parent/child test hierarchy",
        )
    return _pass()


def soft_oversize_hint_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.soft_oversize_hint_visible:
        return _fail(
            "soft_oversize_hint_stays_visible",
            "oversized models, tests, scripts, modules, or commands have no split consideration hint",
        )
    return _pass()


def oversize_hint_remains_soft(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.oversize_hint_not_gate:
        return _fail(
            "oversize_hint_remains_soft",
            "oversize guidance became a hard threshold or forced split gate",
        )
    return _pass()


def planner_language_stays_generic(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.external_planner_generic:
        return _fail(
            "planner_language_stays_generic",
            "public Skill wording depends on a named external planner",
        )
    return _pass()


def model_test_alignment_route_stays_visible(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.model_test_alignment_visible:
        return _fail(
            "model_test_alignment_route_stays_visible",
            "model-test alignment has no dedicated route for comparing model obligations with tests",
        )
    return _pass()


def model_test_alignment_stays_independent(state: SkillKernelState, _trace: object) -> InvariantResult:
    if _empty(state):
        return _pass()
    if not state.model_test_alignment_independent:
        return _fail(
            "model_test_alignment_stays_independent",
            "model-test alignment is coupled to TestMesh, StructureMesh, or ModelMesh",
        )
    return _pass()


INVARIANTS = (
    Invariant(
        "thin_default_path_stays_visible",
        "The smallest useful FlowGuard path appears before advanced routes.",
        thin_default_path_stays_visible,
    ),
    Invariant(
        "advanced_routes_are_escalations",
        "Advanced routes are escalation paths, not mandatory default reading.",
        advanced_routes_are_escalations,
    ),
    Invariant(
        "public_internal_boundary_stays_visible",
        "Public use is separated from internal maintenance machinery.",
        public_internal_boundary_stays_visible,
    ),
    Invariant(
        "satellite_topology_stays_current",
        "Satellite topology wording stays current.",
        satellite_topology_stays_current,
    ),
    Invariant("kernel_stays_compact", "Main Skill is a compact router.", kernel_stays_compact),
    Invariant("hard_gates_remain_visible", "Hard FlowGuard gates remain in the kernel.", hard_gates_remain_visible),
    Invariant("subprotocol_routes_are_complete", "All major sub-protocols are routed.", subprotocol_routes_are_complete),
    Invariant("helper_apis_remain_helpers", "Helper APIs are not treated as sub-skills.", helper_apis_remain_helpers),
    Invariant("rule_ownership_is_not_duplicated", "Rules have one clear owner.", rule_ownership_is_not_duplicated),
    Invariant("standalone_use_is_preserved", "FlowGuard remains useful without OpenSpec/SPAC.", standalone_use_is_preserved),
    Invariant("heavy_checks_are_scoped", "Heavy framework checks do not over-trigger.", heavy_checks_are_scoped),
    Invariant("release_sync_stays_visible", "Release and install sync route stays visible.", release_sync_stays_visible),
    Invariant("testmesh_hierarchy_stays_visible", "TestMesh remains a sibling parent/child hierarchy route.", testmesh_hierarchy_stays_visible),
    Invariant("soft_oversize_hint_stays_visible", "Soft oversize split consideration remains visible.", soft_oversize_hint_stays_visible),
    Invariant("oversize_hint_remains_soft", "Oversize guidance is a consideration hint, not a gate.", oversize_hint_remains_soft),
    Invariant("planner_language_stays_generic", "Public planner language remains generic and optional.", planner_language_stays_generic),
    Invariant("model_test_alignment_route_stays_visible", "Model-test alignment has its own route.", model_test_alignment_route_stays_visible),
    Invariant("model_test_alignment_stays_independent", "Model-test alignment does not depend on mesh routes.", model_test_alignment_stays_independent),
)


def build_workflow() -> Workflow:
    return Workflow((EvaluateSkillKernelPlan(),), name="skill_kernel_modularization")


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(name: str, description: str, case: SkillKernelCase, expected: ScenarioExpectation) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        workflow=build_workflow(),
        initial_state=SkillKernelState(),
        external_input_sequence=(case,),
        invariants=INVARIANTS,
        expected=expected,
    )


SCENARIOS = (
    scenario("good_kernel_passes", "A compact router with complete references passes.", GOOD_KERNEL, _expect_ok("kernel passes", labels=("good_skill_kernel",))),
    scenario("buried_default_path_fails", "The thin default path must appear before advanced routes.", BROKEN_BURIED_DEFAULT_PATH, _expect_violation("buried default path fails", ("thin_default_path_stays_visible",))),
    scenario("advanced_routes_default_fails", "Advanced routes should be escalation paths, not first-step burden.", BROKEN_ADVANCED_ROUTES_DEFAULT, _expect_violation("advanced default fails", ("advanced_routes_are_escalations",))),
    scenario("public_internal_mixing_fails", "Public entry guidance must not be mixed with internal maintenance machinery.", BROKEN_PUBLIC_INTERNAL_MIXED, _expect_violation("public/internal boundary fails", ("public_internal_boundary_stays_visible",))),
    scenario("stale_satellite_topology_fails", "Satellite topology wording must track the current skill set.", BROKEN_STALE_SATELLITE_TOPOLOGY, _expect_violation("stale satellite topology fails", ("satellite_topology_stays_current",))),
    scenario("long_kernel_fails", "Main Skill must not remain a long combined policy.", BROKEN_LONG_KERNEL, _expect_violation("long kernel fails", ("kernel_stays_compact",))),
    scenario("missing_hard_gates_fail", "Hard gates must stay visible after modularization.", BROKEN_HARD_GATES, _expect_violation("missing hard gates fail", ("hard_gates_remain_visible",))),
    scenario("missing_route_fails", "Required sub-protocol routes must stay discoverable.", BROKEN_ROUTE_GAP, _expect_violation("route gap fails", ("subprotocol_routes_are_complete",))),
    scenario("helper_subskill_fails", "Helper APIs are not standalone sub-skills.", BROKEN_HELPER_SUBSKILL, _expect_violation("helper subskill fails", ("helper_apis_remain_helpers",))),
    scenario("duplicate_rule_owner_fails", "Rules should not be duplicated across protocols.", BROKEN_DUPLICATE_RULES, _expect_violation("duplicate rules fail", ("rule_ownership_is_not_duplicated",))),
    scenario("standalone_loss_fails", "OpenSpec/SPAC cannot become a hard prerequisite.", BROKEN_STANDALONE_LOSS, _expect_violation("standalone loss fails", ("standalone_use_is_preserved",))),
    scenario("heavy_overtrigger_fails", "Ordinary work should not run framework suites by default.", BROKEN_HEAVY_OVERTRIGGER, _expect_violation("heavy overtrigger fails", ("heavy_checks_are_scoped",))),
    scenario("release_sync_gap_fails", "Release/install/shadow/GitHub sync route must stay visible.", BROKEN_RELEASE_SYNC_GAP, _expect_violation("release sync gap fails", ("release_sync_stays_visible",))),
    scenario("testmesh_narrowing_fails", "TestMesh must stay parallel to ModelMesh and StructureMesh as a parent/child split route.", BROKEN_TESTMESH_NARROWING, _expect_violation("testmesh narrowing fails", ("testmesh_hierarchy_stays_visible",))),
    scenario("missing_oversize_hint_fails", "Oversized work should keep a short split consideration hint.", BROKEN_MISSING_OVERSIZE_HINT, _expect_violation("missing oversize hint fails", ("soft_oversize_hint_stays_visible",))),
    scenario("oversize_gate_fails", "Oversize guidance must not become a hard threshold or gate.", BROKEN_OVERSIZE_GATE, _expect_violation("oversize gate fails", ("oversize_hint_remains_soft",))),
    scenario("planner_tool_dependency_fails", "Public Skill wording must not depend on a named external planner.", BROKEN_PLANNER_TOOL_DEPENDENCY, _expect_violation("planner tool dependency fails", ("planner_language_stays_generic",))),
    scenario("missing_model_test_alignment_fails", "Model-test alignment needs a dedicated route.", BROKEN_MISSING_MODEL_TEST_ALIGNMENT, _expect_violation("missing model-test alignment fails", ("model_test_alignment_route_stays_visible",))),
    scenario("model_test_alignment_mesh_dependency_fails", "Model-test alignment must not require mesh routes.", BROKEN_MODEL_TEST_ALIGNMENT_MESH_DEPENDENCY, _expect_violation("mesh dependency fails", ("model_test_alignment_stays_independent",))),
)


def run_review():
    return review_scenarios(SCENARIOS)


if __name__ == "__main__":
    report = run_review()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)
