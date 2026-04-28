"""flowguard: executable function-flow models for model-first engineering."""

from .adoption import (
    ADOPTION_STATUSES,
    AdoptionCommandResult,
    AdoptionLogEntry,
    AdoptionTimer,
    append_jsonl,
    append_markdown_log,
    make_adoption_log_entry,
    utc_now_text,
)
from .checks import no_duplicate_values, require_label, require_reachable, state_invariant
from .baseline import (
    EvidenceBaselineReport,
    EvidenceCaseResult,
    build_evidence_baseline_report,
)
from .benchmark import BenchmarkScorecard, build_benchmark_scorecard
from .corpus import (
    ProblemCase,
    ProblemCorpus,
    ProblemCorpusReport,
    build_problem_corpus_report,
)
from .executable import (
    ExecutableCaseResult,
    ExecutableCorpusReport,
    build_executable_corpus_report,
)
from .conformance import (
    ConformanceReport,
    ConformanceRule,
    ConformanceViolation,
    default_conformance_rules,
    replay_trace,
)
from .contract import (
    ContractCheckReport,
    ContractViolation,
    FunctionContract,
    check_refinement_projection,
    check_trace_contracts,
)
from .coverage import (
    BenchmarkCoverageAudit,
    build_benchmark_coverage_audit,
)
from .core import FunctionBlock, FunctionResult, Invariant, InvariantResult
from .explorer import Explorer, ReachabilityCondition, enumerate_input_sequences
from .export import to_json_text, to_jsonable
from .loop import GraphEdge, LoopCheckConfig, LoopCheckReport, check_loops, tarjan_scc
from .progress import (
    BoundedEventuallyProperty,
    EventuallyProperty,
    ProgressCheckConfig,
    ProgressCheckReport,
    ProgressFinding,
    check_progress,
)
from .pytest_adapter import assert_no_executable_corpus_regression, assert_report_ok
from .report import (
    CheckReport,
    DeadBranch,
    ExceptionBranch,
    InvariantViolation,
    ReachabilityFailure,
)
from .replay import ReplayAdapter, ReplayObservation
from .review import OracleReviewResult, ScenarioReviewReport, review_scenario, review_scenarios
from .scenario import (
    OracleCheckResult,
    Scenario,
    ScenarioExpectation,
    ScenarioRun,
    run_exact_sequence,
)
from .schema import ArtifactEnvelope, SCHEMA_VERSION, make_artifact, report_artifact, trace_artifact
from .templates import TemplateFile, adoption_template_files, project_template_files
from .trace import Trace, TraceStep
from .workflow import Workflow, WorkflowPath, WorkflowRun

__all__ = [
    "AdoptionCommandResult",
    "AdoptionLogEntry",
    "AdoptionTimer",
    "ADOPTION_STATUSES",
    "CheckReport",
    "ConformanceReport",
    "ConformanceRule",
    "ConformanceViolation",
    "ContractCheckReport",
    "ContractViolation",
    "BoundedEventuallyProperty",
    "DeadBranch",
    "EvidenceBaselineReport",
    "EvidenceCaseResult",
    "EventuallyProperty",
    "BenchmarkScorecard",
    "BenchmarkCoverageAudit",
    "ExecutableCaseResult",
    "ExecutableCorpusReport",
    "ExceptionBranch",
    "Explorer",
    "FunctionBlock",
    "FunctionContract",
    "FunctionResult",
    "GraphEdge",
    "Invariant",
    "InvariantResult",
    "InvariantViolation",
    "LoopCheckConfig",
    "LoopCheckReport",
    "OracleCheckResult",
    "OracleReviewResult",
    "ProblemCase",
    "ProblemCorpus",
    "ProblemCorpusReport",
    "ProgressCheckConfig",
    "ProgressCheckReport",
    "ProgressFinding",
    "ReachabilityCondition",
    "ReachabilityFailure",
    "ReplayAdapter",
    "ReplayObservation",
    "Scenario",
    "ScenarioExpectation",
    "ScenarioReviewReport",
    "ScenarioRun",
    "ArtifactEnvelope",
    "SCHEMA_VERSION",
    "TemplateFile",
    "Trace",
    "TraceStep",
    "Workflow",
    "WorkflowPath",
    "WorkflowRun",
    "check_loops",
    "check_progress",
    "check_refinement_projection",
    "check_trace_contracts",
    "assert_no_executable_corpus_regression",
    "assert_report_ok",
    "append_jsonl",
    "append_markdown_log",
    "adoption_template_files",
    "build_executable_corpus_report",
    "build_benchmark_scorecard",
    "build_benchmark_coverage_audit",
    "build_evidence_baseline_report",
    "build_problem_corpus_report",
    "enumerate_input_sequences",
    "default_conformance_rules",
    "no_duplicate_values",
    "require_label",
    "require_reachable",
    "replay_trace",
    "review_scenario",
    "review_scenarios",
    "run_exact_sequence",
    "make_artifact",
    "make_adoption_log_entry",
    "project_template_files",
    "report_artifact",
    "state_invariant",
    "tarjan_scc",
    "trace_artifact",
    "to_json_text",
    "to_jsonable",
    "utc_now_text",
]
