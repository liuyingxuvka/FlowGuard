from dataclasses import is_dataclass
from pathlib import Path
import unittest

import flowguard
import flowguard.development_process_strategy as optimization


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_OPTIMIZER_API = (
    "ProcessOptimizationContract",
    "ProcessOptimizationCandidate",
    "ProcessRepairGroup",
    "ProcessOptimizationDecision",
    "ProcessOptimizationReport",
    "review_process_optimization",
)

RETIRED_RUNTIME_NAMES = (
    "ProcessOutcomeContract",
    "ProcessCostVector",
    "ProcessCandidate",
    "DiagnosticCampaign",
    "FailureObservation",
    "FailureCluster",
    "RootCauseHypothesis",
    "RepairBatch",
    "StrategyReevaluation",
    "ProcessDependencyGraph",
    "DevelopmentProcessStrategyPlan",
    "ProcessStrategyFinding",
    "ProcessStrategyReport",
    "pareto_frontier",
    "failure_observations_from_finding_ledger",
    "spec_work_package_dependency_graph",
    "review_development_process_strategy",
    "ProcessStrategyAlignmentBinding",
)

RETIRED_CURRENT_PATH_TOKENS = RETIRED_RUNTIME_NAMES + (
    "PROCESS_STRATEGY_FAIL_FAST",
    "PROCESS_STRATEGY_COLLECT_ALL",
    "PROCESS_STRATEGY_FOCUSED_FIRST",
    "PROCESS_STRATEGY_BOUNDED_COLLECT",
    "PROCESS_STRATEGY_PARALLEL_SHARDS",
    "PROCESS_STRATEGY_ADAPTIVE",
    "PROCESS_STRATEGIES",
    "STRATEGY_ROLLOUT_",
    "CAMPAIGN_ENUMERATION_",
    "STRATEGY_OPTIMALITY_",
    "strategy_bindings",
    "strategy_binding_",
    "strategy_selection_required",
    "required_strategy_evidence_ids",
    "strategy_rollout_stage",
    "strategy_enforcement_required",
    "selected_process_strategy",
    "strategy_decision_evidence_ids",
    "strategy_reevaluation_evidence_ids",
    "failure_observation_ids",
    "failure_cluster_ids",
    "execution_policy",
    "enumeration_status",
    "early_stop_reason",
)


def current_guidance_files():
    roots = (
        ROOT / "flowguard",
        ROOT / ".agents" / "skills" / "flowguard-development-process-flow",
        ROOT / ".agents" / "skills" / "flowguard-test-mesh",
    )
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".md", ".yaml", ".yml"}:
                yield path
    for relative in (
        "AGENTS.md",
        "docs/agents_snippet.md",
        "docs/api_surface.md",
        "docs/development_process_flow.md",
        "docs/development_process_strategy_selection.md",
        "docs/test_evidence_mesh.md",
    ):
        yield ROOT / relative


class ProcessOptimizationZeroResidualTests(unittest.TestCase):
    def test_optimizer_public_surface_is_exactly_five_records_and_one_review(self):
        self.assertEqual(PUBLIC_OPTIMIZER_API, tuple(optimization.__all__))
        record_names = tuple(
            name for name in PUBLIC_OPTIMIZER_API if is_dataclass(getattr(optimization, name))
        )
        self.assertEqual(PUBLIC_OPTIMIZER_API[:5], record_names)
        process_api = set(flowguard.FLOWGUARD_ROUTE_API["development_process_flow"])
        self.assertTrue(set(PUBLIC_OPTIMIZER_API).issubset(process_api))
        self.assertNotIn("development_process_strategy", flowguard.FLOWGUARD_ROUTE_API)

    def test_retired_runtime_names_have_no_public_authority(self):
        for name in RETIRED_RUNTIME_NAMES:
            with self.subTest(name=name):
                self.assertFalse(hasattr(flowguard, name), name)
                self.assertNotIn(name, flowguard.__all__)

    def test_optimizer_implementation_stays_within_small_source_budget(self):
        path = ROOT / "flowguard" / "development_process_strategy.py"
        nonblank = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        self.assertLessEqual(nonblank, 500)

    def test_current_runtime_and_guidance_have_no_retired_success_vocabulary(self):
        violations = []
        for path in current_guidance_files():
            text = path.read_text(encoding="utf-8")
            for token in RETIRED_CURRENT_PATH_TOKENS:
                if token in text:
                    violations.append(f"{path.relative_to(ROOT)}: {token}")
        self.assertEqual([], violations, "\n".join(violations))

    def test_retired_public_mode_skills_are_absent_and_internal_routes_are_current(self):
        skills = ROOT / ".agents" / "skills"
        self.assertFalse((skills / "flowguard-plan-detailing-compiler").exists())
        self.assertFalse((skills / "flowguard-agent-workflow-rehearsal").exists())
        dpf = skills / "flowguard-development-process-flow"
        self.assertTrue((dpf / "references" / "plan_detailing_protocol.md").is_file())
        self.assertTrue((dpf / "references" / "agent_workflow_protocol.md").is_file())


if __name__ == "__main__":
    unittest.main()
