"""FlowGuard core engine API.

``import flowguard`` loads only this facade; core names load lazily from their
owning modules. Node kinds live in ``flowguard.validator`` and
``flowguard.ui_flow``; computed hints in ``flowguard.hazards``; parent-child
handoffs in ``flowguard.closure``; test shards in ``flowguard.pytest_shards_cli``.
Maps and code facts use ``flowguard.map.*`` (for example
``flowguard.map.facts.CodeFacts``). FlowGuard's own benchmark corpus uses
``flowguard.corpus`` and the other benchmark modules directly.
"""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.70.12"

# owner module -> public names
_PUBLIC_API: dict[str, tuple[str, ...]] = {
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
    ),
    "flowguard.conformance": (
        "ConformanceReport",
        "ConformanceRule",
        "ConformanceViolation",
        "default_conformance_rules",
        "projected_output_matches",
        "projected_state_matches",
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
    "flowguard.core": (
        "FunctionBlock",
        "FunctionResult",
        "Invariant",
        "InvariantResult",
    ),
    "flowguard.explorer": (
        "Explorer",
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
        "feature_conformance",
        "feature_explorer",
        "feature_variants",
        "reachable_states",
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
        "trace_artifact",
    ),
    "flowguard.templates": (
        "TemplateFile",
        "adoption_template_files",
        "validator_template_files",
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
            from .map.retired import retired_public_name_message
            retired = retired_public_name_message(name)
            if retired:
                raise ImportError(retired) from None
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
        globals()[name] = module
        return module
    value = getattr(importlib.import_module(owner), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
