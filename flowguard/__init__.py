"""FlowGuard public API.

``import flowguard`` loads only this file.  Each public name below is loaded
from its owning module the first time it is used.  The table is plain data:
when a module's public names change, edit the table and run
``python -m pytest tests/test_public_api.py``.
"""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.70.10"

# owner module -> public names
_PUBLIC_API: dict[str, tuple[str, ...]] = {
    "flowguard._hashing": (
        "canonical_fingerprint",
    ),
    "flowguard.baseline": (
        "EvidenceBaselineReport",
        "EvidenceCaseResult",
        "build_evidence_baseline_report",
    ),
    "flowguard.benchmark": (
        "BenchmarkScorecard",
        "build_benchmark_scorecard",
    ),
    "flowguard.budgeted": (
        "BudgetedGraphConfig",
        "BudgetedGraphFailure",
        "BudgetedGraphReport",
        "BudgetedShardReport",
        "budgeted_graph_fingerprint",
        "budgeted_graph_run_dir",
        "run_budgeted_graph_checks",
    ),
    "flowguard.checks": (
        "all_items_have_source",
        "at_most_once_by",
        "cache_matches_source",
        "forbid_label_after",
        "no_contradictory_values",
        "no_duplicate_by",
        "no_duplicate_values",
        "only_named_block_writes",
        "require_label",
        "require_label_order",
        "require_reachable",
        "state_invariant",
    ),
    "flowguard.conformance": (
        "ConformanceReport",
        "ConformanceRule",
        "ConformanceViolation",
        "default_conformance_rules",
        "replay_trace",
        "select_covering_traces",
    ),
    "flowguard.contract": (
        "ContractCheckReport",
        "ContractViolation",
        "FunctionContract",
        "check_refinement_projection",
        "check_trace_contracts",
    ),
    "flowguard.contract_exhaustion": (
        "CONTRACT_COVERAGE_STATUS_BLOCKED",
        "CONTRACT_COVERAGE_STATUS_COVERED",
        "CONTRACT_COVERAGE_STATUS_IN_PROGRESS",
        "CONTRACT_COVERAGE_STATUS_SCOPED",
        "CONTRACT_DIMENSION_EVIDENCE",
        "CONTRACT_DIMENSION_FIELD",
        "CONTRACT_DIMENSION_INPUT",
        "CONTRACT_DIMENSION_LOOP",
        "CONTRACT_DIMENSION_PARENT_CHILD",
        "CONTRACT_DIMENSION_PAYLOAD",
        "CONTRACT_DIMENSION_SAME_CLASS",
        "CONTRACT_DIMENSION_STATE",
        "CONTRACT_DIMENSION_TRANSITION",
        "CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED",
        "CONTRACT_EXHAUSTION_CONFIDENCE_FULL",
        "CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED",
        "CONTRACT_EXHAUSTION_DECISION_BLOCKED",
        "CONTRACT_EXHAUSTION_DECISION_READY",
        "CONTRACT_EXHAUSTION_DECISION_SCOPED",
        "CONTRACT_EXHAUSTION_FINDING_BLOCKER",
        "CONTRACT_EXHAUSTION_FINDING_GAP",
        "CONTRACT_EXHAUSTION_FINDING_INFO",
        "CONTRACT_EXHAUSTION_ROUTE",
        "CONTRACT_GENERATION_LOCAL_CARTESIAN",
        "CONTRACT_GENERATION_PARENT_INTERFACE",
        "CONTRACT_GENERATION_SINGLE_DIMENSION",
        "CONTRACT_MODEL_LEVEL_CHILD",
        "CONTRACT_MODEL_LEVEL_LEAF",
        "CONTRACT_MODEL_LEVEL_PARENT",
        "CONTRACT_MODEL_LEVEL_ROOT",
        "CONTRACT_MUTATION_CARTESIAN_COMBINATION",
        "CONTRACT_MUTATION_CONFLICTING_PAYLOAD",
        "CONTRACT_MUTATION_EMPTY_VALUE",
        "CONTRACT_MUTATION_MALFORMED_INPUT",
        "CONTRACT_MUTATION_MISSING_BODY",
        "CONTRACT_MUTATION_MISSING_EVIDENCE_FILE",
        "CONTRACT_MUTATION_MISSING_REQUIRED_FIELD",
        "CONTRACT_MUTATION_OMITTED_FAMILY_MEMBER",
        "CONTRACT_MUTATION_OMITTED_REDUCTION_CANDIDATE",
        "CONTRACT_MUTATION_PATH_MISMATCH",
        "CONTRACT_MUTATION_RELATION_MATERIALIZATION",
        "CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA",
        "CONTRACT_MUTATION_SAME_CLASS_CASE",
        "CONTRACT_MUTATION_SCENARIO_CHALLENGE",
        "CONTRACT_MUTATION_STALE_CHILD_EVIDENCE",
        "CONTRACT_MUTATION_STALE_EVIDENCE",
        "CONTRACT_MUTATION_TRANSITION_REPLAY",
        "CONTRACT_MUTATION_UNCONSUMED_CHILD_EVIDENCE",
        "CONTRACT_MUTATION_UNKNOWN_ENUM",
        "CONTRACT_MUTATION_UNMATERIALIZED_RELATION_ID",
        "CONTRACT_MUTATION_WRONG_TYPE",
        "CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM",
        "CONTRACT_ORACLE_MARK_STALE",
        "CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW",
        "CONTRACT_ORACLE_NO_DELTA_LOOP_BLOCK",
        "CONTRACT_ORACLE_PASS_ALLOWED",
        "CONTRACT_ORACLE_REISSUE_WITH_REPAIR_INFO",
        "CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT",
        "CONTRACT_ORACLE_SCOPED_CONFIDENCE",
        "CONTRACT_ROUTE_FIELD_LIFECYCLE",
        "CONTRACT_ROUTE_MODEL_MESH",
        "CONTRACT_ROUTE_MODEL_MISS_REVIEW",
        "CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT",
        "CONTRACT_ROUTE_OBLIGATION_FAMILY",
        "CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER",
        "CONTRACT_ROUTE_TEST_MESH",
        "CONTRACT_STRICT_CLAIM_SCOPES",
        "CompositeHandoffAcceptance",
        "CompositeHandoffResult",
        "ContractAxis",
        "ContractCombinationCase",
        "ContractCoverageExclusion",
        "ContractCoverageShard",
        "ContractCoverageUniverse",
        "ContractDimension",
        "ContractExhaustionFinding",
        "ContractExhaustionPlan",
        "ContractExhaustionReport",
        "ContractFaultProfile",
        "ContractInteractionGroup",
        "ContractMutationCase",
        "ContractOracle",
        "ContractProductSignature",
        "DEFAULT_CARTESIAN_CASE_LIMIT",
        "ObservedProblemBackfeed",
        "ObservedProblemBackfeedReport",
        "build_contract_product_signature",
        "contract_exhaustion_features",
        "contract_exhaustion_to_composite_handoff_acceptance_ids",
        "contract_exhaustion_to_risk_gate_ids",
        "contract_exhaustion_to_test_mesh_cell_ids",
        "contract_exhaustion_to_test_mesh_shard_ids",
        "contract_fault_profiles_from_report",
        "execute_contract_features",
        "review_contract_exhaustion",
        "review_observed_problem_backfeed",
        "scenario_matrix_to_contract_cases",
    ),
    "flowguard.core": (
        "FunctionBlock",
        "FunctionResult",
        "Invariant",
        "InvariantResult",
    ),
    "flowguard.corpus": (
        "ProblemCase",
        "ProblemCorpus",
        "ProblemCorpusReport",
        "build_problem_corpus_report",
    ),
    "flowguard.coverage": (
        "BenchmarkCoverageAudit",
        "build_benchmark_coverage_audit",
    ),
    "flowguard.executable": (
        "ExecutableCaseResult",
        "ExecutableCorpusReport",
        "build_executable_corpus_report",
    ),
    "flowguard.explorer": (
        "ReachabilityCondition",
        "enumerate_input_sequences",
    ),
    "flowguard.export": (
        "to_json_text",
        "to_jsonable",
    ),
    "flowguard.kit": (
        "FEATURE_INVARIANTS",
        "Feature",
        "FeatureReport",
        "FeatureState",
        "FeatureViolation",
        "PlanState",
        "feature_conformance",
        "feature_explorer",
        "feature_variants",
        "plan_explorer",
        "review_invariant",
    ),
    "flowguard.loop": (
        "GraphEdge",
        "LoopCheckConfig",
        "LoopCheckReport",
        "check_loops",
        "tarjan_scc",
    ),
    "flowguard.mermaid": (
        "graph_to_mermaid_text",
        "loop_report_to_mermaid_text",
        "mermaid_code_block",
        "trace_to_mermaid_text",
    ),
    "flowguard.minimize": (
        "MinimizedCounterexample",
        "ReductionStep",
        "minimize_failing_sequence",
        "minimize_report_counterexample",
    ),
    "flowguard.packs": (
        "CachePack",
        "DeduplicationPack",
        "RetryPack",
        "SideEffectPack",
    ),
    "flowguard.progress": (
        "BoundedEventuallyProperty",
        "EventuallyProperty",
        "ProgressCheckConfig",
        "ProgressCheckReport",
        "ProgressFinding",
        "check_progress",
    ),
    "flowguard.replay": (
        "ReplayAdapter",
        "ReplayObservation",
    ),
    "flowguard.report": (
        "CheckReport",
        "DeadBranch",
        "ExceptionBranch",
        "InvariantViolation",
        "ReachabilityFailure",
    ),
    "flowguard.review": (
        "OracleReviewResult",
        "ScenarioReviewReport",
        "review_scenario",
        "review_scenarios",
        "scenario_status_explanation",
        "scenario_status_ok",
    ),
    "flowguard.scenario": (
        "OracleCheckResult",
        "Scenario",
        "ScenarioExpectation",
        "ScenarioRun",
        "run_exact_sequence",
    ),
    "flowguard.scenario_matrix": (
        "ScenarioMatrixBuilder",
    ),
    "flowguard.schema": (
        "ArtifactEnvelope",
        "SCHEMA_VERSION",
        "make_artifact",
        "report_artifact",
        "trace_artifact",
    ),
    "flowguard.templates": (
        "TemplateFile",
        "adoption_template_files",
        "contract_exhaustion_template_files",
        "ui_journey_template_files",
        "write_template_files",
    ),
    "flowguard.trace": (
        "Trace",
        "TraceStep",
    ),
    "flowguard.workflow": (
        "Workflow",
        "WorkflowPath",
        "WorkflowRun",
    ),
}

_OWNER: dict[str, str] = {name: owner for owner, group in _PUBLIC_API.items() for name in group}
__all__ = sorted(_OWNER)


def __getattr__(name: str) -> Any:
    owner = _OWNER.get(name)
    if owner is None:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise
            retired = {"ModelAuthoritySnapshot", "ModelRevisionSet", "ModelAuthority", "ModelAuthorityStore",
                       "model_authority_snapshot", "RuntimeGateway"}
            if name in retired:
                raise ImportError(f"{name} retired in 0.70.0; see references/upgrade.md") from None
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
        globals()[name] = module
        return module
    value = getattr(importlib.import_module(owner), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
