"""FlowGuard rollout model for model/test/code contract alignment.

Risk Purpose Header:
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the Model-Test Alignment upgrade that binds model obligations,
owner code contracts, source audit, closure targets, and test evidence.
Guards against: green alignment claims when a model obligation has no code
contract, a code contract misses or adds external behavior, a test does not
bind the code contract it proves, a test checks only internal paths, source
audit is missing for real-code claims, or a counterexample lacks target-aware
owner-code replay evidence. It also keeps pre-code design separate from
executed evidence, requires one exact leaf receipt per execution owner, rejects
a validation-parent receipt used as a leaf, and preserves bidirectional
model/implementation traceability. Plane-aware obligations also block when
product runtime, AI operation, and development-process evidence are mixed.

Run:
python .flowguard/model_test_code_alignment/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import (
    CodeContract,
    ClosureEvidenceTarget,
    ModelObligation,
    ModelTestAlignmentPlan,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
    TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    CODE_CONTRACT_ROLE_FACADE,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
    review_model_test_alignment,
)
from flowguard.software_blueprint_readiness import DelegatedAssertionHelper


@dataclass(frozen=True)
class RolloutCase:
    name: str
    plan: ModelTestAlignmentPlan
    expected_ok: bool
    expected_codes: tuple[str, ...] = ()
    expected_pre_code_status: str = ""
    expected_executed_evidence_status: str = ""


# These are part of this model's native evidence contract, not a broad suite.
# The runner executes them in the same foreground command as the rollout cases
# so SkillGuard's native owner cannot claim alignment from the model alone.
NATIVE_PYTEST_SELECTORS = (
    "tests/test_model_test_alignment.py",
    "tests/test_implementation_blueprint.py::test_binding_review_is_bidirectional_and_exposes_integration_protocol",
    "tests/test_implementation_blueprint.py::test_path_binding_without_semantics_and_oracles_is_only_traceability",
    "tests/test_project_blueprint.py::test_shared_test_glob_is_supporting_and_does_not_grant_coverage_ownership",
    "tests/test_project_blueprint.py::test_same_owner_behavior_contracts_are_partitioned_by_block",
    "tests/test_project_blueprint.py::test_external_python_project_uses_generic_read_only_builder",
    "tests/test_software_blueprint_readiness.py::test_exact_current_leaf_receipt_closes_executed_evidence",
    "tests/test_software_blueprint_readiness.py::test_execution_receipt_rules_remain_separate_from_design",
    "tests/test_software_blueprint_readiness.py::test_not_run_skip_or_xfail_dispositions_never_become_executed_pass",
    "tests/test_software_blueprint_readiness.py::test_portable_binding_must_preserve_the_protected_failure_boundary",
    "tests/test_software_blueprint_readiness.py::test_sibling_blocks_cannot_borrow_case_design_or_coverage",
    "tests/test_software_blueprint_readiness.py::test_delegated_assertion_helpers_require_current_terminal_acyclic_paths",
    "tests/test_software_blueprint_readiness.py::test_placeholder_or_cross_test_member_cannot_close_coverage",
    "tests/test_software_blueprint_readiness.py::test_validation_parent_receipt_cannot_impersonate_leaf_coverage",
    "tests/test_software_blueprint_readiness.py::test_one_receipt_cannot_be_reused_across_execution_owners",
    "tests/test_validation_execution_ownership.py::ValidationExecutionOwnershipTests::test_child_bound_owner_receipt_consumes_real_verified_child",
    "tests/test_model_revision_owner_evidence.py::ModelRevisionOwnerEvidenceTests::test_produces_distinct_child_bound_owner_receipts_accepted_by_builder",
)

NATIVE_TEST_OBLIGATION_BINDINGS = (
    (
        "pre_code_design_is_not_execution",
        "tests/test_model_test_alignment.py::ModelTestAlignmentTests::test_pre_code_design_ready_does_not_promote_not_run_evidence",
    ),
    (
        "blueprint_traceability_is_bidirectional_and_not_semantic_proof",
        "tests/test_implementation_blueprint.py::test_path_binding_without_semantics_and_oracles_is_only_traceability",
    ),
    (
        "executed_pass_requires_exact_current_owner_leaf",
        "tests/test_software_blueprint_readiness.py::test_exact_current_leaf_receipt_closes_executed_evidence",
    ),
    (
        "validation_parent_cannot_replace_owner_leaf",
        "tests/test_software_blueprint_readiness.py::test_validation_parent_receipt_cannot_impersonate_leaf_coverage",
    ),
    (
        "one_leaf_receipt_cannot_be_reused_across_owners",
        "tests/test_software_blueprint_readiness.py::test_one_receipt_cannot_be_reused_across_execution_owners",
    ),
    (
        "block_local_failures_cannot_be_copied_to_siblings",
        "tests/test_software_blueprint_readiness.py::test_portable_binding_must_preserve_the_protected_failure_boundary",
    ),
    (
        "owner_wide_result_is_not_leaf_execution",
        "tests/test_software_blueprint_readiness.py::test_execution_receipt_rules_remain_separate_from_design",
    ),
    (
        "planned_checker_without_leaf_receipt_stays_not_run",
        "tests/test_software_blueprint_readiness.py::test_not_run_skip_or_xfail_dispositions_never_become_executed_pass",
    ),
    (
        "sibling_case_and_checker_evidence_remains_partitioned",
        "tests/test_software_blueprint_readiness.py::test_sibling_blocks_cannot_borrow_case_design_or_coverage",
    ),
    (
        "coverage_owner_comes_from_exact_coverage_contract",
        "tests/test_project_blueprint.py::test_shared_test_glob_is_supporting_and_does_not_grant_coverage_ownership",
    ),
    (
        "behavior_block_implementation_binding_is_distinct_from_model_owner",
        "tests/test_project_blueprint.py::test_external_python_project_uses_generic_read_only_builder",
    ),
    (
        "delegated_checker_requires_current_terminal_graph",
        "tests/test_software_blueprint_readiness.py::test_delegated_assertion_helpers_require_current_terminal_acyclic_paths",
    ),
    (
        "delegated_checker_cannot_borrow_sibling_test_ownership",
        "tests/test_software_blueprint_readiness.py::test_placeholder_or_cross_test_member_cannot_close_coverage",
    ),
)


def native_test_obligation_bindings_are_executed() -> bool:
    """Require every declared native obligation to reach an executed selector."""

    obligation_ids = tuple(item[0] for item in NATIVE_TEST_OBLIGATION_BINDINGS)
    evidence_nodes = tuple(item[1] for item in NATIVE_TEST_OBLIGATION_BINDINGS)
    selected = set(NATIVE_PYTEST_SELECTORS)
    selected_files = {selector for selector in selected if "::" not in selector}
    return (
        len(obligation_ids) == len(set(obligation_ids))
        and len(evidence_nodes) == len(set(evidence_nodes))
        and all(
            node in selected or node.split("::", 1)[0] in selected_files
            for node in evidence_nodes
        )
    )


@dataclass(frozen=True)
class DelegatedHelperGraphInput:
    """One finite delegated-checker graph and its exact coverage ownership."""

    scenario_id: str
    helpers: tuple[DelegatedAssertionHelper, ...]
    expected_helper_fingerprints: tuple[tuple[str, str], ...]
    current_terminal_fingerprints: tuple[tuple[str, str], ...]
    test_helper_calls: tuple[tuple[str, str], ...]
    coverage_checker_bindings: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class DelegatedHelperGraphState:
    phase: str = "start"
    terminal_member_ids: tuple[str, ...] = ()
    registered_helper_ids: tuple[str, ...] = ()
    helper_owner_bindings: tuple[tuple[str, str], ...] = ()
    coverage_checker_bindings: tuple[tuple[str, str, str], ...] = ()
    pre_code_status: str = "not_run"
    finding_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DelegatedHelperGraphOutput:
    scenario_id: str
    ok: bool
    pre_code_status: str
    finding_codes: tuple[str, ...]


@dataclass(frozen=True)
class DelegatedHelperGraphCase:
    name: str
    model_input: DelegatedHelperGraphInput
    expected_ok: bool
    expected_codes: tuple[str, ...] = ()


def delegated_helper_graph_transition(
    model_input: DelegatedHelperGraphInput,
    state: DelegatedHelperGraphState,
) -> tuple[tuple[DelegatedHelperGraphOutput, DelegatedHelperGraphState], ...]:
    """Resolve helper calls only when every branch reaches current evidence."""

    if state.phase != "start":
        output = DelegatedHelperGraphOutput(
            model_input.scenario_id,
            False,
            "blocked",
            ("delegated_helper_graph_reentry",),
        )
        return ((output, replace(
            state,
            phase="blocked",
            pre_code_status="blocked",
            finding_codes=output.finding_codes,
        )),)

    findings: set[str] = set()
    expected = dict(model_input.expected_helper_fingerprints)
    member_fingerprints = dict(model_input.current_terminal_fingerprints)
    helper_by_id: dict[str, DelegatedAssertionHelper] = {}
    helper_direct_terminal_valid: dict[str, bool] = {}
    for helper in model_input.helpers:
        direct_terminal_valid = True
        if helper.helper_id in helper_by_id:
            findings.add("duplicate_delegated_assertion_helper")
        helper_by_id[helper.helper_id] = helper
        expected_fingerprint = expected.get(helper.helper_id)
        if (
            expected_fingerprint is not None
            and expected_fingerprint != helper.source_fingerprint
        ):
            findings.add("delegated_assertion_helper_stale")
        for terminal_id, terminal_fingerprint in (
            helper.terminal_member_fingerprints
        ):
            current = member_fingerprints.get(terminal_id)
            if current is not None and current != terminal_fingerprint:
                findings.add("delegated_assertion_terminal_stale")
                direct_terminal_valid = False
            else:
                member_fingerprints[terminal_id] = terminal_fingerprint
        helper_direct_terminal_valid[helper.helper_id] = direct_terminal_valid

    terminal_member_ids = set(member_fingerprints)
    helper_state: dict[str, bool] = {}

    def reaches_terminal(
        helper_id: str,
        stack: tuple[str, ...] = (),
    ) -> bool:
        if helper_id in helper_state:
            return helper_state[helper_id]
        if helper_id in stack:
            findings.add("delegated_assertion_helper_cycle")
            helper_state[helper_id] = False
            return False
        helper = helper_by_id[helper_id]
        reaches = bool(helper.terminal_member_fingerprints)
        valid = helper_direct_terminal_valid[helper_id]
        for callee_id in helper.callee_member_ids:
            if callee_id in terminal_member_ids:
                reaches = True
            elif callee_id in helper_by_id:
                child_ok = reaches_terminal(
                    callee_id,
                    stack + (helper_id,),
                )
                reaches = reaches or child_ok
                valid = valid and child_ok
            else:
                findings.add("delegated_assertion_terminal_missing")
                valid = False
        helper_state[helper_id] = valid and reaches
        return helper_state[helper_id]

    registered_helper_ids = {
        helper_id
        for helper_id in helper_by_id
        if reaches_terminal(helper_id)
    }
    helper_owner = {
        helper_id: helper_by_id[helper_id].test_node_id
        for helper_id in registered_helper_ids
    }

    def helper_leaf(helper_id: str) -> str:
        return helper_id.rsplit("::", 1)[-1].rsplit(".", 1)[-1]

    helper_ids_by_leaf: dict[str, set[str]] = {}
    for helper_id in helper_by_id:
        helper_ids_by_leaf.setdefault(helper_leaf(helper_id), set()).add(
            helper_id
        )
    registered_names = {
        name
        for helper_id in helper_by_id
        for name in (helper_id, helper_leaf(helper_id))
    }
    for test_node_id, call in model_input.test_helper_calls:
        leaf = call.rsplit(".", 1)[-1]
        candidates = helper_ids_by_leaf.get(leaf, set())
        if len(candidates) >= 2:
            exact_owners = {
                helper_id
                for helper_id in candidates
                if helper_by_id[helper_id].test_node_id == test_node_id
            }
            if len(exact_owners) != 1:
                findings.add("ambiguous_delegated_assertion_helper")
        if (
            leaf.startswith("assert_")
            and call not in registered_names
            and leaf not in registered_names
        ):
            findings.add("unregistered_assertion_helper")

    known_members = terminal_member_ids | registered_helper_ids
    for _coverage_id, checker_id, test_node_id in (
        model_input.coverage_checker_bindings
    ):
        if checker_id not in known_members:
            findings.add("coverage_oracle_member_missing")
            continue
        checker_owner = helper_owner.get(checker_id)
        if checker_owner is not None and checker_owner != test_node_id:
            findings.add("coverage_cross_test_member")

    finding_codes = tuple(sorted(findings))
    pre_code_status = "blocked" if finding_codes else "ready"
    next_state = DelegatedHelperGraphState(
        phase="reviewed",
        terminal_member_ids=tuple(sorted(known_members)),
        registered_helper_ids=tuple(sorted(registered_helper_ids)),
        helper_owner_bindings=tuple(sorted(helper_owner.items())),
        coverage_checker_bindings=tuple(
            sorted(model_input.coverage_checker_bindings)
        ),
        pre_code_status=pre_code_status,
        finding_codes=finding_codes,
    )
    output = DelegatedHelperGraphOutput(
        model_input.scenario_id,
        not finding_codes,
        pre_code_status,
        finding_codes,
    )
    return ((output, next_state),)


def delegated_helper_graph_invariants(
    model_input: DelegatedHelperGraphInput,
    state: DelegatedHelperGraphState,
) -> bool:
    codes = set(state.finding_codes)
    if (state.pre_code_status == "ready") != (not codes):
        return False
    registered = set(state.registered_helper_ids)
    known = set(state.terminal_member_ids)
    owners = dict(state.helper_owner_bindings)
    if registered - set(owners):
        return False
    for _coverage_id, checker_id, test_node_id in (
        model_input.coverage_checker_bindings
    ):
        if checker_id not in known and "coverage_oracle_member_missing" not in codes:
            return False
        if (
            checker_id in owners
            and owners[checker_id] != test_node_id
            and "coverage_cross_test_member" not in codes
        ):
            return False
    return True


def delegated_helper_graph_rollout_cases() -> tuple[
    DelegatedHelperGraphCase, ...
]:
    helper_id = "fixture.assert_saved"
    helper_fingerprint = "sha256:helper-current"
    terminal_id = "delegated-terminal:assert-saved"
    terminal_fingerprint = "sha256:terminal-current"
    direct = DelegatedAssertionHelper(
        helper_id,
        "test:save",
        helper_fingerprint,
        (),
        ((terminal_id, terminal_fingerprint),),
    )
    base = DelegatedHelperGraphInput(
        "delegated_direct_terminal",
        (direct,),
        ((helper_id, helper_fingerprint),),
        (),
        (("test:save", "assert_saved"),),
        (("coverage:save", helper_id, "test:save"),),
    )
    first = replace(
        direct,
        helper_id="fixture_a.assert_saved",
        source_fingerprint="sha256:helper-a",
        terminal_member_fingerprints=(
            ("delegated-terminal:helper-a", "sha256:terminal-a"),
        ),
    )
    second = replace(
        direct,
        helper_id="fixture_b.assert_saved",
        source_fingerprint="sha256:helper-b",
        terminal_member_fingerprints=(
            ("delegated-terminal:helper-b", "sha256:terminal-b"),
        ),
    )
    cyclic_first = replace(
        direct,
        callee_member_ids=("fixture.assert_other",),
        terminal_member_fingerprints=(),
    )
    cyclic_second = DelegatedAssertionHelper(
        "fixture.assert_other",
        "test:save",
        "sha256:helper-other",
        (helper_id,),
    )
    return (
        DelegatedHelperGraphCase(
            "delegated_direct_terminal_is_current",
            base,
            True,
        ),
        DelegatedHelperGraphCase(
            "delegated_terminal_stale_blocks",
            replace(
                base,
                scenario_id="delegated_terminal_stale",
                helpers=(
                    replace(
                        direct,
                        terminal_member_fingerprints=(
                            ("assertion:save", "sha256:terminal-stale"),
                        ),
                    ),
                ),
                current_terminal_fingerprints=(
                    ("assertion:save", "sha256:terminal-current"),
                ),
            ),
            False,
            ("delegated_assertion_terminal_stale",),
        ),
        DelegatedHelperGraphCase(
            "delegated_terminal_ambiguity_blocks",
            replace(
                base,
                scenario_id="delegated_terminal_ambiguous",
                helpers=(first, second),
                expected_helper_fingerprints=(
                    (first.helper_id, first.source_fingerprint),
                    (second.helper_id, second.source_fingerprint),
                ),
                coverage_checker_bindings=(
                    ("coverage:save", first.helper_id, "test:save"),
                ),
            ),
            False,
            ("ambiguous_delegated_assertion_helper",),
        ),
        DelegatedHelperGraphCase(
            "delegated_unknown_branch_blocks",
            replace(
                base,
                scenario_id="delegated_terminal_unknown_branch",
                helpers=(replace(direct, callee_member_ids=("assert_missing",)),),
            ),
            False,
            ("delegated_assertion_terminal_missing",),
        ),
        DelegatedHelperGraphCase(
            "delegated_cycle_blocks",
            replace(
                base,
                scenario_id="delegated_terminal_cycle",
                helpers=(cyclic_first, cyclic_second),
                expected_helper_fingerprints=(
                    (cyclic_first.helper_id, cyclic_first.source_fingerprint),
                    (cyclic_second.helper_id, cyclic_second.source_fingerprint),
                ),
            ),
            False,
            ("delegated_assertion_helper_cycle",),
        ),
        DelegatedHelperGraphCase(
            "delegated_nonterminal_call_blocks",
            replace(
                base,
                scenario_id="delegated_terminal_nonterminal",
                helpers=(),
                expected_helper_fingerprints=(),
            ),
            False,
            ("unregistered_assertion_helper",),
        ),
        DelegatedHelperGraphCase(
            "delegated_checker_cannot_borrow_sibling_test_owner",
            replace(
                base,
                scenario_id="delegated_coverage_sibling_owner",
                helpers=(replace(direct, test_node_id="test:sibling"),),
            ),
            False,
            ("coverage_cross_test_member",),
        ),
    )


def run_delegated_helper_graph_review() -> tuple[
    tuple[str, bool, tuple[str, ...]], ...
]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for case in delegated_helper_graph_rollout_cases():
        ((output, state),) = delegated_helper_graph_transition(
            case.model_input,
            DelegatedHelperGraphState(),
        )
        matched = (
            output.ok is case.expected_ok
            and all(code in output.finding_codes for code in case.expected_codes)
            and delegated_helper_graph_invariants(case.model_input, state)
        )
        results.append((case.name, matched, output.finding_codes))
    return tuple(results)


@dataclass(frozen=True)
class BehaviorBlockEvidenceInput:
    """Independent expected and candidate failure ownership for one block."""

    behavior_block_id: str
    expected_protected_failure_ids: tuple[str, ...]
    declared_protected_failure_ids: tuple[str, ...]
    bad_case_protected_failure_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "expected_protected_failure_ids",
            "declared_protected_failure_ids",
            "bad_case_protected_failure_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(set(getattr(self, field_name)))),
            )


@dataclass(frozen=True)
class CoverageDesignInput:
    """One exact block/case/checker-to-test coverage contract."""

    coverage_id: str
    behavior_block_id: str
    test_node_id: str
    behavior_owner_id: str
    checker_id: str
    checker_accepted: bool = True


@dataclass(frozen=True)
class CoverageExecutionInput:
    """One claimed execution result and its independently typed receipt."""

    coverage_id: str
    execution_owner_id: str
    disposition: str
    receipt_id: str = ""
    receipt_kind: str = ""
    receipt_owner_id: str = ""
    receipt_covered_coverage_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "receipt_covered_coverage_ids",
            tuple(sorted(set(self.receipt_covered_coverage_ids))),
        )


@dataclass(frozen=True)
class EvidenceProjectionInput:
    """Input for block-local static design and leaf execution projection."""

    scenario_id: str
    blocks: tuple[BehaviorBlockEvidenceInput, ...]
    coverage_contracts: tuple[CoverageDesignInput, ...]
    supporting_provenance_test_node_ids: tuple[str, ...]
    claimed_test_node_owner_bindings: tuple[tuple[str, str], ...]
    execution_claims: tuple[CoverageExecutionInput, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))
        object.__setattr__(self, "coverage_contracts", tuple(self.coverage_contracts))
        object.__setattr__(
            self,
            "supporting_provenance_test_node_ids",
            tuple(sorted(set(self.supporting_provenance_test_node_ids))),
        )
        object.__setattr__(
            self,
            "claimed_test_node_owner_bindings",
            tuple(sorted(set(self.claimed_test_node_owner_bindings))),
        )
        object.__setattr__(self, "execution_claims", tuple(self.execution_claims))


@dataclass(frozen=True)
class EvidenceProjectionState:
    """State reached after the model has classified design and execution."""

    phase: str = "start"
    block_failure_bindings: tuple[
        tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...
    ] = ()
    exact_test_node_owner_bindings: tuple[tuple[str, str], ...] = ()
    claimed_test_node_owner_bindings: tuple[tuple[str, str], ...] = ()
    coverage_ids: tuple[str, ...] = ()
    exact_leaf_coverage_ids: tuple[str, ...] = ()
    pre_code_status: str = "not_run"
    executed_evidence_status: str = "not_run"
    finding_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceProjectionOutput:
    scenario_id: str
    ok: bool
    pre_code_status: str
    executed_evidence_status: str
    finding_codes: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceProjectionRolloutCase:
    name: str
    model_input: EvidenceProjectionInput
    expected_ok: bool
    expected_pre_code_status: str
    expected_executed_evidence_status: str
    expected_codes: tuple[str, ...] = ()


_DESIGN_FINDING_CODES = frozenset(
    {
        "behavior_block_duplicate",
        "block_protected_failure_boundary_mismatch",
        "coverage_behavior_block_missing",
        "coverage_contract_duplicate",
        "coverage_owner_exact_contract_omitted",
        "coverage_owner_without_exact_contract",
        "planned_checker_design_missing",
        "planned_checker_design_unaccepted",
        "protected_failure_case_not_block_local",
        "sibling_protected_failure_list_copied",
        "supporting_provenance_granted_coverage_owner",
    }
)
_AGGREGATE_RECEIPT_KINDS = frozenset(
    {"validation_parent", "model_native_check", "full_model_native_check"}
)


def evidence_projection_transition(
    model_input: EvidenceProjectionInput,
    state: EvidenceProjectionState,
) -> tuple[tuple[EvidenceProjectionOutput, EvidenceProjectionState], ...]:
    """Input x State -> Set(Output x State) for exact design/evidence ownership."""

    if state.phase != "start":
        output = EvidenceProjectionOutput(
            model_input.scenario_id,
            False,
            "blocked",
            "blocked",
            ("evidence_projection_replayed_after_terminal",),
        )
        return ((output, replace(state, finding_codes=output.finding_codes)),)

    design_findings: set[str] = set()
    execution_findings: set[str] = set()
    block_ids = tuple(row.behavior_block_id for row in model_input.blocks)
    if len(block_ids) != len(set(block_ids)):
        design_findings.add("behavior_block_duplicate")
    all_expected_failures = {
        failure_id
        for block in model_input.blocks
        for failure_id in block.expected_protected_failure_ids
    }
    block_failure_bindings = tuple(
        (
            block.behavior_block_id,
            block.expected_protected_failure_ids,
            block.declared_protected_failure_ids,
            block.bad_case_protected_failure_ids,
        )
        for block in model_input.blocks
    )
    for block in model_input.blocks:
        expected = set(block.expected_protected_failure_ids)
        declared = set(block.declared_protected_failure_ids)
        bad_cases = set(block.bad_case_protected_failure_ids)
        foreign_sibling_failures = (declared | bad_cases) & (
            all_expected_failures - expected
        )
        if foreign_sibling_failures:
            design_findings.add("sibling_protected_failure_list_copied")
        if declared != expected:
            design_findings.add("block_protected_failure_boundary_mismatch")
        if bad_cases != expected:
            design_findings.add("protected_failure_case_not_block_local")

    coverage_ids = tuple(row.coverage_id for row in model_input.coverage_contracts)
    if len(coverage_ids) != len(set(coverage_ids)):
        design_findings.add("coverage_contract_duplicate")
    block_id_set = set(block_ids)
    exact_owner_bindings: set[tuple[str, str]] = set()
    for row in model_input.coverage_contracts:
        if row.behavior_block_id not in block_id_set:
            design_findings.add("coverage_behavior_block_missing")
        if not row.checker_id:
            design_findings.add("planned_checker_design_missing")
        elif not row.checker_accepted:
            design_findings.add("planned_checker_design_unaccepted")
        exact_owner_bindings.add((row.test_node_id, row.behavior_owner_id))

    claimed_owner_bindings = set(model_input.claimed_test_node_owner_bindings)
    supporting_nodes = set(model_input.supporting_provenance_test_node_ids)
    for test_node_id, _owner_id in claimed_owner_bindings - exact_owner_bindings:
        if test_node_id in supporting_nodes:
            design_findings.add("supporting_provenance_granted_coverage_owner")
        else:
            design_findings.add("coverage_owner_without_exact_contract")
    if exact_owner_bindings - claimed_owner_bindings:
        design_findings.add("coverage_owner_exact_contract_omitted")

    execution_by_coverage: dict[str, list[CoverageExecutionInput]] = {}
    for claim in model_input.execution_claims:
        execution_by_coverage.setdefault(claim.coverage_id, []).append(claim)
        if claim.coverage_id not in set(coverage_ids):
            execution_findings.add("coverage_execution_unknown_coverage")
    if any(len(rows) != 1 for rows in execution_by_coverage.values()):
        execution_findings.add("coverage_execution_duplicate")

    receipt_owners: dict[str, set[str]] = {}
    exact_leaf_coverage_ids: set[str] = set()
    for coverage_id in coverage_ids:
        claims = execution_by_coverage.get(coverage_id, ())
        if len(claims) != 1:
            continue
        claim = claims[0]
        if claim.disposition == "not_run":
            if claim.receipt_id or claim.receipt_kind or claim.receipt_owner_id:
                execution_findings.add("not_run_execution_carries_receipt")
            continue
        if claim.disposition != "pass":
            execution_findings.add("coverage_execution_not_terminal_pass")
            continue
        if not claim.receipt_id:
            execution_findings.add("owner_wide_result_promoted_to_leaf")
            continue
        receipt_owners.setdefault(claim.receipt_id, set()).add(
            claim.execution_owner_id
        )
        if claim.receipt_kind == "owner_wide_result":
            execution_findings.add("owner_wide_result_promoted_to_leaf")
            continue
        if claim.receipt_kind in _AGGREGATE_RECEIPT_KINDS:
            execution_findings.add("aggregate_receipt_used_as_leaf")
            continue
        if claim.receipt_kind != "validation_owner":
            execution_findings.add("leaf_receipt_kind_mismatch")
            continue
        if claim.receipt_owner_id != claim.execution_owner_id:
            execution_findings.add("leaf_receipt_owner_mismatch")
            continue
        if coverage_id not in set(claim.receipt_covered_coverage_ids):
            execution_findings.add("leaf_receipt_member_missing")
            continue
        exact_leaf_coverage_ids.add(coverage_id)
    if any(len(owner_ids) > 1 for owner_ids in receipt_owners.values()):
        execution_findings.add("leaf_receipt_reused_across_owners")

    pre_code_status = "blocked" if design_findings else "ready"
    if execution_findings:
        executed_evidence_status = "blocked"
    elif set(coverage_ids) and exact_leaf_coverage_ids == set(coverage_ids):
        executed_evidence_status = "passed"
    else:
        executed_evidence_status = "not_run"
    finding_codes = tuple(sorted(design_findings | execution_findings))
    next_state = EvidenceProjectionState(
        phase="reviewed",
        block_failure_bindings=block_failure_bindings,
        exact_test_node_owner_bindings=tuple(sorted(exact_owner_bindings)),
        claimed_test_node_owner_bindings=tuple(sorted(claimed_owner_bindings)),
        coverage_ids=tuple(sorted(set(coverage_ids))),
        exact_leaf_coverage_ids=tuple(sorted(exact_leaf_coverage_ids)),
        pre_code_status=pre_code_status,
        executed_evidence_status=executed_evidence_status,
        finding_codes=finding_codes,
    )
    output = EvidenceProjectionOutput(
        scenario_id=model_input.scenario_id,
        ok=not finding_codes,
        pre_code_status=pre_code_status,
        executed_evidence_status=executed_evidence_status,
        finding_codes=finding_codes,
    )
    return ((output, next_state),)


def evidence_projection_invariants(
    model_input: EvidenceProjectionInput,
    state: EvidenceProjectionState,
) -> bool:
    """The reviewer must never turn aggregate/supporting facts into leaf proof."""

    codes = set(state.finding_codes)
    for _block_id, expected, declared, bad_cases in state.block_failure_bindings:
        if (declared != expected or bad_cases != expected) and not codes.intersection(
            {
                "block_protected_failure_boundary_mismatch",
                "protected_failure_case_not_block_local",
                "sibling_protected_failure_list_copied",
            }
        ):
            return False
    if (
        state.exact_test_node_owner_bindings
        != state.claimed_test_node_owner_bindings
        and not codes.intersection(
            {
                "coverage_owner_exact_contract_omitted",
                "coverage_owner_without_exact_contract",
                "supporting_provenance_granted_coverage_owner",
            }
        )
    ):
        return False
    if state.executed_evidence_status == "passed" and set(
        state.exact_leaf_coverage_ids
    ) != set(state.coverage_ids):
        return False
    aggregate_or_owner_wide_claim = any(
        claim.disposition == "pass"
        and (
            claim.receipt_kind in _AGGREGATE_RECEIPT_KINDS
            or claim.receipt_kind == "owner_wide_result"
            or not claim.receipt_id
        )
        for claim in model_input.execution_claims
    )
    if aggregate_or_owner_wide_claim and state.executed_evidence_status == "passed":
        return False
    if (
        not model_input.execution_claims
        and state.pre_code_status == "ready"
        and state.executed_evidence_status != "not_run"
    ):
        return False
    if codes.intersection(_DESIGN_FINDING_CODES) and state.pre_code_status == "ready":
        return False
    return True


def _base_evidence_projection_input() -> EvidenceProjectionInput:
    blocks = (
        BehaviorBlockEvidenceInput(
            "behavior:block-a",
            ("failure:block-a:rejected",),
            ("failure:block-a:rejected",),
            ("failure:block-a:rejected",),
        ),
        BehaviorBlockEvidenceInput(
            "behavior:block-b",
            ("failure:block-b:timeout",),
            ("failure:block-b:timeout",),
            ("failure:block-b:timeout",),
        ),
    )
    coverage_contracts = (
        CoverageDesignInput(
            "coverage:block-a:bad-error",
            "behavior:block-a",
            "test:block-a",
            "owner:block-a",
            "checker:block-a:bad-error",
        ),
        CoverageDesignInput(
            "coverage:block-b:bad-timeout",
            "behavior:block-b",
            "test:block-b",
            "owner:block-b",
            "checker:block-b:bad-timeout",
        ),
    )
    return EvidenceProjectionInput(
        scenario_id="planned_checker_design_without_execution",
        blocks=blocks,
        coverage_contracts=coverage_contracts,
        supporting_provenance_test_node_ids=("test:shared-input-glob",),
        claimed_test_node_owner_bindings=(
            ("test:block-a", "owner:block-a"),
            ("test:block-b", "owner:block-b"),
        ),
    )


def evidence_projection_rollout_cases() -> tuple[
    EvidenceProjectionRolloutCase, ...
]:
    base = _base_evidence_projection_input()
    exact_leaf_execution = tuple(
        CoverageExecutionInput(
            coverage_id=row.coverage_id,
            execution_owner_id=f"execution:{row.behavior_block_id}",
            disposition="pass",
            receipt_id=f"receipt:leaf:{row.behavior_block_id}",
            receipt_kind="validation_owner",
            receipt_owner_id=f"execution:{row.behavior_block_id}",
            receipt_covered_coverage_ids=(row.coverage_id,),
        )
        for row in base.coverage_contracts
    )
    copied_failures = tuple(
        replace(
            block,
            declared_protected_failure_ids=(
                "failure:block-a:rejected",
                "failure:block-b:timeout",
            ),
            bad_case_protected_failure_ids=(
                "failure:block-a:rejected",
                "failure:block-b:timeout",
            ),
        )
        for block in base.blocks
    )
    owner_wide_execution = tuple(
        CoverageExecutionInput(
            coverage_id=row.coverage_id,
            execution_owner_id="execution:whole-owner",
            disposition="pass",
            receipt_id="result:owner-wide-green",
            receipt_kind="owner_wide_result",
            receipt_owner_id="execution:whole-owner",
        )
        for row in base.coverage_contracts
    )
    exact_merged_owner_execution = tuple(
        CoverageExecutionInput(
            coverage_id=row.coverage_id,
            execution_owner_id="execution:exact-merged-owner",
            disposition="pass",
            receipt_id="receipt:leaf:exact-merged-owner",
            receipt_kind="validation_owner",
            receipt_owner_id="execution:exact-merged-owner",
            receipt_covered_coverage_ids=tuple(
                item.coverage_id for item in base.coverage_contracts
            ),
        )
        for row in base.coverage_contracts
    )

    def aggregate_execution(receipt_kind: str) -> tuple[CoverageExecutionInput, ...]:
        return tuple(
            CoverageExecutionInput(
                coverage_id=row.coverage_id,
                execution_owner_id=f"execution:{row.behavior_block_id}",
                disposition="pass",
                receipt_id=f"receipt:{receipt_kind}:{row.behavior_block_id}",
                receipt_kind=receipt_kind,
                receipt_owner_id=f"execution:{row.behavior_block_id}",
                receipt_covered_coverage_ids=(row.coverage_id,),
            )
            for row in base.coverage_contracts
        )

    return (
        EvidenceProjectionRolloutCase(
            "planned_checker_design_ready_but_leaf_execution_not_run",
            base,
            True,
            "ready",
            "not_run",
        ),
        EvidenceProjectionRolloutCase(
            "exact_current_leaf_receipts_can_close_each_behavior_block",
            replace(
                base,
                scenario_id="exact_leaf_receipts",
                execution_claims=exact_leaf_execution,
            ),
            True,
            "ready",
            "passed",
        ),
        EvidenceProjectionRolloutCase(
            "one_exact_merged_owner_receipt_can_cover_declared_members",
            replace(
                base,
                scenario_id="exact_merged_owner_receipt",
                execution_claims=exact_merged_owner_execution,
            ),
            True,
            "ready",
            "passed",
        ),
        EvidenceProjectionRolloutCase(
            "parent_failure_list_cannot_be_copied_to_sibling_blocks",
            replace(
                base,
                scenario_id="copied_parent_failure_list",
                blocks=copied_failures,
            ),
            False,
            "blocked",
            "not_run",
            (
                "sibling_protected_failure_list_copied",
                "block_protected_failure_boundary_mismatch",
                "protected_failure_case_not_block_local",
            ),
        ),
        EvidenceProjectionRolloutCase(
            "owner_wide_result_cannot_be_copied_as_leaf_execution",
            replace(
                base,
                scenario_id="owner_wide_result_copied",
                execution_claims=owner_wide_execution,
            ),
            False,
            "ready",
            "blocked",
            ("owner_wide_result_promoted_to_leaf",),
        ),
        EvidenceProjectionRolloutCase(
            "validation_parent_receipt_cannot_replace_behavior_leaf",
            replace(
                base,
                scenario_id="validation_parent_as_leaf",
                execution_claims=aggregate_execution("validation_parent"),
            ),
            False,
            "ready",
            "blocked",
            ("aggregate_receipt_used_as_leaf",),
        ),
        EvidenceProjectionRolloutCase(
            "model_native_check_cannot_replace_behavior_leaf",
            replace(
                base,
                scenario_id="model_native_check_as_leaf",
                execution_claims=aggregate_execution("model_native_check"),
            ),
            False,
            "ready",
            "blocked",
            ("aggregate_receipt_used_as_leaf",),
        ),
        EvidenceProjectionRolloutCase(
            "supporting_input_glob_cannot_grant_coverage_ownership",
            replace(
                base,
                scenario_id="supporting_provenance_as_owner",
                claimed_test_node_owner_bindings=(
                    *base.claimed_test_node_owner_bindings,
                    ("test:shared-input-glob", "owner:block-a"),
                    ("test:shared-input-glob", "owner:block-b"),
                ),
            ),
            False,
            "blocked",
            "not_run",
            ("supporting_provenance_granted_coverage_owner",),
        ),
    )


def run_evidence_projection_review() -> tuple[
    tuple[str, bool, tuple[str, ...]], ...
]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for case in evidence_projection_rollout_cases():
        ((output, state),) = evidence_projection_transition(
            case.model_input,
            EvidenceProjectionState(),
        )
        codes = output.finding_codes
        matched = (
            output.ok is case.expected_ok
            and output.pre_code_status == case.expected_pre_code_status
            and output.executed_evidence_status
            == case.expected_executed_evidence_status
            and all(code in codes for code in case.expected_codes)
            and evidence_projection_invariants(case.model_input, state)
        )
        results.append((case.name, matched, codes))
    return tuple(results)


def _obligation() -> ModelObligation:
    return ModelObligation(
        "reject_duplicate_order",
        obligation_type="hazard",
        description="duplicate order is rejected without a second side effect",
        external_inputs=("order_id",),
        external_outputs=("Rejected",),
        state_reads=("order_status",),
        side_effects=(),
        error_paths=("duplicate_order",),
        exact_external_contract=True,
        required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
        business_intent_id="checkout.submit-order",
        behavior_commitment_id="commitment:checkout.submit-order",
        primary_path_id="path:checkout.reject-duplicate",
    )


def _contract(**overrides: object) -> CodeContract:
    values = {
        "code_contract_id": "checkout_reject_duplicate",
        "path": "checkout/service.py",
        "symbol": "reject_duplicate_order",
        "implements_obligations": ("reject_duplicate_order",),
        "external_inputs": ("order_id",),
        "external_outputs": ("Rejected",),
        "state_reads": ("order_status",),
        "side_effects": (),
        "error_paths": ("duplicate_order",),
        "business_intent_id": "checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.reject-duplicate",
    }
    values.update(overrides)
    return CodeContract(**values)


def _evidence(evidence_id: str, kind: str, **overrides: object) -> TestEvidence:
    values = {
        "test_name": evidence_id,
        "path": "tests/test_checkout.py",
        "result_status": "passed",
        "test_kind": kind,
        "covered_obligations": ("reject_duplicate_order",),
        "covered_code_contracts": ("checkout_reject_duplicate",),
        "assertion_scope": TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
        "business_intent_id": "checkout.submit-order",
        "behavior_commitment_id": "commitment:checkout.submit-order",
        "primary_path_id": "path:checkout.reject-duplicate",
    }
    values.update(overrides)
    return TestEvidence(evidence_id, **values)


def aligned_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def pre_code_design_plan() -> ModelTestAlignmentPlan:
    """Complete obligation/oracle design with deliberately not-run execution."""

    return ModelTestAlignmentPlan(
        model_id="checkout-pre-code",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH, result_status="not_run"),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH, result_status="not_run"),
        ),
    )


SOURCE = {
    "checkout/service.py": """
def reject_duplicate_order(order_id):
    if order_id:
        return "Rejected"
    return "Rejected"
""",
    "tests/test_checkout.py": """
def test_duplicate_happy():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_duplicate_failure():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_duplicate_counterexample_replay():
    assert reject_duplicate_order("counterexample:duplicate-order") == "Rejected"
""",
}


def source_audit_report(plan: ModelTestAlignmentPlan):
    code_audit = audit_python_code_contracts(plan.code_contracts, SOURCE)
    test_audit = audit_python_test_assertions(plan.test_evidence, plan.code_contracts, SOURCE)
    return review_python_contract_source_audit(plan.code_contracts, plan.test_evidence, code_audit, test_audit)


def source_audited_plan() -> ModelTestAlignmentPlan:
    base = aligned_plan()
    return replace(base, require_source_audit=True, source_audit_reports=(source_audit_report(base),))


def missing_source_audit_plan() -> ModelTestAlignmentPlan:
    return replace(aligned_plan(), require_source_audit=True)


def missing_code_contract_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH, covered_code_contracts=()),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH, covered_code_contracts=()),
        ),
    )


def extra_side_effect_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(side_effects=("publish_duplicate_metric",)),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def missing_output_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(external_outputs=()),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def missing_code_bound_test_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH, covered_code_contracts=()),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH, covered_code_contracts=()),
        ),
    )


def internal_path_only_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(),),
        test_evidence=(
            _evidence(
                "test_duplicate_happy",
                TEST_KIND_HAPPY_PATH,
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
            _evidence(
                "test_duplicate_failure",
                TEST_KIND_FAILURE_PATH,
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
        ),
    )


def binding_mismatch_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(), ModelObligation("accept_valid_order")),
        code_contracts=(_contract(code_contract_id="checkout_accept_order", implements_obligations=("accept_valid_order",)),),
        test_evidence=(
            _evidence(
                "test_duplicate_happy",
                TEST_KIND_HAPPY_PATH,
                covered_code_contracts=("checkout_accept_order",),
            ),
            _evidence(
                "test_duplicate_failure",
                TEST_KIND_FAILURE_PATH,
                covered_code_contracts=("checkout_accept_order",),
            ),
        ),
    )


def stable_path_mismatch_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(_contract(primary_path_id="path:checkout.alternate-success"),),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def facade_delegation_plan(*, current: bool, delegation_only: bool) -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(_obligation(),),
        code_contracts=(
            _contract(),
            _contract(
                code_contract_id="checkout_public_facade",
                role=CODE_CONTRACT_ROLE_FACADE,
                delegates_to_code_contract_id="checkout_reject_duplicate",
                delegation_evidence_id="runtime:checkout-public-facade",
                delegation_evidence_current=current,
                delegation_only=delegation_only,
            ),
        ),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
    )


def canonical_relation_materialization_plan(*, materialized: bool) -> ModelTestAlignmentPlan:
    relation_id = "canonical-relation:checkout-duplicate-handlers"
    test_obligation_id = "relation-test:checkout-duplicate-handlers"
    code_obligation_id = "relation-code:checkout-duplicate-handlers"
    obligation = replace(
        _obligation(),
        relation_ids=(relation_id,) if materialized else (),
        relation_test_obligation_ids=(test_obligation_id,) if materialized else (),
        relation_impacted_model_ids=("checkout",) if materialized else (),
    )
    contract = replace(
        _contract(),
        relation_ids=(relation_id,) if materialized else (),
        relation_code_obligation_ids=(code_obligation_id,) if materialized else (),
    )
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(obligation,),
        code_contracts=(contract,),
        test_evidence=(
            _evidence("test_duplicate_happy", TEST_KIND_HAPPY_PATH),
            _evidence("test_duplicate_failure", TEST_KIND_FAILURE_PATH),
        ),
        canonical_relation_handoff={
            "relations": ({
                "relation_id": relation_id,
                "relation_type": "duplicate_boundary",
                "source_endpoint_kind": "model",
                "source_endpoint_id": "checkout",
                "target_endpoint_kind": "code_contract",
                "target_endpoint_id": "checkout_reject_duplicate",
                "source_ids": ("semantic-mesh:checkout",),
            },),
            "relation_group_ids": ("relation-group:checkout",),
            "affected_model_ids": ("checkout",),
            "test_obligation_ids": (test_obligation_id,),
            "code_obligation_ids": (code_obligation_id,),
            "evidence_current": True,
        },
    )


def plane_aware_alignment_plan(*, mismatch: bool = False) -> ModelTestAlignmentPlan:
    plane_rows = (
        ("behavior_plane_schema", "development_process"),
        ("behavior_plane_lookup", "agent_operation"),
        ("behavior_plane_preflight", "agent_operation"),
        ("behavior_plane_relation", "agent_operation"),
        ("behavior_plane_migration", "development_process"),
        ("behavior_plane_miss_backfeed", "agent_operation"),
    )
    obligations = tuple(
        ModelObligation(
            obligation_id,
            description=f"{obligation_id} remains bound to its owning behavior plane",
            required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            required_closure_targets=(
                ClosureEvidenceTarget(
                    f"plane-upgrade:{obligation_id}",
                    closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
                ),
            ),
            behavior_plane=behavior_plane,
        )
        for obligation_id, behavior_plane in plane_rows
    )
    contracts = tuple(
        CodeContract(
            f"flowguard.{obligation_id}",
            path="flowguard/behavior_commitment.py",
            symbol=obligation_id,
            implements_obligations=(obligation_id,),
            behavior_plane=(
                "product_runtime"
                if mismatch and obligation_id == "behavior_plane_lookup"
                else behavior_plane
            ),
        )
        for obligation_id, behavior_plane in plane_rows
    )
    evidence = tuple(
        TestEvidence(
            f"test_{obligation_id}",
            result_status="passed",
            test_kind=TEST_KIND_HAPPY_PATH,
            covered_obligations=(obligation_id,),
            covered_code_contracts=(f"flowguard.{obligation_id}",),
            assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
            evidence_target_id=f"plane-upgrade:{obligation_id}",
            behavior_plane=behavior_plane,
        )
        for obligation_id, behavior_plane in plane_rows
    )
    return ModelTestAlignmentPlan(
        model_id="behavior-plane-upgrade",
        obligations=obligations,
        code_contracts=contracts,
        test_evidence=evidence,
        require_behavior_plane_binding=True,
    )


def counterexample_closure_obligation() -> ModelObligation:
    return ModelObligation(
        "reject_duplicate_counterexample",
        obligation_type="model_miss",
        description="duplicate-order counterexample is replayed through owner code",
        external_inputs=("order_id",),
        external_outputs=("Rejected",),
        required_test_kinds=(TEST_KIND_HAPPY_PATH,),
        required_closure_targets=(
            ClosureEvidenceTarget(
                "counterexample:duplicate-order",
                closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION,
            ),
        ),
    )


def counterexample_closure_plan(include_target_evidence: bool) -> ModelTestAlignmentPlan:
    test_items = (
        _evidence(
            "test_duplicate_counterexample_replay",
            TEST_KIND_HAPPY_PATH,
            covered_obligations=("reject_duplicate_counterexample",),
            covered_code_contracts=("checkout_reject_counterexample",),
            closure_evidence_role=TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION if include_target_evidence else "",
            evidence_target_id="counterexample:duplicate-order" if include_target_evidence else "",
        ),
    )
    return ModelTestAlignmentPlan(
        model_id="checkout",
        obligations=(counterexample_closure_obligation(),),
        code_contracts=(
            _contract(
                code_contract_id="checkout_reject_counterexample",
                implements_obligations=("reject_duplicate_counterexample",),
            ),
        ),
        test_evidence=test_items,
    )


UNDERSTANDING_ALIGNMENT_ROWS = (
    (
        "task_coverage_demand_no_caller_reduction",
        "commitment:task-coverage-demand",
        "flowguard/task_coverage_demand.py",
        "compile_task_coverage_demand",
        "tests/test_task_coverage_demand.py",
        "development_process",
    ),
    (
        "canonical_owner_resolution_exact_identity",
        "commitment:task-coverage-demand",
        "flowguard/task_coverage_demand.py",
        "project_owner_resolution_to_demand",
        "tests/test_task_coverage_demand.py",
        "development_process",
    ),
    (
        "proof_artifact_requires_verifiable_material",
        "commitment:model-maturation-receipt",
        "flowguard/proof_artifact.py",
        "proof_artifact_gap_codes",
        "tests/test_proof_artifact.py",
        "development_process",
    ),
    (
        "model_maturation_receipt_independent_verification",
        "commitment:model-maturation-receipt",
        "flowguard/model_maturation_receipt.py",
        "verify_model_maturation_receipt",
        "tests/test_model_maturation_receipt.py",
        "development_process",
    ),
    (
        "implementation_admission_preserves_maturation",
        "commitment:implementation-admission",
        "flowguard/development_process_flow.py",
        "review_implementation_admission",
        "tests/test_development_process_flow.py",
        "development_process",
    ),
    (
        "risk_ledger_owns_understanding_confidence",
        "commitment:understanding-confidence",
        "flowguard/risk_evidence_ledger.py",
        "review_risk_evidence_ledger",
        "tests/test_risk_evidence_ledger.py",
        "development_process",
    ),
    (
        "closure_preserves_risk_and_receipt_identity",
        "commitment:understanding-closure-integrity",
        "flowguard/closure_contract.py",
        "review_flowguard_closure_contract",
        "tests/test_closure_contract.py",
        "development_process",
    ),
    (
        "read_only_three_axis_understanding_status",
        "commitment:understanding-readiness-status",
        "flowguard/understanding_readiness.py",
        "compose_understanding_status",
        "tests/test_understanding_readiness.py",
        "product_runtime",
    ),
    (
        "whole_system_semantic_mesh_is_not_inventory_only",
        "commitment:authoritative-model-system",
        ".flowguard/authoritative_model_system/semantic_self_model.py",
        "review_semantic_self_model",
        ".flowguard/authoritative_model_system/run_checks.py",
        "development_process",
    ),
)


def understanding_chain_alignment_plan(
    *, omit_failure_evidence_for: str = ""
) -> ModelTestAlignmentPlan:
    obligations = tuple(
        ModelObligation(
            obligation_id,
            obligation_type="invariant",
            description=f"{obligation_id} remains bound to its exact public owner and evidence",
            required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
            required_closure_targets=(
                ClosureEvidenceTarget(
                    f"understanding:{obligation_id}:known-bad",
                    closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
                ),
            ),
            behavior_plane=behavior_plane,
            business_intent_id=f"intent:{obligation_id}",
            behavior_commitment_id=commitment_id,
            primary_path_id=f"path:understanding:{obligation_id}",
        )
        for obligation_id, commitment_id, _path, _symbol, _test_path, behavior_plane in UNDERSTANDING_ALIGNMENT_ROWS
    )
    contracts = tuple(
        CodeContract(
            f"flowguard.{obligation_id}",
            path=path,
            symbol=symbol,
            implements_obligations=(obligation_id,),
            behavior_plane=behavior_plane,
            business_intent_id=f"intent:{obligation_id}",
            behavior_commitment_id=commitment_id,
            primary_path_id=f"path:understanding:{obligation_id}",
        )
        for obligation_id, commitment_id, path, symbol, _test_path, behavior_plane in UNDERSTANDING_ALIGNMENT_ROWS
    )
    evidence: list[TestEvidence] = []
    for obligation_id, commitment_id, _path, _symbol, test_path, behavior_plane in UNDERSTANDING_ALIGNMENT_ROWS:
        contract_id = f"flowguard.{obligation_id}"
        common = {
            "path": test_path,
            "result_status": "passed",
            "covered_obligations": (obligation_id,),
            "covered_code_contracts": (contract_id,),
            "assertion_scope": TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
            "behavior_plane": behavior_plane,
            "business_intent_id": f"intent:{obligation_id}",
            "behavior_commitment_id": commitment_id,
            "primary_path_id": f"path:understanding:{obligation_id}",
        }
        evidence.append(
            TestEvidence(
                f"test_{obligation_id}_happy",
                test_name=f"test_{obligation_id}_happy",
                test_kind=TEST_KIND_HAPPY_PATH,
                **common,
            )
        )
        if obligation_id != omit_failure_evidence_for:
            evidence.append(
                TestEvidence(
                    f"test_{obligation_id}_known_bad",
                    test_name=f"test_{obligation_id}_known_bad",
                    test_kind=TEST_KIND_FAILURE_PATH,
                    closure_evidence_role=TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY,
                    evidence_target_id=f"understanding:{obligation_id}:known-bad",
                    **common,
                )
            )
    return ModelTestAlignmentPlan(
        model_id="flowguard-understanding-readiness",
        obligations=obligations,
        code_contracts=contracts,
        test_evidence=tuple(evidence),
        require_behavior_plane_binding=True,
    )


def rollout_cases() -> tuple[RolloutCase, ...]:
    return (
        RolloutCase("aligned_model_code_test_contracts", aligned_plan(), True),
        RolloutCase(
            "pre_code_design_is_ready_but_execution_is_not_run",
            pre_code_design_plan(),
            False,
            ("test_evidence_not_passing",),
            "ready",
            "not_run",
        ),
        RolloutCase("source_audited_real_code_claim", source_audited_plan(), True),
        RolloutCase("missing_source_audit_blocks", missing_source_audit_plan(), False, ("missing_source_audit_report",)),
        RolloutCase("counterexample_target_closure_passes", counterexample_closure_plan(True), True),
        RolloutCase(
            "counterexample_target_without_replay_blocks",
            counterexample_closure_plan(False),
            False,
            ("missing_counterexample_regression_test",),
        ),
        RolloutCase("missing_code_contract_blocks", missing_code_contract_plan(), False, ("missing_code_contract",)),
        RolloutCase("extra_code_side_effect_blocks", extra_side_effect_plan(), False, ("code_contract_extra_behavior",)),
        RolloutCase("missing_code_output_blocks", missing_output_plan(), False, ("code_contract_missing_behavior",)),
        RolloutCase(
            "test_without_code_contract_binding_blocks",
            missing_code_bound_test_plan(),
            False,
            ("test_not_bound_to_code_contract", "missing_code_contract_test_evidence"),
        ),
        RolloutCase(
            "internal_path_only_test_blocks",
            internal_path_only_plan(),
            False,
            ("test_checks_internal_path_only", "missing_code_contract_test_evidence"),
        ),
        RolloutCase("model_code_test_binding_mismatch_blocks", binding_mismatch_plan(), False, ("model_code_test_binding_mismatch",)),
        RolloutCase("stable_primary_path_mismatch_blocks", stable_path_mismatch_plan(), False, ("primary_path_id_mismatch",)),
        RolloutCase("current_delegating_facade_passes", facade_delegation_plan(current=True, delegation_only=True), True),
        RolloutCase("stale_facade_delegation_blocks", facade_delegation_plan(current=False, delegation_only=True), False, ("facade_delegation_evidence_stale",)),
        RolloutCase("facade_parallel_success_blocks", facade_delegation_plan(current=True, delegation_only=False), False, ("facade_independent_business_authority",)),
        RolloutCase("canonical_relation_handoff_materializes", canonical_relation_materialization_plan(materialized=True), True),
        RolloutCase("opaque_canonical_relation_handoff_blocks", canonical_relation_materialization_plan(materialized=False), False, ("unmaterialized_canonical_relation_id",)),
        RolloutCase("plane_aware_model_code_test_bindings_pass", plane_aware_alignment_plan(), True),
        RolloutCase(
            "cross_plane_code_binding_blocks",
            plane_aware_alignment_plan(mismatch=True),
            False,
            ("behavior_plane_mismatch",),
        ),
        RolloutCase(
            "understanding_chain_obligations_are_explicitly_owned",
            understanding_chain_alignment_plan(),
            True,
        ),
        RolloutCase(
            "understanding_chain_missing_failure_owner_blocks",
            understanding_chain_alignment_plan(
                omit_failure_evidence_for="closure_preserves_risk_and_receipt_identity"
            ),
            False,
            ("missing_required_test_kind", "missing_known_bad_replay_test"),
        ),
    )


def run_rollout_review() -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for case in rollout_cases():
        report = review_model_test_alignment(case.plan)
        codes = tuple(finding.code for finding in report.findings)
        ok_matches = report.ok is case.expected_ok
        codes_match = all(code in codes for code in case.expected_codes)
        pre_code_matches = (
            not case.expected_pre_code_status
            or getattr(report, "pre_code_status", "") == case.expected_pre_code_status
        )
        execution_matches = (
            not case.expected_executed_evidence_status
            or getattr(report, "executed_evidence_status", "")
            == case.expected_executed_evidence_status
        )
        results.append(
            (
                case.name,
                ok_matches and codes_match and pre_code_matches and execution_matches,
                codes,
            )
        )
    results.extend(run_evidence_projection_review())
    results.extend(run_delegated_helper_graph_review())
    return tuple(results)


__all__ = [
    "NATIVE_PYTEST_SELECTORS",
    "NATIVE_TEST_OBLIGATION_BINDINGS",
    "delegated_helper_graph_invariants",
    "delegated_helper_graph_rollout_cases",
    "delegated_helper_graph_transition",
    "evidence_projection_invariants",
    "evidence_projection_rollout_cases",
    "evidence_projection_transition",
    "native_test_obligation_bindings_are_executed",
    "rollout_cases",
    "run_delegated_helper_graph_review",
    "run_evidence_projection_review",
    "run_rollout_review",
]


from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    """Project the existing model-test-alignment owner for SkillGuard V2."""

    return build_skill_contract_model_export(
        skill_id="flowguard-model-test-alignment",
        route_id="model_test_alignment",
        owner_id="model_test_alignment",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Bind model obligations to one owner contract and current tests without plane or path drift.",
        claim_boundary="Projection only; row-level alignment, source audit, replay, canonical relation provenance, and native runner evidence remain authoritative.",
    )


__all__ = [*__all__, "FLOWGUARD_MODEL_MARKER", "export_contract_model"]
