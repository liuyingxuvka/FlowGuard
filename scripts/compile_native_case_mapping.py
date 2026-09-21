"""Compile the checked-in native-case mapping from the frozen audit annexes.

The compiler is intentionally conservative.  It reads the owner catalog and
the four mapping annexes as *source declarations*, resolves exact selectors,
and emits one content-addressed registry consumed by ``native_case_runner``.
It never executes a runner, infers a selector from a similar name, or turns a
planned boundary into a passing result.  A changed/missing source declaration
is a compilation error so the next owner has a precise repair target.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = ROOT.parent / "Codex" / "2026-09-01" / "flowguard-b" / "FlowGuard-audit-20260904"
CATALOG_NAME = "owner-case-catalog.json"
SCENARIO_NAME = "MAPPING_SCENARIO.md"
FORMAL_NAME = "MAPPING_FORMAL.md"
CUSTOM_NAME = "MAPPING_CUSTOM.md"
BENCHMARK_NAME = "MAPPING_BENCHMARK.md"
PRODUCER_OVERRIDES_NAME = "native-case-producer-overrides.json"

SCENARIO_OWNERS = frozenset(
    {
        "authoritative_model_system",
        "adversarial_scenario_synthesis",
        "architecture_reduction",
        "hierarchical_model_mesh",
        "mesh_target_split_derivation",
        "skill_kernel_modularization",
        "structure_refactor_mesh",
        "test_evidence_mesh",
        "validation_evidence_gates",
    }
)
FORMAL_OWNERS = frozenset(
    {
        "compositional_verification_kernel",
        "model_maturation_loop",
        "task_coverage_demand",
        "ai_route_handoffs",
        "default_replacement_field_lifecycle",
        "development_process_flow",
        "existing_model_preflight",
        "field_prompt_reduction",
        "flowguard_closure_contract",
        "guard_closure_contract",
        "guidance_compression",
        "implementation_blueprint",
        "maintenance_obligation_memory",
        "minimum_valuable_model_entry",
        "model_impact_freshness_gate",
        "model_mesh_closure_model",
        "model_topology_hazard_review",
        "model_visibility",
        "project_adoption_version_gate",
        "runtime_path_evidence",
        "self_maintenance_mesh",
        "state_closure_gate",
        "task_local_prediction_replay",
    }
)
CUSTOM_OWNERS = frozenset(
    {
        "code_boundary_conformance",
        "contract_source_audit",
        "runtime_gateway_adoption",
        "model_test_code_alignment",
        "ai_entry_surface_reduction",
        "harden_ui_real_surface_validation",
        "ui_human_operability_gate",
        "ui_flow_structure_skill",
        "user_facing_model_diagrams",
        "codex_skill_satellites",
        "work_context",
        "development_process_strategy",
        "primary_path_authority",
        "behavior_commitment_ledger",
        "model_miss_review",
        "plan_detailing_compiler",
        "template_public_release",
        "harden_ui_content_visibility_validation",
    }
)
BENCHMARK_OWNER = "bounded_system_composition_benchmark"

# Native helper rows that are emitted by a current producer but are not
# independent blueprint obligations.  They remain in ``native-source.json``
# for diagnosis and boundary accounting; naming them here is the only way a
# runner may classify one as non-authoritative.  Any newly emitted row still
# blocks until it is either mapped as a leaf/aggregate or added explicitly to
# this finite list after reviewing the producer contract.
EXPLICIT_DIAGNOSTIC_SELECTORS: dict[str, tuple[str, ...]] = {
    "compositional_verification_kernel": (
        "bad-schema",
        "bad-temporal",
        "bad-refinement",
        "bad-provider",
        "bad-slice",
        "bad-system",
        "bad-truncation",
        "safety-fail-with-truncation",
        "temporal-observation-with-truncation",
        "system-not-run",
    ),
    # These are human-facing sub-reviews emitted by the minimum-entry runner;
    # the exact positive workflow is exposed separately under the stable
    # ``minimum_valuable_model_entry`` selector.
    "minimum_valuable_model_entry": (
        "ordinary minimum-model entry",
        "narrow minimum-entry projection",
        "missing_purpose",
        "missing_protected_error",
        "missing_state",
        "missing_effect",
        "missing_completion",
        "missing_known_bad",
        "missing_model_binding",
        "missing_code_binding",
        "missing_test_binding",
    ),
    "state_closure_gate": (
        "safe_unknown_rejects_before_side_effect",
        "unsafe_unknown_accepts_as_normal",
        "confidence",
    ),
    "model_topology_hazard_review": (
        "unanchored_hazard_is_observation",
        "anchored_side_effect_blocks_release",
        "confidence",
    ),
}

GOOD_DIMENSIONS = ("input", "state", "output", "effect", "order", "completion")
BAD_DIMENSIONS = ("input", "state", "effect", "error", "decision", "completion")
BOUNDARY_DIMENSIONS = ("input", "error", "decision", "retry", "timeout", "completion")


class CompileError(ValueError):
    """A source mapping is absent, ambiguous, or inconsistent."""


def _text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompileError(f"{label} must be non-empty text")
    return value.strip()


def _unique(values: Iterable[str], *, label: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        item = _text(value, label=label)
        if item not in result:
            result.append(item)
    if not result:
        raise CompileError(f"{label} is empty")
    return tuple(result)


def _code_tokens(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in re.findall(r"`([^`]+)`", value) if item.strip())


def _sections(lines: Sequence[str], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current = ""
    for line in lines:
        match = pattern.match(line)
        if match:
            current = match.group(1).strip()
            result[current] = []
        elif current:
            result[current].append(line)
    return result


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompileError(f"cannot read JSON source {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise CompileError(f"JSON source must be an object: {path}")
    return payload


def _catalog(path: Path) -> dict[str, Mapping[str, Any]]:
    payload = _read_json(path)
    owners = payload.get("owners")
    if not isinstance(owners, list):
        raise CompileError("owner catalog owners must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for index, owner in enumerate(owners):
        if not isinstance(owner, Mapping):
            raise CompileError(f"owner catalog owners[{index}] is not an object")
        model_id = _text(owner.get("model_id"), label=f"owners[{index}].model_id")
        if model_id in result:
            raise CompileError(f"duplicate owner in catalog: {model_id}")
        result[model_id] = owner
    if set(result) != SCENARIO_OWNERS | FORMAL_OWNERS | CUSTOM_OWNERS | {BENCHMARK_OWNER}:
        missing = sorted((SCENARIO_OWNERS | FORMAL_OWNERS | CUSTOM_OWNERS | {BENCHMARK_OWNER}) - set(result))
        extra = sorted(set(result) - (SCENARIO_OWNERS | FORMAL_OWNERS | CUSTOM_OWNERS | {BENCHMARK_OWNER}))
        raise CompileError(f"catalog owner inventory mismatch: missing={missing}; extra={extra}")
    return result


def _catalog_sources(owner: Mapping[str, Any]) -> tuple[str, tuple[str, ...], str]:
    good = _text(owner.get("known_good_case_id"), label="known_good_case_id")
    raw_bad = owner.get("failure_bindings")
    if not isinstance(raw_bad, list):
        raise CompileError(f"failure_bindings is not an array for {good}")
    bad: list[str] = []
    for item in raw_bad:
        if not isinstance(item, Mapping):
            raise CompileError(f"failure binding is not an object for {good}")
        bad.append(_text(item.get("known_bad_case_id"), label="known_bad_case_id"))
    boundary = _text(owner.get("boundary_case_id_proposed"), label="boundary_case_id_proposed")
    return good, _unique(bad, label="known_bad_case_ids") if bad else (), boundary


def _qualified(owner: str, selector: str) -> str:
    selector = _text(selector, label="native selector")
    if owner in SCENARIO_OWNERS:
        return f"native-scenario:{owner}:{selector}"
    if owner == BENCHMARK_OWNER:
        if selector.startswith("benchmark:"):
            return selector
        raise CompileError(f"benchmark selector must already be qualified: {selector}")
    return f"case:{owner}:{selector}"


def _boundary_native_id(owner: str) -> str:
    if owner in SCENARIO_OWNERS:
        return f"native-scenario:{owner}:boundary"
    if owner == BENCHMARK_OWNER:
        return "benchmark:boundary:finite-domain"
    return f"case:{owner}:boundary:finite-domain"


def _scenario_mappings(
    path: Path,
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, dict[str, dict[str, tuple[str, ...] | str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    owner_sections = _sections(lines, re.compile(r"^###\s+(.+?)\s*$"))
    mappings: dict[str, dict[str, tuple[str, ...]]] = {}
    oracle: dict[str, dict[str, dict[str, tuple[str, ...] | str]]] = {}
    for owner in SCENARIO_OWNERS:
        if owner not in owner_sections:
            raise CompileError(f"Scenario mapping section missing: {owner}")
        good, bad, _ = _catalog_sources(catalog[owner])
        allowed = {good, *bad}
        source_map: dict[str, tuple[str, ...]] = {}
        oracle_map: dict[str, dict[str, tuple[str, ...] | str]] = {}
        in_oracle = False
        for line in owner_sections[owner]:
            if line.startswith("#### 原生 selector"):
                in_oracle = True
                continue
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if len(cells) < 2:
                continue
            tokens = _code_tokens(cells[0])
            if not tokens:
                continue
            first = tokens[0]
            if not in_oracle and first in allowed:
                selectors = _code_tokens(cells[1])
                if not selectors:
                    raise CompileError(f"Scenario source has no selectors: {owner}:{first}")
                if first in source_map:
                    raise CompileError(f"duplicate Scenario source mapping: {owner}:{first}")
                source_map[first] = _unique(selectors, label=f"selectors:{owner}:{first}")
            elif in_oracle and first not in {"Selector"} and len(cells) >= 3:
                status_tokens = _code_tokens(cells[2])
                status = status_tokens[0].lower() if status_tokens else ""
                if status in {"ok", "violation"}:
                    codes = _code_tokens(cells[3]) if len(cells) > 3 else ()
                    labels = _code_tokens(cells[4]) if len(cells) > 4 else ()
                    oracle_map[first] = {"status": status, "codes": codes, "labels": labels}
        if set(source_map) != allowed:
            raise CompileError(
                f"Scenario source mapping inventory mismatch for {owner}: "
                f"missing={sorted(allowed - set(source_map))}; extra={sorted(set(source_map) - allowed)}"
            )
        for source, selectors in source_map.items():
            for selector in selectors:
                if selector not in oracle_map:
                    raise CompileError(f"Scenario selector lacks oracle row: {owner}:{selector}")
        mappings[owner] = source_map
        oracle[owner] = oracle_map
    return mappings, oracle


FORMAL_RAW_GOOD = {
    # These labels are the exact stable producer names printed by the
    # current runners.  The annex's prose names the source obligation, but
    # the native wire selector must match the callback's concrete label; a
    # source-name alias would remain unbound and block the owner.
    "compositional_verification_kernel": "correct_portable_kernel",
    "model_maturation_loop": "correct_model_maturation_loop",
    "task_coverage_demand": "correct_task_coverage_demand",
    "flowguard_closure_contract": "thin_closure_contract",
    "guard_closure_contract": "guard_closure_contract",
    "maintenance_obligation_memory": "correct_maintenance_obligation_memory",
    "minimum_valuable_model_entry": "minimum_valuable_model_entry",
    "model_topology_hazard_review": "correct_topology_hazard_review",
    "state_closure_gate": "correct_state_closure_gate",
    "task_local_prediction_replay": "correct_task_local_prediction_replay",
}


def _formal_bad_selectors(rhs: str) -> tuple[str, ...]:
    if "全部children必需" in rhs:
        prefix = rhs.split("全部children必需", 1)[1]
        prefix = prefix.split("；", 1)[0]
        values = [item.removeprefix("DESIGN:") for item in _code_tokens(prefix)]
        return _unique(values, label="formal aggregate children")
    scenario = re.search(r"scenario_name\s*==\s*['\"]([^'\"]+)['\"]", rhs)
    if scenario:
        return (scenario.group(1),)
    function_case = re.search(r"F\(([^)]+)\)", rhs)
    if function_case:
        return (function_case.group(1).strip(),)
    tokens = _code_tokens(rhs)
    if tokens:
        return (tokens[0],)
    raise CompileError(f"formal bad mapping has no exact selector: {rhs}")


def _formal_mappings(
    path: Path,
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, set[str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    owner_sections = _sections(lines, re.compile(r"^##\s+(.+?)\s*$"))
    mappings: dict[str, dict[str, tuple[str, ...]]] = {}
    extras: dict[str, set[str]] = {}
    for owner in FORMAL_OWNERS:
        if owner not in owner_sections:
            raise CompileError(f"Formal mapping section missing: {owner}")
        good, bad, _ = _catalog_sources(catalog[owner])
        allowed = {good, *bad}
        source_map: dict[str, tuple[str, ...]] = {}
        section = owner_sections[owner]
        for line in section:
            match = re.match(r"^###\s+Good\s+`([^`]+)`", line)
            if match:
                source = match.group(1)
                if source != good:
                    raise CompileError(f"Formal good source disagrees with catalog: {owner}:{source}")
                selector = FORMAL_RAW_GOOD.get(owner, "")
                if owner == "implementation_blueprint":
                    selectors = ("complete", "delegated_direct_terminal", "supporting_oracle_surface")
                elif selector:
                    selectors = (selector,)
                else:
                    nearby = "\n".join(section)
                    labels = re.findall(r"run_exact_workflow_case\s+label=['`]([^'`]+)['`]", nearby)
                    if len(labels) != 1:
                        raise CompileError(f"cannot resolve Formal good selector exactly: {owner}")
                    selectors = (labels[0],)
                source_map[source] = selectors
                continue
            if not (line.startswith("- `") and "failure=" in line):
                continue
            tokens = _code_tokens(line)
            if not tokens:
                continue
            source = tokens[0]
            if source not in allowed:
                continue
            rhs = line.split("→", 1)[1] if "→" in line else ""
            selectors = _formal_bad_selectors(rhs)
            if source in source_map:
                raise CompileError(f"duplicate Formal source mapping: {owner}:{source}")
            source_map[source] = selectors
        if set(source_map) != allowed:
            raise CompileError(
                f"Formal source mapping inventory mismatch for {owner}: "
                f"missing={sorted(allowed - set(source_map))}; extra={sorted(set(source_map) - allowed)}"
            )
        labels: set[str] = set()
        for line in section:
            if line.startswith(("- runner:", "- model:")):
                match = re.search(r"label=['`]([^'`]+)['`]", line)
                if match:
                    labels.add(match.group(1))
        used = {item for values in source_map.values() for item in values}
        extras[owner] = labels - used
        mappings[owner] = source_map
    return mappings, extras


# The custom annex deliberately names these rows in prose/tables rather than
# one machine-readable table.  Keeping the exact finite lists here makes the
# compiler reject a renamed/deleted annex selector instead of guessing it.
CUSTOM_GOOD: dict[str, tuple[str, ...]] = {
    "code_boundary_conformance": ("green_boundary",),
    "contract_source_audit": ("good_external_contract_source",),
    "runtime_gateway_adoption": ("structured_inventory_passes",),
    "model_test_code_alignment": (
        "aligned_model_code_test_contracts", "source_audited_real_code_claim",
        "counterexample_target_closure_passes", "current_delegating_facade_passes",
        "canonical_relation_handoff_materializes", "plane_aware_model_code_test_bindings_pass",
        "understanding_chain_obligations_are_explicitly_owned",
        "planned_checker_design_ready_but_leaf_execution_not_run",
        "exact_current_leaf_receipts_can_close_each_behavior_block",
        "one_exact_merged_owner_receipt_can_cover_declared_members",
        "delegated_direct_terminal_is_current",
    ),
    "ai_entry_surface_reduction": ("correct_ai_entry_reduction",),
    "harden_ui_real_surface_validation": ("correct_ui_last_mile_hardening",),
    "ui_human_operability_gate": ("correct_ui_human_operability",),
    "ui_flow_structure_skill": ("correct_ui_flow_structure_rollout", "correct_implemented_ui_validation"),
    "user_facing_model_diagrams": (
        "correct_deterministic_projection", "correct_reordered_source_projection",
        "correct_explicit_skip", "correct_not_applicable", "correct_source_change_rejects_stale_projection",
    ),
    "codex_skill_satellites": (
        "current_real_suite_map_and_route_registry", "dynamic_add", "dynamic_remove",
        "dynamic_role_swap", "dynamic_required_file", "evidence_domains_remain_separate",
    ),
    "work_context": (
        "peer_adapter_selection", "current_context_projection",
        "explicit_behavior_source_admission", "multiple_distinct_contexts",
    ),
    "development_process_strategy": (
        "ordinary_path_lightweight", "targeted_sequential", "declared_complete_parallel",
        "budgeted_sequential", "freeze_first_measured", "field_lifecycle",
        "contract_exhaustion", "model_test_alignment", "architecture_reduction",
    ),
    "primary_path_authority": ("complete_plan",),
    "behavior_commitment_ledger": ("native_ledger_review", "live_source_inventory", "reverse_surface_semantic_tests"),
    "model_miss_review": ("correct_model_miss_review", "diagnostic_projection_positive", "diagnostic_budget_bounded"),
    "plan_detailing_compiler": ("PDC01_good_plan_passes", "PDC06_human_review_scopes", "PDC07_spec_mapping_passes"),
    "template_public_release": (
        "ordinary_path_no_template_operation", "explicit_template_reuse_lifecycle",
        "correct_template_release", "current_code_test_bindings",
    ),
    "harden_ui_content_visibility_validation": (
        "focused-ui-core", "ui-templates", "contract-matrix", "ui-flow-structure-model",
        "real-surface-model", "behavior-ledger-model", "field-lifecycle-model",
        "contract_exhaustion", "model_test_alignment", "test_mesh",
        "risk_evidence_ledger", "canonical_contract_chain",
    ),
}

CUSTOM_BAD: dict[str, tuple[str, ...]] = {
    "code_boundary_conformance": (
        "forbidden_input_accepted", "extra_output_and_side_effect", "missing_rejected_input_gate_evidence",
        "internal_path_only_boundary_observation", "alignment_blocks_on_boundary_failure",
    ),
    "contract_source_audit": (
        "missing_code_symbol_blocks", "missing_input_blocks", "missing_return_blocks", "missing_state_write_blocks",
        "extra_side_effect_blocks", "test_calls_helper_blocks", "test_without_assertion_blocks",
    ),
    "runtime_gateway_adoption": (
        "opaque_inventory_id_without_structured_evidence_blocks", "missing_inventory_blocks", "stale_inventory_blocks",
        "uncovered_critical_surface_blocks", "scoped_writer_without_reason_blocks", "proofless_inventory_blocks",
    ),
    "model_test_code_alignment": (
        "pre_code_design_is_ready_but_execution_is_not_run", "missing_source_audit_blocks",
        "counterexample_target_without_replay_blocks", "missing_code_contract_blocks", "extra_code_side_effect_blocks",
        "missing_code_output_blocks", "test_without_code_contract_binding_blocks", "internal_path_only_test_blocks",
        "model_code_test_binding_mismatch_blocks", "stable_primary_path_mismatch_blocks", "stale_facade_delegation_blocks",
        "facade_parallel_success_blocks", "opaque_canonical_relation_handoff_blocks", "cross_plane_code_binding_blocks",
        "understanding_chain_missing_failure_owner_blocks", "parent_failure_list_cannot_be_copied_to_sibling_blocks",
        "owner_wide_result_cannot_be_copied_as_leaf_execution", "validation_parent_receipt_cannot_replace_behavior_leaf",
        "model_native_check_cannot_replace_behavior_leaf", "supporting_input_glob_cannot_grant_coverage_ownership",
        "delegated_terminal_stale_blocks", "delegated_terminal_ambiguity_blocks", "delegated_unknown_branch_blocks",
        "delegated_cycle_blocks", "delegated_nonterminal_call_blocks", "delegated_checker_cannot_borrow_sibling_test_owner",
    ),
    "ai_entry_surface_reduction": ("broken_default_uses_full_api", "broken_compact_drops_safety_evidence", "broken_full_path_missing"),
    "harden_ui_real_surface_validation": (
        "broken_no_observed_inventory", "broken_observed_mapping_grants_permission", "broken_internal_product_content_leak",
        "broken_api_only_functional_chain", "broken_source_cancel_branch_missing", "broken_final_claim_overbroad",
    ),
    "ui_human_operability_gate": (
        "broken_missing_task_coverage", "broken_orphan_primary_control", "broken_duplicate_primary_action",
        "broken_dialog_return", "broken_keyboard_focus", "broken_confused_walkthrough", "broken_overbroad_human_done",
    ),
    "ui_flow_structure_skill": tuple(
        "broken_" + item
        for item in (
            "layout_only_without_ui_model", "missing_expected_product_surface", "cross_surface_product_semantic_drift",
            "invalid_behavior_authority_exception", "typography_role_token_scale_weight_drift",
            "same_intent_business_authority_drift", "fourth_content_visibility_class", "internal_product_content_leak",
            "missing_content_visibility_plan", "unclassified_content_accepted", "untyped_user_need_accepted",
            "overbroad_control_label_exemption_accepted", "internal_content_mapped_to_ui",
            "on_demand_content_visible_by_default", "on_demand_non_display_state_bypass", "on_demand_content_missing_reveal",
            "on_demand_content_missing_return", "on_demand_affordance_or_feedback_gap", "no_parent_child_topology",
            "no_journey_coverage", "no_visible_branch_coverage", "no_typography_handoff",
            "implementation_without_feature_alignment_sequence", "implementation_without_clickthrough_sequence",
            "stale_implementation_evidence_sequence", "opaque_content_visibility_evidence_sequence",
            "cross_content_visibility_evidence_sequence",
        )
    ),
    "user_facing_model_diagrams": (
        "broken_diagram_model_mismatch", "broken_diagram_as_checker_evidence", "broken_route_edge_semantics_lost",
        "broken_stale_diagram_reused",
    ),
    "codex_skill_satellites": (
        "missing_declared_member", "extra_reserved_member", "duplicate_discovered_member",
        "discovered_member_role_mismatch", "internal_helper_exposed_public", "required_member_file_missing",
        "fixed_count_mismatch", "fixed_count_parallel_authority",
        "stale_suite_map_fingerprint", "stale_route_registry_fingerprint", "stale_skill_inputs_fingerprint",
        "stale_contract_inputs_fingerprint", "stale_suite_scripts_fingerprint", "stale_suite_tests_fingerprint",
        "stale_model_fingerprint", "stale_runner_fingerprint", "broken_member_missing", "broken_member_extra",
        "broken_member_duplicate", "broken_member_misclassified", "broken_member_internal_helper_public",
        "broken_fixed", "broken_stale", "broken_collapsed", "broken_overclaim",
    ),
    "work_context": tuple("known_bad:" + item for item in (
        "unregistered_adapter", "unbounded_root", "missing_required_role", "stale_fingerprint", "duplicate_context",
        "provider_write", "provider_execution", "provider_validation", "authority_bridge",
    )),
    "development_process_strategy": (
        "cheaper_non_equivalent", "hard_blocker", "unsafe_parallel", "unrelated_findings", "missing_primary_owner",
        "incomplete_revalidation", "qualitative_minimum_overclaim", "global_optimum_overclaim", "stale_decision",
        "declared_order_violation", "measured_step_cost_missing", "dominated_caller_preselection", "unresolved_non_dominated_boundary",
        "broken_selector",
    ),
    "primary_path_authority": (
        "broken_a_failed_b_success", "broken_old_field_fallback", "broken_manual_recovery_auto_invoked",
        "broken_two_paths_same_exact_intent", "broken_missing_candidate_inventory", "broken_stale_material_evidence",
    ),
    "behavior_commitment_ledger": (
        "duplicate_exact_intent_commitment", "delegate_commitment_forbidden", "implementation_source_cannot_own_promise",
    ),
    "model_miss_review": (
        "classify_without_same_plane_lookup", "finalize_without_review", "validate_fix_without_representation",
        "validate_without_root_cause_backpropagation", "point_fix_only_without_generalized_bad_case",
        "validate_without_known_bug_holdout_role", "validate_without_target_aware_replay_evidence",
        "validate_without_same_class_test_evidence", "validate_without_owner_code_contract",
        "validate_without_legacy_path_disposition", "validate_recurring_without_canonical_contributions",
        "missing_positive_witness",
    ),
    "plan_detailing_compiler": (
        "PDC02_vague_plan_blocks", "PDC03_happy_path_only_blocks", "PDC04_missing_rework_blocks",
        "PDC05_ungated_side_effect_blocks", "PDC08_spec_mapping_gap_blocks",
    ),
    "template_public_release": (
        "ordinary_path_accidentally_searches_templates", "merge_without_authorization", "harvest_without_authorization",
        "merge_without_source", "merge_repeats_source", "merge_conflict_without_rationale",
        "harvest_duplicate_as_new_template", "harvest_incomplete_contract", "reuse_without_search",
        "search_without_current_test_binding", "private_template_leak", "release_before_checks",
    ),
    "harden_ui_content_visibility_validation": tuple(
        [f"missing:{item}" for item in ("focused-ui-core", "ui-templates", "contract-matrix", "ui-flow-structure-model", "real-surface-model", "behavior-ledger-model", "field-lifecycle-model")]
        + [f"failed:{item}" for item in ("focused-ui-core", "ui-templates", "contract-matrix", "ui-flow-structure-model", "real-surface-model", "behavior-ledger-model", "field-lifecycle-model")]
        + [f"stale:{item}" for item in ("focused-ui-core", "ui-templates", "contract-matrix", "ui-flow-structure-model", "real-surface-model", "behavior-ledger-model", "field-lifecycle-model")]
        + [f"not_run:{item}" for item in ("focused-ui-core", "ui-templates", "contract-matrix", "ui-flow-structure-model", "real-surface-model", "behavior-ledger-model", "field-lifecycle-model")]
        + [f"report_missing:{item}" for item in ("contract_exhaustion", "model_test_alignment", "test_mesh", "risk_evidence_ledger")]
        + [f"forged_report:{item}" for item in ("contract_exhaustion", "model_test_alignment", "test_mesh", "risk_evidence_ledger")]
        + ["canonical_chain_false", "forged_green_child"]
    ),
}


CUSTOM_EXPLICIT = {
    "model_test_code_alignment": {
        "declared-negative-suite": (
            "pre_code_design_is_ready_but_execution_is_not_run", "missing_source_audit_blocks",
            "counterexample_target_without_replay_blocks", "missing_code_contract_blocks",
            "extra_code_side_effect_blocks", "missing_code_output_blocks",
            "test_without_code_contract_binding_blocks", "internal_path_only_test_blocks",
            "model_code_test_binding_mismatch_blocks", "stable_primary_path_mismatch_blocks",
            "stale_facade_delegation_blocks", "facade_parallel_success_blocks",
            "opaque_canonical_relation_handoff_blocks", "cross_plane_code_binding_blocks",
            "understanding_chain_missing_failure_owner_blocks",
        ),
        "parent_failure_list_cannot_be_copied_to_sibling_blocks": "parent_failure_list_cannot_be_copied_to_sibling_blocks",
        "owner_wide_result_cannot_be_copied_as_leaf_execution": "owner_wide_result_cannot_be_copied_as_leaf_execution",
        "validation_parent_receipt_cannot_replace_behavior_leaf": "validation_parent_receipt_cannot_replace_behavior_leaf",
        "model_native_check_cannot_replace_behavior_leaf": "model_native_check_cannot_replace_behavior_leaf",
        "supporting_input_glob_cannot_grant_coverage_ownership": "supporting_input_glob_cannot_grant_coverage_ownership",
        "delegated_terminal_stale_blocks": "delegated_terminal_stale_blocks",
        "delegated_terminal_ambiguity_blocks": "delegated_terminal_ambiguity_blocks",
        "delegated_unknown_branch_blocks": "delegated_unknown_branch_blocks",
        "delegated_cycle_blocks": "delegated_cycle_blocks",
        "delegated_nonterminal_call_blocks": "delegated_nonterminal_call_blocks",
        "delegated_checker_cannot_borrow_sibling_test_owner": "delegated_checker_cannot_borrow_sibling_test_owner",
    },
    "work_context": {
        "unregistered-adapter": "known_bad:unregistered_adapter", "unbounded-root": "known_bad:unbounded_root",
        "missing-role": "known_bad:missing_required_role", "stale-fingerprint": "known_bad:stale_fingerprint",
        "duplicate-context": "known_bad:duplicate_context", "provider-write": "known_bad:provider_write",
        "provider-execution": "known_bad:provider_execution", "provider-validation": "known_bad:provider_validation",
        "authority-bridge": "known_bad:authority_bridge",
    },
    "model_miss_review": {
        # The catalog has one aggregate bad declaration plus one explicit
        # diagnostic leaf.  Keep the aggregate's eleven named scenarios
        # separate from the missing-positive-witness callback; otherwise a
        # broad runner row could be mistaken for that distinct oracle.
        "declared-negative-suite": (
            "classify_without_same_plane_lookup", "finalize_without_review",
            "validate_fix_without_representation", "validate_without_root_cause_backpropagation",
            "point_fix_only_without_generalized_bad_case", "validate_without_known_bug_holdout_role",
            "validate_without_target_aware_replay_evidence", "validate_without_same_class_test_evidence",
            "validate_without_owner_code_contract", "validate_without_legacy_path_disposition",
            "validate_recurring_without_canonical_contributions",
        ),
        "missing-positive-witness": "missing_positive_witness",
    },
}


def _assert_custom_document_selectors(path: Path, owner: str, selectors: Iterable[str]) -> None:
    text = path.read_text(encoding="utf-8")
    # A few annex rows intentionally preserve the literal predicate or the
    # prose hyphenation used by the gate contract.  These are explicit
    # spelling aliases, not fuzzy matching: the emitted selector remains the
    # stable registry key below, while the compiler requires the corresponding
    # exact contract marker to be present in the annex.
    annex_aliases = {
        "canonical_chain_false": "canonical_chain=False",
        "forged_green_child": "forged-green-child",
    }
    for selector in selectors:
        probe = selector
        if selector.startswith("broken_") and selector[7:] in text:
            probe = selector[7:]
        if selector.startswith("known_bad:"):
            probe = selector.split(":", 1)[1]
        if selector.startswith(("missing:", "failed:", "stale:", "not_run:", "report_missing:", "forged_report:")):
            probe = selector.split(":", 1)[1]
        if probe not in text and annex_aliases.get(probe, "") not in text:
            raise CompileError(f"custom selector is absent from {owner} annex: {selector}")


def _custom_mappings(
    path: Path,
    catalog: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, tuple[str, ...]]]:
    mappings: dict[str, dict[str, tuple[str, ...]]] = {}
    for owner in CUSTOM_OWNERS:
        good, bad, _ = _catalog_sources(catalog[owner])
        if owner not in CUSTOM_GOOD or owner not in CUSTOM_BAD:
            raise CompileError(f"custom selector table missing: {owner}")
        _assert_custom_document_selectors(path, owner, (*CUSTOM_GOOD[owner], *CUSTOM_BAD[owner]))
        source_map: dict[str, tuple[str, ...]] = {good: CUSTOM_GOOD[owner]}
        if owner in CUSTOM_EXPLICIT:
            explicit = CUSTOM_EXPLICIT[owner]
        else:
            explicit = {}
        remaining = list(CUSTOM_BAD[owner])
        for source in bad:
            suffix = source.rsplit(":", 1)[-1]
            if suffix in explicit:
                declared = explicit[suffix]
                mapped = (declared,) if isinstance(declared, str) else tuple(declared)
                if not mapped:
                    raise CompileError(f"custom explicit mapping is empty: {owner}:{source}")
                source_map[source] = _unique(mapped, label=f"custom:{owner}:{source}")
                remaining = [item for item in remaining if item not in source_map[source]]
            elif len(bad) == 1:
                source_map[source] = CUSTOM_BAD[owner]
                remaining = []
            else:
                raise CompileError(f"custom bad source has no exact mapping: {owner}:{source}")
        if set(source_map) != {good, *bad}:
            raise CompileError(f"custom source mapping inventory mismatch: {owner}")
        mappings[owner] = source_map
    return mappings


def _benchmark_mappings(
    path: Path,
    catalog: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    text = path.read_text(encoding="utf-8")
    for probe in ("payment-order-retry-identity", "permission-revocation-cache", "deletion-index-export", "missing-semantics", "truncated"):
        if probe not in text:
            raise CompileError(f"benchmark annex lacks exact fixture marker: {probe}")
    families = ("payment-order-retry-identity", "permission-revocation-cache", "deletion-index-export")
    variants = ("bad", "repaired", "missing-semantics", "truncated")
    leaves = tuple(f"benchmark:{family}:{variant}" for family in families for variant in variants)
    good, bad, boundary = _catalog_sources(catalog[BENCHMARK_OWNER])
    if len(bad) != 4:
        raise CompileError("benchmark catalog must have four bad declarations")
    return {
        good: tuple(f"benchmark:{family}:repaired" for family in families),
        bad[0]: tuple(f"benchmark:{family}:bad" for family in families),
        bad[1]: tuple(f"benchmark:{family}:repaired" for family in families),
        bad[2]: tuple(f"benchmark:{family}:missing-semantics" for family in families),
        bad[3]: tuple(f"benchmark:{family}:truncated" for family in families),
        boundary: leaves,
    }


def _scope(owner: str) -> str:
    return "implementation_boundary" if owner in {
        "code_boundary_conformance", "contract_source_audit", "runtime_gateway_adoption",
        "model_test_code_alignment", "primary_path_authority", "behavior_commitment_ledger",
        "harden_ui_content_visibility_validation", "plan_detailing_compiler",
    } else "model_policy"


def _observed_status(owner: str, kind: str, selector: str) -> str:
    if kind == "boundary":
        # Boundary is an explicit finite aggregate.  The producer emits a
        # separate boundary row only after every declared child result is
        # present and passing, so ``ok`` is the only honest expected model
        # status.  A missing/incomplete boundary is represented by a blocked
        # result and fails the strict binding gate; it is never a planned
        # ``not_run`` pass.
        return "ok"
    if owner in SCENARIO_OWNERS:
        return "ok" if kind == "good" else "violation"
    if owner == BENCHMARK_OWNER:
        return "pass" if selector.endswith(":repaired") else "fail" if selector.endswith(":bad") else "blocked"
    if kind == "good":
        return "ok"
    if owner in FORMAL_OWNERS:
        return "ok" if owner == "implementation_blueprint" else "violation"
    if owner in {"work_context", "development_process_strategy", "harden_ui_real_surface_validation", "ui_human_operability_gate"}:
        return "blocked" if owner == "work_context" or selector in {"broken_selector"} else "ok"
    if owner == "ui_flow_structure_skill" and selector == "broken_no_parent_child_topology":
        return "violation"
    if owner == "model_miss_review" and selector in {"missing_positive_witness"}:
        return "blocked"
    if owner == "plan_detailing_compiler":
        return "ok"
    return "violation"


def _case_kind(source: str, good: str, boundary: str) -> str:
    if source == good:
        return "good"
    if source == boundary:
        return "boundary"
    return "bad"


def _surface_ids(root: Path) -> dict[str, str]:
    try:
        from flowguard.implementation_inventory import implementation_surface_id
    except ImportError as exc:
        raise CompileError(f"flowguard package is not importable: {exc}") from exc
    definition = _read_json(root / ".flowguard" / "models" / "owners" / "authoritative_model_system" / "software_blueprint_definition.json")
    contracts = definition.get("composite_behavior_contracts")
    if not isinstance(contracts, list):
        raise CompileError("composite_behavior_contracts is not an array")
    result: dict[str, str] = {}
    for item in contracts:
        if not isinstance(item, Mapping):
            raise CompileError("composite behavior contract is not an object")
        owner = _text(item.get("owner_id"), label="composite owner_id")
        surface_key = _text(item.get("surface_key"), label=f"surface_key:{owner}")
        path_text, sep, symbol = surface_key.partition("#")
        if not sep:
            raise CompileError(f"surface_key lacks symbol separator: {surface_key}")
        result[owner] = implementation_surface_id(path_text, symbol, "module")
    return result


def _producer_override_bindings(path: Path, binding_type: Any) -> tuple[Any, ...]:
    """Load the small, current producer-to-blueprint additions.

    The scenario annexes describe the historical seven projections per owner.
    A current producer can also expose a real leaf that was not present in
    those frozen annex tables.  Such a leaf must be declared in the repository
    beside the generated mapping; silently deriving it from a runner would
    make the denominator depend on execution.  The rows are parsed through the
    same typed ``NativeCaseBinding`` constructor as the annex compiler.
    """

    if path.is_symlink() or not path.is_file():
        raise CompileError(f"producer override source is missing or a symlink: {path}")
    payload = _read_json(path)
    if payload.get("schema_version") != "flowguard.native_case_producer_overrides.v1":
        raise CompileError("producer override schema is not current")
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise CompileError("producer override bindings must be a non-empty array")
    allowed = {
        "owner_id",
        "blueprint_case_id",
        "blueprint_source_case_id",
        "native_case_ids",
        "case_kind",
        "evidence_scope",
        "covered_dimensions",
        "expected_status",
        "expected_observed_status",
        "protected_failure_ids",
        "expected_finding_codes",
        "required_child_case_ids",
        "required_trace_labels",
    }
    result: list[Any] = []
    for index, raw in enumerate(raw_bindings):
        if not isinstance(raw, Mapping):
            raise CompileError(f"producer override bindings[{index}] is not an object")
        unknown = sorted(set(raw) - allowed)
        missing = sorted(allowed - set(raw))
        if unknown or missing:
            raise CompileError(
                f"producer override bindings[{index}] fields mismatch: "
                f"missing={missing}; unknown={unknown}"
            )
        try:
            result.append(binding_type(**dict(raw)))
        except (TypeError, ValueError) as exc:
            raise CompileError(f"invalid producer override bindings[{index}]: {exc}") from exc
    return tuple(result)


def compile_registry(root: Path, audit_root: Path) -> Mapping[str, Any]:
    # Import the package from the requested source root, not from a similarly
    # named checkout.  This keeps the compiler's identity tied to the target.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    catalog = _catalog(audit_root / CATALOG_NAME)
    scenario, scenario_oracle = _scenario_mappings(audit_root / SCENARIO_NAME, catalog)
    formal, formal_extras = _formal_mappings(audit_root / FORMAL_NAME, catalog)
    custom = _custom_mappings(audit_root / CUSTOM_NAME, catalog)
    benchmark = _benchmark_mappings(audit_root / BENCHMARK_NAME, catalog)
    surface_ids = _surface_ids(root)
    if set(surface_ids) != set(catalog):
        raise CompileError("blueprint composite surface inventory does not match catalog owners")

    manifest = root / ".flowguard" / "models" / "regression-manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise CompileError(f"current regression manifest is missing or a symlink: {manifest}")
    # Import after source-root insertion so the canonical source identity helper
    # is the current target package.
    from flowguard.native_case_protocol import GOOD_DIMENSIONS as _GOOD
    from flowguard.native_case_protocol import BAD_DIMENSIONS as _BAD
    from flowguard.native_case_protocol import BOUNDARY_DIMENSIONS as _BOUNDARY
    from flowguard.native_case_protocol import NativeCaseBinding
    from flowguard.native_case_mapping import compute_native_case_mapping_fingerprint
    from flowguard.source_identity import source_file_fingerprint

    source_manifest_fingerprint = source_file_fingerprint(manifest)
    producer_override_path = root / ".flowguard" / "models" / PRODUCER_OVERRIDES_NAME
    producer_overrides = _producer_override_bindings(producer_override_path, NativeCaseBinding)
    source_paths = tuple(
        item.replace("\\", "/")
        for item in (
            ".flowguard/models/regression-manifest.json",
            ".flowguard/models/" + PRODUCER_OVERRIDES_NAME,
            str((audit_root / CATALOG_NAME).resolve()),
            str((audit_root / SCENARIO_NAME).resolve()),
            str((audit_root / FORMAL_NAME).resolve()),
            str((audit_root / CUSTOM_NAME).resolve()),
            str((audit_root / BENCHMARK_NAME).resolve()),
            ".flowguard/models/owners/authoritative_model_system/software_blueprint_definition.json",
        )
    )

    selector_maps: dict[str, dict[str, tuple[str, ...]]] = {}
    selector_maps.update(scenario)
    selector_maps.update(formal)
    selector_maps.update(custom)
    selector_maps[BENCHMARK_OWNER] = benchmark
    # The catalog's boundary ID is a planned finite domain, not a Markdown
    # selector.  Keep it explicit in the registry while leaving the annex
    # parsers strict about every declared good/bad source row.
    for owner, declaration in catalog.items():
        if owner == BENCHMARK_OWNER:
            continue
        _good, _bad, boundary = _catalog_sources(declaration)
        selector_maps[owner][boundary] = ("boundary",)
    bindings_without_fp: list[NativeCaseBinding] = []
    for owner, declaration in catalog.items():
        good, bad, boundary = _catalog_sources(declaration)
        source_map = selector_maps[owner]
        source_ids = {good, *bad, boundary}
        if set(source_map) != source_ids:
            raise CompileError(f"source mapping inventory mismatch at final assembly: {owner}")
        for source in (good, *bad, boundary):
            kind = _case_kind(source, good, boundary)
            selectors = source_map[source]
            # The benchmark's repaired leaves are deliberately reused by the
            # positive aggregate and the repair-preservation bad obligation.
            # They execute once and have the positive (input/state/output/...)
            # result contract in both projections; the source-case ID keeps
            # the second obligation distinct without falsifying its receipt
            # dimensions.
            if owner == BENCHMARK_OWNER and selectors and all(
                selector.endswith(":repaired") for selector in selectors
            ):
                kind = "good"
            native_ids = tuple(
                selector if owner == BENCHMARK_OWNER else _qualified(owner, selector)
                for selector in selectors
            )
            required_child_case_ids: tuple[str, ...] = ()
            if source == boundary:
                # Boundary is a real finite aggregate over the exact native
                # leaves declared by this owner.  The producer must emit the
                # aggregate only after each child is observed; the verifier
                # checks both the child set and the concrete child rows.  This
                # is not a copied aggregate pass: it is a distinct boundary
                # receipt consuming the already-produced atomic observations.
                native_ids = (_boundary_native_id(owner),)
                required_child_case_ids = tuple(
                    sorted(
                        {
                            native_id
                            for child_source in (good, *bad)
                            for child_selector in source_map[child_source]
                            for native_id in (
                                child_selector
                                if owner == BENCHMARK_OWNER
                                else _qualified(owner, child_selector),
                            )
                        }
                    )
                )
                if not required_child_case_ids:
                    raise CompileError(
                        f"boundary has no declared native children: {owner}"
                    )
            dimensions = _GOOD if kind == "good" else _BAD if kind == "bad" else _BOUNDARY
            expected_observed = _observed_status(owner, kind, selectors[0])
            surface_id = surface_ids[owner]
            blueprint_case_id = f"behavior-case:{surface_id}:{kind}:{source}"
            bindings_without_fp.append(
                NativeCaseBinding(
                    owner_id=f"model:{owner}",
                    blueprint_case_id=blueprint_case_id,
                    blueprint_source_case_id=source,
                    native_case_ids=native_ids,
                    case_kind=kind,
                    evidence_scope=_scope(owner),
                    covered_dimensions=tuple(dimensions),
                    expected_status="pass",
                    expected_observed_status=expected_observed,
                    required_child_case_ids=required_child_case_ids,
                )
            )

    existing_blueprints = {row.blueprint_case_id for row in bindings_without_fp}
    existing_native = {
        (row.owner_id, native_id)
        for row in bindings_without_fp
        for native_id in row.native_case_ids
    }
    for index, binding in enumerate(producer_overrides):
        if binding.blueprint_case_id in existing_blueprints:
            raise CompileError(
                f"producer override bindings[{index}] duplicates blueprint case: "
                f"{binding.blueprint_case_id}"
            )
        duplicate_native = [
            native_id
            for native_id in binding.native_case_ids
            if (binding.owner_id, native_id) in existing_native
        ]
        if duplicate_native:
            raise CompileError(
                f"producer override bindings[{index}] duplicates native rows: "
                f"{duplicate_native}"
            )
        existing_blueprints.add(binding.blueprint_case_id)
        existing_native.update(
            (binding.owner_id, native_id)
            for native_id in binding.native_case_ids
        )
        bindings_without_fp.append(binding)

    diagnostic_selectors: dict[str, set[str]] = {
        owner: set(values)
        for owner, values in EXPLICIT_DIAGNOSTIC_SELECTORS.items()
    }
    for owner, values in formal_extras.items():
        diagnostic_selectors.setdefault(owner, set()).update(values)
    diagnostic_native_case_ids = tuple(
        sorted(
            _qualified(owner, selector)
            for owner, selectors in diagnostic_selectors.items()
            for selector in selectors
        )
    )

    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_manifest_fingerprint,
        source_paths=source_paths,
        bindings=bindings_without_fp,
        diagnostic_native_case_ids=diagnostic_native_case_ids,
    )
    # Rebuild rows with the root fingerprint.  The constructor and registry
    # loader then enforce that every row points to this exact mapping.
    bindings = tuple(
        NativeCaseBinding(
            **{
                **{
                    key: value
                    for key, value in row.to_dict(include_fingerprint=False).items()
                    if key != "schema_version"
                },
                "mapping_fingerprint": mapping_fp,
            }
        )
        for row in bindings_without_fp
    )
    from flowguard.native_case_mapping import NativeCaseMappingRegistry
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=source_manifest_fingerprint,
        source_paths=source_paths,
        bindings=bindings,
        diagnostic_native_case_ids=diagnostic_native_case_ids,
    )
    payload = registry.to_dict()
    expected_binding_count = len(catalog) * 7 + len(producer_overrides)
    if len(bindings) != expected_binding_count:
        raise CompileError(
            f"compiled binding count is {len(bindings)}, expected {expected_binding_count}"
        )
    # Ensure every catalog declaration is represented exactly once and the
    # three boundary namespaces remain one stable case per owner.
    expected_blueprints = expected_binding_count
    if len(registry.blueprint_case_ids) != expected_blueprints:
        raise CompileError(f"compiled blueprint case count is {len(registry.blueprint_case_ids)}, expected {expected_blueprints}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--audit-root", type=Path, default=AUDIT_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    audit_root = args.audit_root.expanduser().resolve()
    output = (args.output or (root / ".flowguard" / "models" / "native-case-mapping.json")).expanduser().resolve()
    try:
        payload = compile_registry(root, audit_root)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    except (CompileError, OSError, UnicodeError, ValueError) as exc:
        print(f"native case mapping compile blocked: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "compiled",
        "output": str(output),
        "binding_count": len(payload["bindings"]),
        "mapping_fingerprint": payload["mapping_fingerprint"],
        "source_manifest_fingerprint": payload["source_manifest_fingerprint"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
