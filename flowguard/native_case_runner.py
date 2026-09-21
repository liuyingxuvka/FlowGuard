"""Small producer-side bridge for native model case evidence.

The verification owner scripts predate the strict native-case envelope and
therefore expose their results in a few different, already-existing report
shapes.  This module does not run another check and does not invent a verdict:
it captures the result returned by the owner, preserves its machine-readable
artifacts or terminal transcript as raw evidence, and projects each observed
case into the common envelope consumed by the model-regression verifier.

It is intentionally a producer helper.  Readers still verify the envelope,
raw bytes, owner identity, marker, and (when supplied) the exact frozen case
contracts.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any, Callable, Mapping, Sequence

from .native_case_protocol import (
    CASE_DIMENSIONS,
    GOOD_DIMENSIONS,
    NATIVE_CASE_RESULT_SCHEMA,
    NativeModelCaseResult,
    NativeCaseProtocolError,
    fingerprint_payload,
)
from .native_case_mapping import (
    NativeCaseMappingError,
    NativeCaseMappingRegistry,
    load_native_case_mapping,
)


_CASE_KEYS = ("scenario_name", "source_case_id", "case_id", "case", "name", "id")
_STATUS_KEYS = ("status", "observed_status", "decision", "outcome")
_OK_KEYS = ("ok", "passed", "match", "observed_ok")
_CASE_CONTAINERS = {
    "results",
    "case_results",
    "cases",
    "known_bad_proofs",
    "checks",
    "reviews",
    "evidence_runs",
}

# These are the only owners whose native leaf identity has a distinct wire
# namespace.  The distinction is part of the checked-in case mapping: it is
# not inferred from a report count or a similar-looking case name.
_SCENARIO_OWNERS = frozenset(
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
_BENCHMARK_OWNER = "bounded_system_composition_benchmark"
# These five owners are the finite scenario producers whose report is now
# converted to the typed native tuple by the owner itself.  They deliberately
# bypass the historical capture bridge below: stdout, globals, and an
# existing JSON file are never evidence for these owners.
_STRICT_NATIVE_OWNER_IDS = frozenset(
    {
        "architecture_reduction",
        "hierarchical_model_mesh",
        "mesh_target_split_derivation",
        "structure_refactor_mesh",
        "test_evidence_mesh",
    }
)
_SUMMARY_CASE_NAMES = frozenset(
    {
        "status", "result", "decision", "outcome", "observed", "expected", "evidence",
        # Wrapper-only projections.  These labels are emitted by a report
        # formatter or by the generic model serializer, not by a registered
        # native leaf.  Keeping them out of the leaf inventory prevents a
        # summary line from becoming a foreign case while preserving the raw
        # transcript in ``native-source.json``.
        "anonymous",
        "model_report",
        "scenario_review",
        "model-miss diagnostic projection",
        # Public benchmark runner summary; the twelve family/variant rows are
        # the executable leaves and this aggregate label has no registry
        # binding of its own.
        "bounded_system_benchmark",
    }
)

# Primary Path Authority calls the same typed reviewer once for the complete
# plan and once for each named counterexample.  The plan id is the stable
# producer selector; keeping this finite table here lets the native bridge
# project the outer assertion without treating a report's finding list as a
# set of guessed leaves.
_PRIMARY_PATH_PLAN_CASES = {
    "complete-primary-path-authority": ("complete_plan", True),
    "broken-a-failed-b-success": ("broken_a_failed_b_success", False),
    "broken-old-field-fallback": ("broken_old_field_fallback", False),
    "broken-manual-recovery-auto-invoked": ("broken_manual_recovery_auto_invoked", False),
    "broken-two-paths-same-exact-intent": ("broken_two_paths_same_exact_intent", False),
    "broken-missing-candidate-inventory": ("broken_missing_candidate_inventory", False),
    "broken-stale-material-evidence": ("broken_stale_material_evidence", False),
}

# Existing named producer callbacks used by the verification owners.  This is
# an allow-list, not reflective discovery: native_main wraps only callbacks
# that are explicitly part of the owner contract and captures each call once.
_OWNER_CAPTURE_FUNCTIONS: Mapping[str, tuple[str, ...]] = {
    "code_boundary_conformance": ("run_rollout_review",),
    "contract_source_audit": ("run_rollout_review",),
    "runtime_gateway_adoption": ("run_inventory_review",),
    "model_test_code_alignment": (
        "run_rollout_review",
        "run_evidence_projection_review",
        "run_delegated_helper_graph_review",
        "run_native_pytest_contract",
    ),
    "ai_entry_surface_reduction": ("run_case",),
    "harden_ui_real_surface_validation": ("run_case",),
    "ui_human_operability_gate": ("run_case",),
    "ui_flow_structure_skill": ("run_sequence", "run_rejected_release_sequence"),
    "user_facing_model_diagrams": ("run_case", "print_case"),
    "codex_skill_satellites": (
        "_run",
        "_accepted",
        "_rejected_with",
        "_stale_rejected",
        "_print_case",
    ),
    "work_context": ("run_model_checks",),
    # The strategy surface was contracted to one canonical optimization
    # review.  Its child reports are invoked through the owner module (and
    # emitted as the explicit structured ``native_cases`` rows), not through
    # globals in this bridge.  Keeping the retired callback names here would
    # make the current runtime advertise a removed public vocabulary while
    # adding no capture coverage.
    "development_process_strategy": (),
    "maintenance_obligation_memory": ("run_workflow_suite",),
    "model_topology_hazard_review": ("run_workflow_suite",),
    "state_closure_gate": ("run_workflow_suite",),
    "primary_path_authority": ("review_primary_path_authority",),
    "behavior_commitment_ledger": (
        "review_behavior_commitment_ledger",
        "audit_flowguard_behavior_commitment_source_inventory",
    ),
    "model_miss_review": (
        "run_checks",
        "_check_diagnostic_projection",
        "_native_case_projection",
    ),
    "plan_detailing_compiler": ("run_plan_detailing_review",),
    "template_public_release": ("run_checks",),
    "harden_ui_content_visibility_validation": (
        "review_model_test_alignment",
        "review_test_mesh",
        "review_risk_evidence_ledger",
        "contract_exhaustion_report",
    ),
    "development_process_flow": (
        "review_scenarios",
        "run_author_shadow_sync_model",
        "run_implementation_admission_model",
        "run_release_identity_model",
        "run_path_quality_lifecycle_model",
    ),
    "default_replacement_field_lifecycle": (
        "review_field_lifecycle",
        "ui_reader_handoff_contract",
        "product_language_authority_field_contract",
    ),
    "existing_model_preflight": (
        "review_existing_model_preflight",
        "run_exact_owner_identity_review",
    ),
    "minimum_valuable_model_entry": (
        "run_narrow_entry_projection_review",
        "run_ordinary_entry_review",
        "run_rejection_examples",
    ),
    "guidance_compression": (
        "review_prompt_bundles",
        "run_real_load_graph_budget_review",
        "architecture_reduction_report",
        "development_process_report",
    ),
    "maintenance_obligation_memory": (
        "build_maintenance_obligation_report",
        "review_risk_evidence_ledger",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "model_topology_hazard_review": (
        "review_topology_hazards",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "state_closure_gate": (
        "review_state_closure",
        "run_helper_cases",
        "run_workflow_suite",
    ),
    "self_maintenance_mesh": (
        "review_flowguard_self_maintenance",
        "review_route_admission",
        "run_narrow_route_admission_review",
        "run_plane_upgrade_contract_binding",
        "run_receipt_parent_review",
        "run_route_profile_review",
        "run_route_topology_review",
        "run_semantic_mesh_verification_review",
        "run_skill_self_governance",
        "run_workflow_suite",
    ),
}


@dataclass(frozen=True)
class _CapturedCall:
    """One exact callback return plus callbacks nested inside it."""

    function_name: str
    args: tuple[Any, ...]
    kwargs: Mapping[str, Any]
    result: Any
    nested: tuple[Any, ...] = ()
    parent_function: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            # Keep the immutable call receipt bounded.  The typed result is
            # projected into ``cases`` separately; serialising a full model
            # trace here used to duplicate every transition and could create
            # hundreds of megabytes for one owner.  The summary retains
            # enough shape/fingerprint information to audit the producer
            # without becoming a second result authority.
            "args": _bounded_source_summary(self.args),
            "kwargs": _bounded_source_summary(dict(self.kwargs)),
            "result": _bounded_source_summary(self.result),
            "nested": [_bounded_source_summary(item) for item in self.nested],
            "parent_function": self.parent_function,
        }


_SOURCE_SEQUENCE_FIELDS = (
    "results",
    "case_results",
    "cases",
    "known_bad_proofs",
    "checks",
    "reviews",
    "evidence_runs",
    "traces",
    "final_states",
    "violations",
    "evidence",
)
_SOURCE_SCALAR_FIELDS = (
    "scenario_name",
    "name",
    "status",
    "decision",
    "diagnostic_status",
    "owner_decision",
    "observed_status",
    "ok",
    "expected_ok",
    "observed_ok",
    "closure_licensed",
)


def _bounded_source_summary(value: Any, *, depth: int = 0) -> Any:
    """Return a deterministic, small summary for a captured call receipt.

    This function is used only for ``structured_reports`` in
    ``native-source.json``.  Behavioural leaf projection continues to inspect
    the live typed return object through the explicit projectors above.  A
    bounded summary avoids duplicating large traces while retaining the
    producer name, scalar verdicts, collection sizes, and a short sample of
    mapping/sequence keys for diagnosis.
    """

    if depth > 3:
        return {"type": type(value).__name__}
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 256:
            return value[:256] + "…"
        return value
    if isinstance(value, Mapping):
        keys = sorted(str(key) for key in value)[:24]
        return {
            "type": "mapping",
            "keys": keys,
            "size": len(value),
            "scalars": {
                str(key): _bounded_source_summary(value[key], depth=depth + 1)
                for key in keys
                if key in value and isinstance(value[key], (str, int, float, bool))
            },
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        return {
            "type": type(value).__name__,
            "size": len(items),
            "sample": [
                _bounded_source_summary(item, depth=depth + 1)
                for item in items[:4]
            ],
        }
    summary: dict[str, Any] = {"type": type(value).__name__}
    for field_name in _SOURCE_SCALAR_FIELDS:
        try:
            field_value = getattr(value, field_name)
        except AttributeError:
            continue
        if isinstance(field_value, (str, int, float, bool)) or field_value is None:
            summary[field_name] = _bounded_source_summary(field_value, depth=depth + 1)
    for field_name in _SOURCE_SEQUENCE_FIELDS:
        try:
            field_value = getattr(value, field_name)
        except AttributeError:
            continue
        if isinstance(field_value, (str, bytes, Mapping)):
            continue
        try:
            size = len(field_value)
        except (TypeError, AttributeError):
            continue
        summary[f"{field_name}_count"] = size
    return summary


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _valid_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _case_id(raw: Mapping[str, Any]) -> str:
    for key in _CASE_KEYS:
        value = _valid_text(raw.get(key))
        if value:
            return value
    return ""


def _status(raw: Mapping[str, Any], *, ok: bool) -> str:
    # ``observed_status`` is the model's actual result (for example
    # ``violation``), while ``status`` may be the wrapper's oracle verdict
    # (for example ``expected_violation_observed``).  Keep the two distinct.
    for key in ("observed_status", "status", "decision", "outcome"):
        value = _valid_text(raw.get(key))
        if value:
            return value
    if raw.get("observed_ok") is False:
        return "violation"
    return "pass" if ok else "fail"


def _observed_ok(raw: Mapping[str, Any]) -> bool:
    for key in _OK_KEYS:
        value = raw.get(key)
        if isinstance(value, bool):
            return value
        if key == "match" and isinstance(value, str):
            return value.strip().casefold() in {"yes", "true", "pass", "ok"}
    return False


def _finding_codes(raw: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    # Scenario owners expose invariant labels as ``observed_violation_names``
    # on the typed ScenarioRun.  They are findings for the *model* oracle even
    # when the enclosing check passes because the violation was expected.  Do
    # not drop them while projecting the report into the native envelope.
    for key in (
        "finding_codes",
        "expected_finding_codes",
        "violations",
        "observed_finding_codes",
        "observed_violation_names",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            value = (value,)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                text = _valid_text(item)
                if text and text not in values:
                    values.append(text)
    return tuple(values)


def _is_case_mapping(raw: Mapping[str, Any]) -> bool:
    identifier = _case_id(raw)
    if not identifier:
        return False
    return any(key in raw for key in (*_OK_KEYS, *_STATUS_KEYS, "expected_ok"))


def _collect_json_cases(value: Any, found: list[dict[str, Any]], *, parent_key: str = "") -> None:
    if isinstance(value, Mapping):
        if _is_case_mapping(value):
            row = dict(value)
            row.setdefault("projection_source", "json")
            row.setdefault("projection_priority", 20)
            found.append(row)
        elif parent_key and isinstance(value.get("ok"), bool):
            # Some composite owner reports intentionally keep their child
            # reports under a named section rather than repeating a case id.
            # The section itself is an observed aggregate result; its raw
            # payload remains linked by fingerprint and is never treated as a
            # leaf contract by the strict verifier.
            found.append({
                "name": parent_key,
                "ok": value.get("ok"),
                "status": value.get("status", "pass" if value.get("ok") else "fail"),
                "finding_codes": value.get("finding_codes", value.get("findings", ())),
                "projection_source": "json",
                "projection_priority": 20,
            })
        for key, child in value.items():
            if isinstance(child, (Mapping, list, tuple)):
                _collect_json_cases(child, found, parent_key=str(key))
            elif parent_key in {"known_bad", "known_bad_proofs"} and isinstance(child, str):
                found.append({
                    "name": f"{parent_key}:{key}",
                    "status": child,
                    "ok": child.casefold() in {"blocked", "pass", "passed", "ok"},
                    "projection_source": "json",
                    "projection_priority": 20,
                })
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_json_cases(child, found, parent_key=parent_key)


def _structured_to_payload(value: Any) -> Any:
    """Serialize one captured native return without reducing it to a marker.

    Native owners historically print a human report and return only an exit
    code.  ``native_main`` now captures the structured object at the same call
    site, but keeps the conversion deliberately small: a typed ``to_dict``
    method is authoritative, mappings/sequences are copied recursively, and
    other values are retained only as a scalar representation.  This helper
    never invokes a second producer or reconstructs an oracle from text.
    """

    # Access the typed projection directly.  Keeping this as a fixed protocol
    # lookup (rather than a caller-selected attribute name) is important for
    # the self-model: the runner may project only the four registered report
    # families and must not become a reflective case extractor.
    try:
        to_dict = value.to_dict
    except AttributeError:
        to_dict = None
    if callable(to_dict):
        try:
            return _structured_to_payload(to_dict())
        except (TypeError, ValueError, MemoryError, RecursionError):
            # A malformed or oversized optional projection must not make the
            # owner look like it produced a passing case.  Do not call repr()
            # here: dataclass reprs can recursively walk a full self-model and
            # exhaust the producer process before the immutable source
            # envelope is written.  The bounded structural summary remains
            # linked in that envelope for diagnosis.
            return _bounded_source_summary(value)
    if isinstance(value, Mapping):
        return {
            str(key): _structured_to_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_structured_to_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Unknown objects are kept as a bounded shape summary.  A raw repr is not
    # a stable evidence surface and can expand without limit for nested model
    # graphs.
    return _bounded_source_summary(value)


def _model_run_projection(
    run: Any,
    *,
    name: str,
    wrapper_ok: bool | None = None,
    case_kind: str = "",
    projection_priority: int = 40,
) -> dict[str, Any] | None:
    """Project one already-executed sequence run for an outer oracle.

    ``run_exact_sequence`` returns a rich ``ScenarioRun``.  The outer owner
    helper (``run_sequence``/``print_case``) is the source of the case name and
    expected oracle; the inner run is only the observed model evidence.  This
    keeps an expected violation as a passing *check* while retaining the
    model's actual violation status and names.
    """

    try:
        report = run.model_report
    except AttributeError:
        return None
    if not name:
        try:
            name = _valid_text(run.scenario.name)
        except AttributeError:
            name = ""
    if not name:
        return None
    try:
        report_ok = bool(report.ok)
    except AttributeError:
        report_ok = False
    try:
        violations = tuple(report.violations)
    except AttributeError:
        violations = ()
    finding_codes: list[str] = []
    for violation in violations:
        try:
            value = _valid_text(violation.invariant_name)
        except AttributeError:
            value = ""
        if not value:
            try:
                value = _valid_text(violation.name)
            except AttributeError:
                value = ""
        if value and value not in finding_codes:
            finding_codes.append(value)
    try:
        observed_status = _valid_text(run.observed_status).lower()
    except AttributeError:
        observed_status = "ok" if report_ok else "violation"
    if not observed_status:
        observed_status = "ok" if report_ok else "violation"
    try:
        traces = tuple(run.traces)
    except AttributeError:
        traces = ()
    trace_labels: list[str] = []
    for trace in traces:
        try:
            steps = tuple(trace.steps)
        except AttributeError:
            steps = ()
        for step in steps:
            try:
                label = _valid_text(step.label)
            except AttributeError:
                label = ""
            if label and label not in trace_labels:
                trace_labels.append(label)
    result: dict[str, Any] = {
        "name": name,
        # The outer helper's bool is the declared oracle result.  If it is not
        # available, the inner model report is the only honest fallback.
        "ok": report_ok if wrapper_ok is None else bool(wrapper_ok),
        "observed_status": observed_status,
        "observed_finding_codes": finding_codes,
        "trace_labels": trace_labels,
        "case_kind": case_kind if case_kind in {"good", "bad", "boundary"} else (
            "bad" if not report_ok else "good"
        ),
        "projection_priority": projection_priority,
    }
    return result


def _captured_call_cases(
    call: _CapturedCall,
    *,
    owner_id: str,
) -> list[dict[str, Any]]:
    """Adapt the small set of explicit owner callback return shapes."""

    owner = owner_id.removeprefix("model:")
    name = call.function_name
    result = call.result
    rows: list[dict[str, Any]] = []

    # Preserve the richer typed object before serializing it through the
    # generic JSON collector.  In particular ScenarioRun keeps
    # observed_violation_names on its nested object; flattening first would
    # lose the model finding codes while retaining only the wrapper ``ok``.
    if any(
        hasattr(result, attribute)
        for attribute in ("results", "case_results", "cases")
    ):
        rows = _captured_structured_cases((result,), owner_id=owner_id)
        for row in rows:
            row.setdefault("projection_source", "structured")
            row.setdefault("projection_priority", 50)
        return rows

    # The two rollout-review owners intentionally expose tuple rows.  The
    # tuple shape itself is fixed by their model contract: (name, matched,
    # finding_codes).  Kind/status/dimensions are supplied later by the exact
    # checked-in mapping registry; no name heuristic is used here.
    if isinstance(result, (list, tuple)) and result and all(
        isinstance(item, (list, tuple)) and len(item) == 3 for item in result
    ):
        for item in result:
            case_name = _valid_text(item[0])
            if not case_name or not isinstance(item[1], bool):
                continue
            codes = item[2]
            if isinstance(codes, str):
                codes = (codes,)
            if not isinstance(codes, Sequence) or isinstance(codes, (str, bytes)):
                continue
            normalized_codes = [
                value for value in (_valid_text(code) for code in codes) if value
            ]
            rows.append(
                {
                    "name": case_name,
                    "ok": bool(item[1]),
                    "status": "pass" if item[1] else "fail",
                    # Tuple-based reviewers return the wrapper's oracle match
                    # plus the underlying report finding codes.  The wrapper
                    # bool is therefore not the model status: a matched bad
                    # case is an observed violation, while a matched good
                    # case has no violation codes.  Preserve both layers so a
                    # bad case cannot be flattened into an apparently normal
                    # ``pass`` observation.
                    "observed_status": "violation" if normalized_codes else "ok",
                    "finding_codes": normalized_codes,
                    "projection_priority": 38,
                    "projection_source": "structured",
                }
            )
        return rows

    if name == "review_primary_path_authority" and call.args:
        plan_id = _valid_text(getattr(call.args[0], "plan_id", ""))
        selector = _PRIMARY_PATH_PLAN_CASES.get(plan_id)
        if selector is not None and hasattr(result, "ok"):
            case_name, expected_ok = selector
            observed_ok = bool(getattr(result, "ok", False))
            findings = []
            for finding in tuple(getattr(result, "findings", ()) or ()):
                code = _valid_text(getattr(finding, "code", ""))
                if code and code not in findings:
                    findings.append(code)
            rows.append(
                {
                    "name": case_name,
                    # The owner checks intentionally expect every broken plan
                    # to be rejected.  ``ok`` is therefore the assertion
                    # result, while ``observed_status`` retains the model's
                    # actual authority decision.
                    "ok": observed_ok is expected_ok,
                    "status": "pass" if observed_ok is expected_ok else "fail",
                    "observed_status": "ok" if observed_ok else "violation",
                    "finding_codes": findings,
                    "case_kind": "good" if expected_ok else "bad",
                    "projection_priority": 46,
                    "projection_source": "structured",
                }
            )
        return rows

    # The outer UI flow helper owns the final expected-oracle bool.  Its nested
    # exact sequence report is the model observation and must be consumed once.
    if name in {"run_sequence", "run_rejected_release_sequence"}:
        case_name = _valid_text(call.args[0]) if call.args else ""
        expected_ok = call.kwargs.get("expect_ok")
        kind = "bad" if name == "run_rejected_release_sequence" else (
            "bad" if expected_ok is False else "good"
        )
        for child in call.nested:
            if isinstance(child, _CapturedCall) and child.function_name in {
                "run_exact_sequence",
                "run_exact_workflow_case",
            }:
                row = _model_run_projection(
                    child.result,
                    name=case_name,
                    wrapper_ok=bool(result) if isinstance(result, bool) else None,
                    case_kind=kind,
                    projection_priority=45,
                )
                if row is not None:
                    row.setdefault("projection_source", "structured")
                    if name == "run_rejected_release_sequence":
                        # The inner workflow is allowed to remain invariant
                        # clean while the release claim is rejected.  For
                        # this explicitly named bad boundary, the outer
                        # rejection is the observed violation consumed by
                        # the mapping; do not flatten it into a green model
                        # status merely because no lower invariant fired.
                        row["observed_status"] = "violation" if bool(result) else "ok"
                    rows.append(row)
                break
        return rows

    # Three formal owners expose one named positive workflow check together
    # with a finite suite of deliberately broken workflows.  The outer
    # ``run_workflow_suite`` boolean is an aggregate (and is false whenever a
    # broken workflow is correctly rejected), so it cannot stand in for the
    # positive leaf.  Project the exact positive sequence from its nested
    # typed result and leave the formal suite's bad leaves to the structured
    # report projector below.
    if name == "run_workflow_suite" and owner in {
        "maintenance_obligation_memory",
        "model_topology_hazard_review",
        "state_closure_gate",
    }:
        positive_names = {
            "maintenance_obligation_memory": "correct_maintenance_obligation_memory",
            "model_topology_hazard_review": "correct_topology_hazard_review",
            "state_closure_gate": "correct_state_closure_gate",
        }
        positive_name = positive_names[owner]
        for child in call.nested:
            if not isinstance(child, _CapturedCall) or child.function_name != "run_exact_sequence":
                continue
            exact = child.result
            report = getattr(exact, "model_report", None)
            observed_ok = bool(getattr(report, "ok", False))
            final_states = tuple(getattr(exact, "final_states", ()) or ())
            final_ok = len(final_states) == 1
            if final_ok:
                final_state = final_states[0]
                if owner == "maintenance_obligation_memory":
                    final_ok = getattr(final_state, "broad_claim", None) == "full_accepted"
                elif owner == "model_topology_hazard_review":
                    final_ok = getattr(final_state, "final_claim", None) == "full"
                else:
                    final_ok = getattr(final_state, "final_claim", None) == "full"
            exact_ok = observed_ok and final_ok
            rows.append(
                {
                    "name": positive_name,
                    "ok": exact_ok,
                    "status": "pass" if exact_ok else "fail",
                    "observed_status": "ok" if observed_ok else "violation",
                    "finding_codes": [
                        _valid_text(getattr(item, "code", ""))
                        for item in tuple(getattr(report, "findings", ()) or ())
                        if _valid_text(getattr(item, "code", ""))
                    ],
                    "case_kind": "good",
                    "projection_priority": 60,
                    "projection_source": "structured",
                }
            )
            break
        return rows

    # A few model-only owners invoke the exact sequence helper directly (no
    # named outer wrapper).  ``run_exact_workflow_case`` is slightly
    # different: its first argument is the stable native case name while the
    # nested ``run_exact_sequence`` carries only the model workflow name.
    # Keep that caller-provided name (and remove the one explicit blueprint
    # display prefix) so an aggregate's children cannot collapse into one
    # anonymous ScenarioRun row.
    if name in {"run_exact_sequence", "run_exact_workflow_case"}:
        case_name = ""
        wrapper_ok: bool | None = None
        case_kind = ""
        if name == "run_exact_workflow_case":
            case_name = _valid_text(call.args[0]) if call.args else ""
            if case_name.startswith("bounded blueprint path qualified: "):
                case_name = case_name.removeprefix("bounded blueprint path qualified: ").strip()
            if isinstance(result, bool):
                wrapper_ok = result
            case_kind = "good"
            # ``run_exact_workflow_case`` is the named native producer for a
            # bounded positive case.  Its contract intentionally returns the
            # final oracle as a plain bool, so there is no typed model report
            # for ``_model_run_projection`` to unwrap.  Preserve the exact
            # caller-provided case name as a native leaf instead of silently
            # dropping the evidence.  This is deliberately limited to this
            # explicit helper and does not infer cases from arbitrary bools.
            if case_name and isinstance(result, bool):
                rows.append(
                    {
                        "name": case_name,
                        "ok": result,
                        "status": "pass" if result else "fail",
                        "observed_status": "ok" if result else "violation",
                        "case_kind": "good",
                        "projection_priority": 44,
                        "projection_source": "structured",
                    }
                )
                return rows
        row = _model_run_projection(
            result,
            name=case_name,
            wrapper_ok=wrapper_ok,
            case_kind=case_kind,
            projection_priority=44,
        )
        if row is not None:
            row.setdefault("projection_source", "structured")
            rows.append(row)
        return rows

    # User-facing diagrams use print_case(name, run, expected_ok) as the named
    # oracle while run_case itself has no name.  The report is already present
    # in the call arguments and is never re-executed.
    if name == "print_case" and call.args:
        case_name = _valid_text(call.args[0])
        run = call.args[1] if len(call.args) > 1 else None
        expected_ok = call.args[2] if len(call.args) > 2 else None
        observed_ok = bool(
            run.model_report.ok
            if run is not None and hasattr(run, "model_report")
            else False
        )
        # ``print_case`` is an assertion helper rather than the model report
        # itself: a deliberately broken diagram is a passing *check* when
        # ``expected_ok`` is False.  Preserve the model violation status but
        # project the outer oracle match into ``ok`` so grouped bad leaves and
        # their finite boundary can close without treating rejection as a
        # failed producer.
        oracle_ok = (
            observed_ok is bool(expected_ok)
            if isinstance(expected_ok, bool)
            else observed_ok
        )
        row = _model_run_projection(
            run,
            name=case_name,
            wrapper_ok=oracle_ok,
            case_kind="good" if expected_ok is True else "bad" if expected_ok is False else "",
            projection_priority=45,
        )
        if row is not None:
            row.setdefault("projection_source", "structured")
            rows.append(row)
        return rows

    # AI-entry and the two UI hardening owners return either a bool or a typed
    # per-case dictionary.  The function's first argument is its exact case
    # name; any richer fields are retained as raw observed payload.
    if name == "run_case":
        if isinstance(result, Mapping):
            case_name = _valid_text(result.get("case") or result.get("name"))
            if case_name:
                row = dict(result)
                row["name"] = case_name
                row["ok"] = bool(result.get("ok"))
                row["projection_priority"] = 42
                row["projection_source"] = "structured"
                rows.append(row)
                return rows
        case_name = _valid_text(call.args[0]) if call.args else ""
        if case_name and isinstance(result, bool):
            rows.append(
                {
                    "name": case_name,
                    "ok": result,
                    "status": "pass" if result else "fail",
                    "observed_status": "ok" if result else "violation",
                    "projection_priority": 42,
                    "projection_source": "structured",
                }
            )
        return rows

    # A custom owner returning a mapping with a concrete case/result section
    # is projected through the same exact JSON case collector.  Aggregate
    # wrapper metadata remains raw and cannot satisfy a leaf binding by itself.
    payload = _structured_to_payload(result)
    if isinstance(payload, (Mapping, list, tuple)):
        _collect_json_cases(payload, rows)
        for row in rows:
            row.setdefault("projection_priority", 35)
            row.setdefault("projection_source", "structured")
    return rows


def _captured_structured_cases(
    captured: Sequence[Any],
    *,
    owner_id: str = "",
) -> list[dict[str, Any]]:
    """Project captured typed reports into explicit native case dictionaries.

    The projectors intentionally recognise the four existing report families.
    An aggregate report is retained as metadata, while only its concrete
    ``results``/``case_results``/``cases`` members become executable leaves.
    Unknown return shapes are not guessed into cases.
    """

    projected: list[dict[str, Any]] = []
    for report in captured:
        if isinstance(report, _CapturedCall):
            # A nested exact sequence is evidence for its named outer oracle;
            # projecting it as an anonymous extra leaf would create a foreign
            # case and could mask the outer expected-violation verdict.
            if report.parent_function:
                if report.function_name not in {"run_exact_sequence", "run_exact_workflow_case"}:
                    rows = _captured_call_cases(report, owner_id=owner_id)
                    projected.extend(rows)
                continue
            rows = _captured_call_cases(report, owner_id=owner_id)
            projected.extend(rows)
            # The four canonical typed report producers are captured as call
            # envelopes too.  Their report object is projected by the exact
            # attribute branches below; do not reduce it to repr merely
            # because it has no generic ``to_dict`` method.
            if not rows and report.result is not None:
                projected.extend(
                    _captured_structured_cases((report.result,), owner_id=owner_id)
                )
            continue
        # ScenarioReviewReport / compatible typed report.
        try:
            results = report.results
        except AttributeError:
            results = None
        if isinstance(results, (list, tuple)):
            for item in results:
                try:
                    name = _valid_text(item.scenario_name)
                except AttributeError:
                    name = ""
                if not name:
                    continue
                row = _structured_to_payload(item)
                if not isinstance(row, Mapping):
                    continue
                result = dict(row)
                try:
                    run = item.scenario_run
                except AttributeError:
                    run = None
                if run is not None:
                    result["scenario_run"] = _structured_to_payload(run)
                    try:
                        observed_status = run.observed_status
                    except AttributeError:
                        observed_status = ""
                    result["observed_status"] = _valid_text(observed_status)
                    try:
                        violation_names = run.observed_violation_names
                    except AttributeError:
                        violation_names = ()
                    result["observed_violation_names"] = list(violation_names or ())
                result["scenario_name"] = name
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                # A scenario's wrapper ``ok`` is the oracle verdict, so an
                # expected violation is a passing *check* whose model leaf is
                # nevertheless a bad-case observation.  Classify from the
                # observed model status first and only then fall back to the
                # wrapper status/ok bit.
                observed = _valid_text(result.get("observed_status")).lower()
                wrapper_status = _valid_text(result.get("status")).lower()
                if observed in {"violation", "rejected", "fail", "failed", "blocked"} or "violation" in wrapper_status:
                    result.setdefault("case_kind", "bad")
                else:
                    try:
                        item_ok = item.ok
                    except AttributeError:
                        item_ok = False
                    result.setdefault("case_kind", "good" if bool(item_ok) else "bad")
                projected.append(result)
            # A formal report also exposes ``results`` only for custom
            # wrappers; continue so its explicit case_results branch below can
            # add the richer expected/observed fields.
        try:
            case_results = report.case_results
        except AttributeError:
            case_results = None
        if isinstance(case_results, (list, tuple)):
            for item in case_results:
                try:
                    name = _valid_text(item.name)
                except AttributeError:
                    name = ""
                if not name:
                    continue
                result = _structured_to_payload(item)
                if not isinstance(result, Mapping):
                    continue
                result = dict(result)
                try:
                    expected_ok = item.expected_ok
                except AttributeError:
                    expected_ok = None
                try:
                    observed_ok = item.observed_ok
                except AttributeError:
                    observed_ok = None
                if isinstance(expected_ok, bool):
                    result["expected_ok"] = expected_ok
                    result["case_kind"] = "good" if expected_ok else "bad"
                if isinstance(observed_ok, bool):
                    result["observed_ok"] = observed_ok
                    result["observed_status"] = "ok" if observed_ok else "violation"
                result["name"] = name
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                try:
                    item_ok = item.ok
                except AttributeError:
                    item_ok = False
                result.setdefault("ok", bool(item_ok))
                projected.append(result)
        try:
            cases = report.cases
        except AttributeError:
            cases = None
        if isinstance(cases, (list, tuple)):
            for item in cases:
                try:
                    family = _valid_text(item.family_id)
                except AttributeError:
                    family = ""
                try:
                    case = _valid_text(item.case_id)
                except AttributeError:
                    case = ""
                if not family or not case:
                    continue
                result = _structured_to_payload(item)
                if not isinstance(result, Mapping):
                    continue
                result = dict(result)
                result["family_id"] = family
                result["case_id"] = case
                result["name"] = case
                result["variant"] = case
                result["case_kind"] = (
                    "bad" if case == "bad" else
                    "boundary" if case in {"missing-semantics", "truncated"}
                    else "good"
                )
                try:
                    item_report = item.report
                except AttributeError:
                    item_report = None
                try:
                    item_status = item_report.status
                except AttributeError:
                    item_status = ""
                result["observed_status"] = _valid_text(item_status) or _valid_text(
                    result.get("observed_status")
                )
                try:
                    item_ok = item.ok
                except AttributeError:
                    item_ok = False
                result["ok"] = bool(item_ok)
                result.setdefault("projection_source", "structured")
                result.setdefault("projection_priority", 50)
                projected.append(result)
    return projected


_FORMAL_LINE = re.compile(
    # Both current formal runners are intentionally supported: some print a
    # Markdown-style ``- name: ...`` row while others print the same exact
    # row without the bullet.  The name/verdict fields are unchanged; the
    # optional prefix is not a fuzzy case selector.
    r"^(?:-\s+)?(?P<name>[^:]+):\s+observed=(?P<observed>OK|VIOLATION)\s+"
    # Formal producers may append bounded receipt annotations after the
    # verdict (for example ``exact=yes``).  The verdict fields remain the
    # authoritative parser contract; rejecting a valid line merely because
    # a producer added that explicit trailing annotation silently drops the
    # positive native leaf and can make its boundary appear incomplete.
    r"expected=(?P<expected>OK|VIOLATION)\s+match=(?P<match>yes|no)\s+formal=(?P<formal>\w+)(?:\s+.*)?$",
    re.IGNORECASE,
)
_SCENARIO_NAME = re.compile(r"^Scenario:\s*(?P<name>.+?)\s*$")
_SCENARIO_STATUS = re.compile(r"^Status:\s*(?P<status>\S+)")
_STATUS_LINE = re.compile(r"^status:(?P<name>[^:]+):\s*(?P<status>\S+)", re.IGNORECASE)
# Formal owners that still use ``run_exact_sequence`` print a compact positive
# receipt instead of a ``FormalWorkflowCaseResult`` row.  This line is an
# explicit producer contract (the name and exact marker are fixed), not a
# fuzzy interpretation of arbitrary prose.
_EXACT_PASS_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.:/-][A-Za-z0-9_.:/ -]*):\s*exact\s+model\s+pass\s*$",
    re.IGNORECASE,
)
# Keep the lowercase aggregate summary distinct from ``Status: ...`` inside a
# Scenario block.  The latter must be consumed by ``_SCENARIO_STATUS`` while a
# scenario is pending; treating both spellings as the same line silently left
# every good scenario at its default ``fail`` status.
_SIMPLE_STATUS = re.compile(r"^status:\s*(?P<status>PASS|PASSED|FAIL|FAILED|OK|BLOCKED)\s*$")
_NAMED_STATUS = re.compile(
    r"^(?:-\s*)?(?P<name>[A-Za-z0-9_.:/-][A-Za-z0-9_.:/ -]*?):\s*"
    r"(?P<status>PASS|PASSED|FAIL|FAILED|OK|VIOLATION|BLOCKED)\b",
    re.IGNORECASE,
)


def _collect_text_cases(
    stdout: str,
    *,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """Project the bounded legacy transcript grammar.

    The public helper historically returned only the case fields.  Keep that
    small API stable for callers that use it as a parser, while the native
    execution path opts into provenance metadata so the strict writer can
    prefer a typed report over a duplicate transcript line.  Metadata is
    therefore an execution-envelope concern, not part of the legacy parser's
    semantic result.
    """
    found: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for line in stdout.splitlines():
        match = _SIMPLE_STATUS.match(line.strip())
        if match:
            status = match.group("status").strip().lower()
            found.append({
                "name": "status",
                "status": status,
                "ok": status in {"pass", "passed", "ok"},
                "projection_source": "text",
                "projection_priority": 5,
            })
            continue
        match = _EXACT_PASS_LINE.match(line.strip())
        if match:
            found.append(
                {
                    "name": match.group("name").strip(),
                    "status": "pass",
                    "observed_status": "ok",
                    "ok": True,
                    "case_kind": "good",
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _SCENARIO_NAME.match(line.strip())
        if match:
            pending = {
                "scenario_name": match.group("name"),
                "ok": False,
                "status": "fail",
                "projection_source": "text",
                "projection_priority": 10,
            }
            found.append(pending)
            continue
        if pending is not None:
            observed = re.match(r"^Observed:\s*(?P<status>[^;]+)", line.strip())
            if observed:
                pending["observed_status"] = observed.group("status").strip().lower()
                continue
            match = _SCENARIO_STATUS.match(line.strip())
            if match:
                status = match.group("status").strip().lower()
                pending["status"] = status
                pending["ok"] = status in {"pass", "ok", "expected_violation_observed"}
                continue
            violation_names = re.match(
                r"^-?\s*violation_names=\s*(?P<codes>.+?)\s*$",
                line.strip(),
                re.IGNORECASE,
            )
            if violation_names:
                codes = tuple(
                    item.strip()
                    for item in violation_names.group("codes").split(",")
                    if item.strip()
                )
                if codes:
                    pending["finding_codes"] = list(codes)
                continue
        match = _FORMAL_LINE.match(line.strip())
        if match:
            found.append(
                {
                    "name": match.group("name").strip(),
                    "observed_status": match.group("observed").lower(),
                    "expected_ok": match.group("expected").upper() == "OK",
                    "match": match.group("match"),
                    "ok": match.group("match").lower() == "yes",
                    "formal": match.group("formal"),
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _STATUS_LINE.match(line.strip())
        if match:
            status = match.group("status").strip().lower()
            found.append(
                {
                    "name": match.group("name").strip(),
                    "status": status,
                    "ok": status in {"pass", "ok", "passed"},
                    "projection_source": "text",
                    "projection_priority": 15,
                }
            )
            continue
        match = _NAMED_STATUS.match(line.strip())
        if match:
            name = match.group("name").strip()
            # Avoid turning aggregate summary labels into duplicate cases.
            if name.casefold() not in {
                "status",
                "result",
                "decision",
                "outcome",
                "observed",
                "expected",
                "evidence",
                "counterexample",
            }:
                status = match.group("status").strip().lower()
                row = {
                    "name": name,
                    "status": status,
                    "ok": status in {"pass", "passed", "ok"},
                    "projection_source": "text",
                    "projection_priority": 15,
                }
                # Several legacy custom owners display their typed oracle
                # codes on the same line (``name: PASS codes=[...]``).  Keep
                # that finite diagnostic payload; dropping it would make a
                # known-bad model row indistinguishable from a good row.
                codes_match = re.search(r"\bcodes\s*=\s*\[(?P<codes>[^\]]*)\]", line, re.IGNORECASE)
                if codes_match:
                    encoded = codes_match.group("codes")
                    codes = tuple(
                        item
                        for item in re.findall(r"['\"]([^'\"]+)['\"]", encoded)
                        if item.strip()
                    )
                    if codes:
                        row["finding_codes"] = list(dict.fromkeys(codes))
                found.append(row)
    if not include_metadata:
        for row in found:
            row.pop("projection_source", None)
            row.pop("projection_priority", None)
    return found


_NON_CASE_JSON_NAMES = frozenset(
    {
        # These are FlowGuard envelopes/heads, not producer-owned case
        # sources.  In particular, an older native result must never be
        # re-projected as a case for a later invocation.
        "native-case-results.json",
        "native-source.json",
        "evidence-run.json",
        "CURRENT.json",
    }
)


def _json_file_state(output_dir: Path) -> dict[Path, tuple[int, int, int]]:
    """Return the invocation-boundary state of regular JSON files.

    The native bridge historically walked the complete output tree after the
    owner returned.  That made a previous invocation's case envelope look
    indistinguishable from a file emitted by the current owner.  A small
    stat-based snapshot is sufficient here: files that are created or
    replaced during the owner call are explicitly admitted below, while
    untouched history is not an input to the current case projection.
    """

    state: dict[Path, tuple[int, int, int]] = {}
    if not output_dir.is_dir():
        return state
    for path in sorted(output_dir.rglob("*.json")):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        state[path.resolve()] = (
            int(stat.st_size),
            int(getattr(stat, "st_mtime_ns", 0)),
            int(getattr(stat, "st_ctime_ns", 0)),
        )
    return state


def _load_existing_json(
    output_dir: Path,
    *,
    paths: Sequence[Path] = (),
) -> list[dict[str, Any]]:
    """Load only JSON files explicitly changed by this owner invocation.

    ``paths`` is deliberately required at the call site (an empty default
    yields no rows), so this helper cannot silently fall back to a historical
    recursive scan.  The caller owns the invocation-boundary snapshot and
    passes only newly-created or replaced files.
    """

    found: list[dict[str, Any]] = []
    if not paths or not output_dir.is_dir():
        return found
    root = output_dir.resolve()
    candidates: set[Path] = set()
    for candidate in paths:
        try:
            path = Path(candidate).resolve()
        except (OSError, RuntimeError, TypeError):
            continue
        if root not in path.parents or path.name in _NON_CASE_JSON_NAMES:
            continue
        candidates.add(path)
    for path in sorted(candidates):
        try:
            if path.is_symlink() or not path.is_file():
                continue
        except OSError:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        _collect_json_cases(payload, found)
    return found


def _deduplicate_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    owner_id: str = "",
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for raw in cases:
        identifier = _case_id(raw)
        # Benchmark leaves are keyed by the ordered pair (family_id, case_id)
        # on the wire.  Deduplicating on the short variant alone would retain
        # only the first family and silently shrink the finite denominator.
        family = _valid_text(raw.get("family_id")) if isinstance(raw, Mapping) else ""
        if family and identifier:
            identifier = f"benchmark:{family}:{identifier}"
        if (
            not identifier
            or identifier.casefold() in _SUMMARY_CASE_NAMES
        ):
            continue
        candidate = dict(raw)
        position = positions.get(identifier)
        if position is None:
            positions[identifier] = len(result)
            result.append(candidate)
            continue
        # Prefer the outer, named oracle over an inner report projection and
        # prefer structured data over legacy transcript parsing.  Equal
        # priority keeps first-observed order deterministic.
        old = result[position]
        old_priority = int(old.get("projection_priority", 0) or 0)
        new_priority = int(candidate.get("projection_priority", 0) or 0)
        if new_priority > old_priority:
            result[position] = candidate
    return result


def _qualified_case_id(owner_id: str, raw: Mapping[str, Any]) -> str:
    """Apply the frozen native leaf namespace for one owner.

    This is an explicit owner-class dispatch, not a best-effort alias.  A
    benchmark row must carry both family and case identities; otherwise it is
    left unqualified and the strict binding verifier reports it as foreign.
    """

    owner = _valid_text(owner_id).removeprefix("model:")
    raw_id = _case_id(raw)
    if not owner or not raw_id:
        return ""
    if raw_id.startswith(("native-scenario:", "case:", "benchmark:")):
        return raw_id
    if owner in _SCENARIO_OWNERS:
        return f"native-scenario:{owner}:{raw_id}"
    if owner == _BENCHMARK_OWNER:
        family = _valid_text(raw.get("family_id"))
        case = _valid_text(raw.get("case_id")) or raw_id
        if family and case:
            return f"benchmark:{family}:{case}"
        return raw_id
    return f"case:{owner}:{raw_id}"


def _env_fingerprint(name: str, fallback: Any) -> str:
    value = _valid_text(os.environ.get(name))
    if value.startswith("sha256:") and len(value) == 71:
        return value
    return fingerprint_payload(fallback)


def _case_kind(raw: Mapping[str, Any], qualified_case_id: str) -> str:
    """Return an explicit leaf kind when the producer supplied one."""

    declared = _valid_text(raw.get("case_kind")).lower()
    if declared in {"good", "boundary", "bad"}:
        return declared
    expected_ok = raw.get("expected_ok")
    if isinstance(expected_ok, bool):
        return "good" if expected_ok else "bad"
    variant = _valid_text(raw.get("variant")).lower()
    if variant in {"missing-semantics", "truncated"}:
        return "boundary"
    if variant == "bad":
        return "bad"
    status = _status(raw, ok=_observed_ok(raw)).casefold()
    if "boundary" in qualified_case_id.casefold():
        return "boundary"
    if any(token in status for token in ("violation", "reject", "fail", "error")):
        return "bad"
    return "good"


def _expected_observed_status(raw: Mapping[str, Any], *, fallback: str) -> str:
    """Prefer a producer's observed/model status over wrapper outcome text."""

    for key in ("observed_status", "model_observed_status", "observed"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    scenario_run = raw.get("scenario_run")
    if isinstance(scenario_run, Mapping):
        value = scenario_run.get("observed_status")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return fallback


def _runtime_case_mapping(
    owner_id: str,
) -> tuple[NativeCaseMappingRegistry | None, dict[str, Any], str]:
    """Load the one explicit project mapping, when a project root supplied it.

    Native runners are also used as small standalone tests, so the registry is
    optional for those callers.  Once ``FLOWGUARD_PROJECT_ROOT`` is present,
    however, a missing, stale, or malformed registry is a hard producer input
    error.  No output-directory parent walk or name-based fallback is allowed.
    The returned index is keyed by the exact ``(owner, native_case_id)`` pair
    and contains the binding's declared kind/dimensions/oracle expectations.
    """

    root_text = _valid_text(os.environ.get("FLOWGUARD_PROJECT_ROOT"))
    if not root_text:
        return None, {}, ""
    root = Path(root_text).expanduser().resolve()
    try:
        registry = load_native_case_mapping(root)
        registry.assert_current_manifest(root)
    except (NativeCaseMappingError, OSError, UnicodeError, ValueError) as exc:
        return None, {}, f"native_case_mapping_invalid:{exc}"
    index: dict[str, Any] = {}
    owner = _valid_text(owner_id) or "model:unknown"
    for binding in registry.bindings_by_owner.get(owner, ()):
        for native_id in binding.native_case_ids:
            key = f"{owner}\x00{native_id}"
            # Reuse is legal when the registry proved the projections have an
            # identical observable contract.  Keep one deterministic binding
            # for producer row shaping; the downstream binding verifier still
            # evaluates every blueprint obligation against that one receipt.
            if key in index:
                previous = index[key]
                signature = (
                    previous.expected_status,
                    previous.expected_observed_status or previous.expected_status,
                    previous.evidence_scope,
                    previous.covered_dimensions,
                    previous.protected_failure_ids,
                    previous.expected_finding_codes,
                )
                current = binding
                current_signature = (
                    current.expected_status,
                    current.expected_observed_status or current.expected_status,
                    current.evidence_scope,
                    current.covered_dimensions,
                    current.protected_failure_ids,
                    current.expected_finding_codes,
                )
                if signature != current_signature:
                    return None, {}, f"native_case_mapping_incompatible_reuse:{owner}:{native_id}"
                continue
            index[key] = binding
    return registry, index, ""


def _required_environment_fingerprint(name: str) -> str:
    """Read one producer identity without manufacturing a fallback hash.

    The model-regression launcher supplies all six values from its frozen
    owner observation.  A strict producer invoked outside that launcher must
    fail closed instead of turning the current process, stdout, or a guessed
    model name into an input identity.
    """

    value = _valid_text(os.environ.get(name))
    if not value.startswith("sha256:") or len(value) != 71:
        raise NativeCaseProtocolError(
            f"strict native producer requires canonical {name}"
        )
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise NativeCaseProtocolError(
            f"strict native producer requires canonical {name}"
        ) from exc
    return value


def _scenario_result_status(result: Any) -> tuple[str, bool]:
    """Convert the report's oracle status to native outcome semantics.

    ``expected_violation_observed`` is a passing *oracle* result: the model
    intentionally observed a violation.  The native row therefore has
    ``outcome=pass`` while retaining ``observed_status=violation``.  Any
    unresolved or mismatched report status is blocked and cannot be promoted
    by an exit code or a transcript.
    """

    status = _valid_text(getattr(result, "status", "")).lower()
    if status in {"pass", "expected_violation_observed"}:
        return "pass", True
    return "blocked", False


def _scenario_trace_labels(result: Any) -> tuple[str, ...]:
    run = getattr(result, "scenario_run", None)
    traces = getattr(run, "traces", ()) if run is not None else ()
    labels: list[str] = []
    for trace in traces or ():
        for label in getattr(trace, "labels", ()) or ():
            text = _valid_text(label)
            if text and text not in labels:
                labels.append(text)
    return tuple(labels)


def _scenario_observed_findings(result: Any) -> tuple[str, ...]:
    run = getattr(result, "scenario_run", None)
    values = getattr(run, "observed_violation_names", ()) if run is not None else ()
    findings: list[str] = []
    for value in values or ():
        text = _valid_text(value)
        if text and text not in findings:
            findings.append(text)
    return tuple(findings)


def native_results_from_scenario_report(
    owner_id: str,
    report: Any,
) -> tuple[NativeModelCaseResult, ...]:
    """Convert one real ``ScenarioReviewReport`` to the strict native tuple.

    The conversion is intentionally producer-side and one-shot.  It requires
    the current checked-in mapping, uses the exact scenario names as native
    IDs, preserves the model's observed status/finding/trace data, and emits
    the boundary aggregate only after every declared child was returned by
    this same report.  No stdout, global callback, directory scan, or count
    inference participates in the result.
    """

    owner = _valid_text(owner_id)
    if not owner.startswith("model:"):
        owner = "model:" + owner
    owner_key = owner.removeprefix("model:")
    if owner_key not in _STRICT_NATIVE_OWNER_IDS:
        raise NativeCaseProtocolError(
            f"scenario report producer is not registered for {owner}"
        )
    report_rows = getattr(report, "results", None)
    if not isinstance(report_rows, tuple):
        raise NativeCaseProtocolError(
            "strict scenario producer must return one ScenarioReviewReport tuple"
        )
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    if mapping is None or mapping_error:
        raise NativeCaseProtocolError(
            mapping_error or "strict native producer requires current native mapping"
        )
    input_fp = _required_environment_fingerprint("FLOWGUARD_INPUT_FINGERPRINT")
    model_fp = _required_environment_fingerprint("FLOWGUARD_MODEL_FINGERPRINT")
    code_fp = _required_environment_fingerprint("FLOWGUARD_CODE_FINGERPRINT")
    test_fp = _required_environment_fingerprint("FLOWGUARD_TEST_FINGERPRINT")
    tool_fp = _required_environment_fingerprint("FLOWGUARD_TOOLCHAIN_FINGERPRINT")
    env_fp = _required_environment_fingerprint("FLOWGUARD_ENVIRONMENT_FINGERPRINT")
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", "")).resolve()
    if not str(output_dir) or str(output_dir) == str(Path.cwd().resolve()):
        raise NativeCaseProtocolError(
            "strict native producer requires an explicit FLOWGUARD_OUTPUT_DIR"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "native-source.json"

    # The report itself is the raw immutable producer artifact.  It is written
    # before rows are constructed so every row can bind to its exact bytes.
    report_payload = _structured_to_payload(report)
    source_payload = {
        "schema_version": NATIVE_CASE_RESULT_SCHEMA,
        "owner_id": owner,
        "producer": "scenario_review_report",
        "mapping_fingerprint": mapping.mapping_fingerprint,
        "report": report_payload,
    }
    source_bytes = _json_bytes(source_payload) + b"\n"
    source_path.write_bytes(source_bytes)
    source_fp = _sha256_bytes(source_bytes)

    expected_leaf_ids = {
        key.split("\x00", 1)[1]
        for key, binding in mapping_index.items()
        if key.startswith(owner + "\x00") and binding.case_kind != "boundary"
    }
    rows_by_id: dict[str, NativeModelCaseResult] = {}
    for report_row in report_rows:
        scenario_name = _valid_text(getattr(report_row, "scenario_name", ""))
        if not scenario_name:
            raise NativeCaseProtocolError("scenario report has an unnamed result")
        native_id = f"native-scenario:{owner_key}:{scenario_name}"
        if native_id in rows_by_id:
            raise NativeCaseProtocolError(f"duplicate strict native scenario: {native_id}")
        binding = mapping_index.get(f"{owner}\x00{native_id}")
        if binding is None or binding.case_kind == "boundary":
            raise NativeCaseProtocolError(f"unmapped strict native scenario: {native_id}")
        run = getattr(report_row, "scenario_run", None)
        observed_status = _valid_text(getattr(run, "observed_status", ""))
        if not observed_status:
            raise NativeCaseProtocolError(f"scenario has no observed status: {native_id}")
        outcome, oracle_ok = _scenario_result_status(report_row)
        findings = _scenario_observed_findings(report_row)
        trace_labels = _scenario_trace_labels(report_row)
        dimensions = tuple(binding.covered_dimensions)
        oracle_fp = fingerprint_payload(
            {
                "scenario_name": scenario_name,
                "expected_status": binding.expected_status,
                "expected_observed_status": binding.expected_observed_status,
                "expected_finding_codes": list(binding.expected_finding_codes),
                "observed_status": observed_status,
                "observed_finding_codes": list(findings),
                "trace_labels": list(trace_labels),
            }
        )
        rows_by_id[native_id] = NativeModelCaseResult(
            owner_id=owner,
            source_case_id=native_id,
            outcome=outcome,
            observed_status=observed_status,
            observed_finding_codes=findings,
            executed_dimensions=dimensions,
            oracle_results=tuple(
                {
                    "dimension": dimension,
                    "oracle_member_id": f"{owner}:{native_id}:{dimension}",
                    "status": observed_status,
                    "ok": oracle_ok,
                    "finding_codes": list(findings),
                    "observed": {"trace_labels": list(trace_labels)},
                }
                for dimension in dimensions
            ),
            result_artifact_fingerprint=source_fp,
            input_fingerprint=input_fp,
            model_fingerprint=model_fp,
            code_fingerprint=code_fp,
            test_fingerprint=test_fp,
            oracle_fingerprint=oracle_fp,
            toolchain_fingerprint=tool_fp,
            environment_fingerprint=env_fp,
            raw_artifact_path="native-source.json",
        )
    actual_leaf_ids = set(rows_by_id)
    if actual_leaf_ids != expected_leaf_ids:
        missing = sorted(expected_leaf_ids - actual_leaf_ids)
        extra = sorted(actual_leaf_ids - expected_leaf_ids)
        raise NativeCaseProtocolError(
            f"strict native denominator mismatch: missing={missing}, extra={extra}"
        )

    boundary_bindings = {
        binding.native_case_ids[0]: binding
        for key, binding in mapping_index.items()
        if key.startswith(owner + "\x00") and binding.case_kind == "boundary"
    }
    for boundary_id, binding in sorted(boundary_bindings.items()):
        child_ids = tuple(binding.required_child_case_ids)
        missing = tuple(child for child in child_ids if child not in rows_by_id)
        failed = tuple(
            child
            for child in child_ids
            if child in rows_by_id and rows_by_id[child].outcome != "pass"
        )
        boundary_ok = bool(child_ids) and not missing and not failed
        status = "ok" if boundary_ok else "blocked"
        findings = tuple(
            item
            for item in (
                "boundary_child_result_missing" if missing else "",
                "boundary_child_result_failed" if failed else "",
            )
            if item
        )
        rows_by_id[boundary_id] = NativeModelCaseResult(
            owner_id=owner,
            source_case_id=boundary_id,
            outcome="pass" if boundary_ok else "blocked",
            observed_status=status,
            observed_finding_codes=findings,
            executed_dimensions=tuple(binding.covered_dimensions),
            oracle_results=tuple(
                {
                    "dimension": dimension,
                    "oracle_member_id": f"{owner}:{boundary_id}:{dimension}",
                    "status": status,
                    "ok": boundary_ok,
                    "finding_codes": list(findings),
                    "observed": {"child_case_ids": list(child_ids)},
                }
                for dimension in binding.covered_dimensions
            ),
            result_artifact_fingerprint=source_fp,
            input_fingerprint=input_fp,
            model_fingerprint=model_fp,
            code_fingerprint=code_fp,
            test_fingerprint=test_fp,
            oracle_fingerprint=fingerprint_payload(
                {"boundary": boundary_id, "children": list(child_ids), "status": status}
            ),
            toolchain_fingerprint=tool_fp,
            environment_fingerprint=env_fp,
            raw_artifact_path="native-source.json",
            child_case_ids=child_ids,
        )
    return tuple(rows_by_id[key] for key in sorted(rows_by_id))


def _write_strict_native_results(
    owner_id: str,
    results: tuple[NativeModelCaseResult, ...],
    output_dir: Path,
) -> Path:
    """Persist a typed producer tuple after exact mapping validation."""

    owner = _valid_text(owner_id)
    if not owner.startswith("model:"):
        owner = "model:" + owner
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    if mapping is None or mapping_error:
        raise NativeCaseProtocolError(
            mapping_error or "strict native result requires current native mapping"
        )
    if not results or any(not isinstance(row, NativeModelCaseResult) for row in results):
        raise NativeCaseProtocolError(
            "strict native producer must return tuple[NativeModelCaseResult, ...]"
        )
    keys = [(row.owner_id, row.source_case_id) for row in results]
    if len(keys) != len(set(keys)):
        raise NativeCaseProtocolError("strict native producer returned duplicate rows")
    if any(row.owner_id != owner for row in results):
        raise NativeCaseProtocolError("strict native producer returned a foreign owner")
    declared_keys = {
        (key.split("\x00", 1)[0], key.split("\x00", 1)[1])
        for key in mapping_index
    }
    actual_keys = set(keys)
    if actual_keys != declared_keys:
        missing = sorted(declared_keys - actual_keys)
        extra = sorted(actual_keys - declared_keys)
        raise NativeCaseProtocolError(
            f"strict native result mapping mismatch: missing={missing}, extra={extra}"
        )
    source_path = output_dir / "native-source.json"
    if source_path.is_symlink() or not source_path.is_file():
        raise NativeCaseProtocolError("strict native producer did not write native-source.json")
    source_fp = _sha256_bytes(source_path.read_bytes())
    for row in results:
        raw_path = Path(row.raw_artifact_path)
        if raw_path.is_absolute() or raw_path.parts != ("native-source.json",):
            raise NativeCaseProtocolError("strict native row raw artifact path is not current")
        if row.result_artifact_fingerprint != source_fp:
            raise NativeCaseProtocolError(
                f"strict native row artifact fingerprint mismatch: {row.source_case_id}"
            )
    target = output_dir / "native-case-results.json"
    target.write_bytes(
        _json_bytes(
            {
                "schema_version": NATIVE_CASE_RESULT_SCHEMA,
                "results": [row.to_dict() for row in results],
            }
        )
        + b"\n"
    )
    return target


def _write_results(
    owner_id: str,
    cases: Sequence[Mapping[str, Any]],
    stdout: str,
    exit_code: int,
    output_dir: Path,
    *,
    structured_reports: Sequence[Any] = (),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "native-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    owner = _valid_text(owner_id) or "model:unknown"
    base_input = _env_fingerprint("FLOWGUARD_INPUT_FINGERPRINT", {"owner": owner, "stdout": stdout})
    model_fp = _env_fingerprint("FLOWGUARD_MODEL_FINGERPRINT", {"owner": owner, "model": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    code_fp = _env_fingerprint("FLOWGUARD_CODE_FINGERPRINT", {"owner": owner, "code": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    test_fp = _env_fingerprint("FLOWGUARD_TEST_FINGERPRINT", {"owner": owner, "test": os.environ.get("FLOWGUARD_MODEL_ID", "")})
    tool_fp = _env_fingerprint("FLOWGUARD_TOOLCHAIN_FINGERPRINT", {"python": sys.version, "executable": sys.executable})
    env_fp = _env_fingerprint("FLOWGUARD_ENVIRONMENT_FINGERPRINT", {"platform": sys.platform, "cwd": str(Path.cwd())})
    stdout_fingerprint = _sha256_bytes(stdout.encode("utf-8"))
    mapping, mapping_index, mapping_error = _runtime_case_mapping(owner)
    diagnostic_case_ids = (
        frozenset(mapping.diagnostic_native_case_ids)
        if mapping is not None
        else frozenset()
    )

    # A path-quality consumer is allowed to use a producer's real executed
    # report graph, but only when the producer returned one explicit report
    # with named results and trace/final-state material.  The normal captured
    # call envelope is intentionally bounded; this separate, exact projection
    # preserves the graph needed by the downstream path-quality owner without
    # scanning stdout or inventing a report from case counts.
    report_payload: Mapping[str, Any] | None = None
    for captured in structured_reports:
        candidate = (
            captured.result
            if isinstance(captured, _CapturedCall)
            else captured
        )
        payload = _structured_to_payload(candidate)
        if not isinstance(payload, Mapping):
            continue
        report_rows = payload.get("results")
        if not isinstance(report_rows, list) or not report_rows:
            continue
        if not all(
            isinstance(row, Mapping)
            and isinstance(row.get("scenario_name"), str)
            and bool(row.get("scenario_name", "").strip())
            and isinstance(row.get("scenario_run"), Mapping)
            and isinstance(row["scenario_run"].get("traces"), list)
            and bool(row["scenario_run"].get("traces"))
            and isinstance(row["scenario_run"].get("final_states"), list)
            and bool(row["scenario_run"].get("final_states"))
            for row in report_rows
        ):
            continue
        report_payload = payload
        break
    normalized_cases: list[tuple[str, Mapping[str, Any]]] = []
    for raw in cases:
        qualified = _qualified_case_id(owner, raw)
        if not qualified:
            continue
        normalized_cases.append((qualified, raw))
    compact_cases: list[dict[str, Any]] = []
    for qualified, raw in normalized_cases:
        compact: dict[str, Any] = {}
        for key in (
            *_CASE_KEYS,
            *_STATUS_KEYS,
            *_OK_KEYS,
            "finding_codes",
            "observed_finding_codes",
            # Execution provenance is intentionally kept in the raw source
            # envelope.  It lets a reviewer see why a transcript duplicate
            # was not promoted to an authoritative leaf without making the
            # native result verifier depend on display text.
            "projection_source",
            "projection_priority",
        ):
            if key in raw and not isinstance(raw[key], (Mapping, list, tuple)):
                compact[key] = raw[key]
            elif key in raw and isinstance(raw[key], (list, tuple)):
                compact[key] = [item for item in raw[key] if isinstance(item, (str, int, float, bool))]
        compact["source_fingerprint"] = fingerprint_payload(raw)
        compact["qualified_case_id"] = qualified
        compact_cases.append(compact)
    unmapped_cases: list[dict[str, Any]] = []
    if mapping is not None:
        for qualified, raw in normalized_cases:
            if f"{owner}\x00{qualified}" in mapping_index:
                continue
            unmapped_cases.append(
                {
                    "qualified_case_id": qualified,
                    "source_fingerprint": fingerprint_payload(raw),
                    "disposition": (
                        "diagnostic"
                        if qualified in diagnostic_case_ids
                        else "supporting_native_observation"
                    ),
                }
            )
    # A boundary is a distinct finite aggregate receipt, not a copied good or
    # bad aggregate.  The mapping compiler freezes its exact child set.  Keep
    # the accounting visible in the raw source envelope and emit the boundary
    # result below only after all child rows have been projected from this one
    # producer invocation.  Older standalone fixture mappings may not carry a
    # boundary binding; those callers retain their historical behaviour.
    boundary_binding = None
    boundary_case_id = ""
    boundary_children: tuple[str, ...] = ()
    boundary_present_children: tuple[str, ...] = ()
    boundary_missing_children: tuple[str, ...] = ()
    if mapping is not None and not mapping_error:
        for candidate in mapping_index.values():
            if getattr(candidate, "case_kind", "") == "boundary":
                boundary_binding = candidate
                break
        if boundary_binding is not None:
            boundary_case_id = boundary_binding.native_case_ids[0]
            boundary_children = tuple(boundary_binding.required_child_case_ids)
            observed_ids = {
                qualified
                for qualified, _raw in normalized_cases
                if f"{owner}\x00{qualified}" in mapping_index
                and qualified != boundary_case_id
            }
            boundary_present_children = tuple(
                child for child in boundary_children if child in observed_ids
            )
            boundary_missing_children = tuple(
                child for child in boundary_children if child not in observed_ids
            )
    source_payload = {
        "schema_version": NATIVE_CASE_RESULT_SCHEMA,
        "owner_id": owner,
        "exit_code": exit_code,
        "stdout_fingerprint": stdout_fingerprint,
        "native_case_mapping": {
            "status": (
                "not_configured"
                if mapping is None and not mapping_error
                else "current"
                if mapping is not None
                else "invalid"
            ),
            "mapping_fingerprint": mapping.mapping_fingerprint if mapping is not None else "",
            "error": mapping_error,
            # Current native producers may expose more observations than the
            # small set of rows that this owner declares as blueprint
            # obligations.  Keep those exact rows visible without allowing
            # them to become an implicit leaf or a producer-wide failure.
            # Missing rows that *are* declared remain a hard error in the
            # binding verifier below.
            "unmapped_cases": unmapped_cases,
            "boundary": {
                "native_case_id": boundary_case_id,
                "required_child_case_ids": list(boundary_children),
                "present_child_case_ids": list(boundary_present_children),
                "missing_child_case_ids": list(boundary_missing_children),
                "status": (
                    "not_configured"
                    if mapping is None and not mapping_error
                    else "invalid"
                    if mapping_error
                    else "ready"
                    if not boundary_missing_children
                    else "incomplete"
                ),
            },
            "diagnostic_cases_present": [
                {
                    "qualified_case_id": qualified,
                    "source_fingerprint": fingerprint_payload(raw),
                }
                for qualified, raw in normalized_cases
                if qualified in diagnostic_case_ids
            ],
        },
        "cases": compact_cases,
        "structured_reports": [
            _structured_to_payload(item) for item in structured_reports
        ],
    }
    if report_payload is not None:
        source_payload["report"] = report_payload
    source_path = output_dir / "native-source.json"
    source_bytes = _json_bytes(source_payload) + b"\n"
    source_path.write_bytes(source_bytes)
    source_fp = _sha256_bytes(source_bytes)
    rows: list[dict[str, Any]] = []
    for case, raw in normalized_cases:
        binding = None
        if mapping is not None:
            binding = mapping_index.get(f"{owner}\x00{case}")
            if binding is None:
                if case in diagnostic_case_ids:
                    # This row is a current, explicitly named helper or
                    # transcript projection.  Preserve it in the immutable
                    # source envelope, but never let it satisfy a blueprint
                    # leaf or turn an unknown row into a pass.
                    continue
                # A current registry is authoritative.  Preserve the raw
                # observation above for diagnosis, but do not infer a kind,
                # dimensions, or expected status for an unmapped row.  It is
                # deliberately omitted from authoritative result rows.
                continue
        ok = _observed_ok(raw)
        status = _status(raw, ok=ok)
        outcome = "pass" if ok else ("rejected" if "violation" in status.casefold() or "reject" in status.casefold() else "fail")
        findings = _finding_codes(raw)
        compact = next(
            (item for item in compact_cases if item.get("qualified_case_id") == case),
            {"source_case_id": case, "source_fingerprint": fingerprint_payload(raw)},
        )
        oracle_fp = fingerprint_payload({"case": dict(raw), "status": status, "outcome": outcome})
        kind = binding.case_kind if binding is not None else _case_kind(raw, case)
        dimensions = {
            "boundary": ("input", "error", "decision", "retry", "timeout", "completion"),
            "bad": ("input", "state", "effect", "error", "decision", "completion"),
            "good": GOOD_DIMENSIONS,
        }[kind]
        observed_status = _expected_observed_status(raw, fallback=status)
        # An explicitly captured oracle result is a passed *check* even when
        # the model intentionally observed a violation.  Keep that distinction
        # in the row instead of deriving it from the wrapper's exit status.
        declared_kind = raw.get("case_kind")
        if (isinstance(declared_kind, str) and declared_kind in {"good", "boundary", "bad"}) or "expected_ok" in raw:
            outcome = "pass" if bool(raw.get("ok", ok)) else outcome
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=case,
                outcome=outcome,
                observed_status=observed_status,
                observed_finding_codes=findings,
                executed_dimensions=dimensions,
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:{case}:{dimension}",
                        "status": observed_status,
                        "ok": bool(ok),
                        "finding_codes": list(findings),
                        "observed": compact,
                    }
                    for dimension in dimensions
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=oracle_fp,
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.relative_to(output_dir)),
            ).to_dict()
        )
    if boundary_binding is not None and not mapping_error:
        # Child rows are already produced above; do not call any owner
        # callback again.  A complete boundary requires every frozen child to
        # be present and to have a passing producer outcome.  Bad-model cases
        # intentionally have ``observed_status=violation`` but their wrapper
        # oracle is still ``outcome=pass`` and therefore count as valid
        # children here.
        by_source_case = {
            str(row.get("source_case_id", "")): row
            for row in rows
            if isinstance(row, Mapping)
        }
        missing_children = tuple(
            child
            for child in boundary_children
            if child not in by_source_case
        )
        failed_children = tuple(
            child
            for child in boundary_children
            if child in by_source_case
            and by_source_case[child].get("outcome") != "pass"
        )
        boundary_ok = bool(boundary_children) and not missing_children and not failed_children
        boundary_status = "ok" if boundary_ok else "blocked"
        boundary_findings = tuple(
            ["boundary_child_result_missing"] if missing_children else []
        ) + tuple(
            ["boundary_child_result_failed"] if failed_children else []
        )
        boundary_observed = {
            "native_case_id": boundary_case_id,
            "required_child_case_ids": list(boundary_children),
            "present_child_case_ids": [
                child for child in boundary_children if child in by_source_case
            ],
            "missing_child_case_ids": list(missing_children),
            "failed_child_case_ids": list(failed_children),
            "status": boundary_status,
        }
        boundary_oracle_fp = fingerprint_payload(boundary_observed)
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=boundary_case_id,
                outcome="pass" if boundary_ok else "blocked",
                observed_status=boundary_status,
                observed_finding_codes=boundary_findings,
                executed_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:{boundary_case_id}:{dimension}",
                        "status": boundary_status,
                        "ok": boundary_ok,
                        "finding_codes": list(boundary_findings),
                        "observed": boundary_observed,
                    }
                    for dimension in ("input", "error", "decision", "retry", "timeout", "completion")
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=boundary_oracle_fp,
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.relative_to(output_dir)),
                child_case_ids=boundary_children,
            ).to_dict()
        )
    mapping_findings = tuple(
        dict.fromkeys(mapping_error.splitlines() if mapping_error else ())
    )
    if mapping_findings:
        # A registry failure is represented as a terminal blocked producer
        # result, never as a guessed set of leaf rows.  The complete raw
        # observations remain in native-source.json with the exact error.
        rows = []
    if not rows:
        # A runner with no case-shaped report is still recorded as a blocked
        # producer.  This keeps the strict gate honest instead of turning an
        # exit code into a fabricated behavioural pass.
        raw_payload = {
            "schema_version": NATIVE_CASE_RESULT_SCHEMA,
            "owner_id": owner,
            "source_case_id": "terminal",
            "observed_status": "no_case_projection",
            "outcome": "blocked",
            "stdout_fingerprint": stdout_fingerprint,
            "exit_code": exit_code,
            "mapping_findings": list(mapping_findings),
        }
        finding_code = (
            mapping_findings[0]
            if mapping_findings
            else "native_case_projection_missing"
        )
        rows.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id="terminal",
                outcome="blocked",
                observed_status="no_case_projection",
                observed_finding_codes=(finding_code,),
                executed_dimensions=GOOD_DIMENSIONS,
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{owner}:terminal:{dimension}",
                        "status": "no_case_projection",
                        "ok": False,
                        "finding_codes": [finding_code],
                        "observed": raw_payload,
                    }
                    for dimension in GOOD_DIMENSIONS
                ),
                result_artifact_fingerprint=source_fp,
                input_fingerprint=base_input,
                model_fingerprint=model_fp,
                code_fingerprint=code_fp,
                test_fingerprint=test_fp,
                oracle_fingerprint=fingerprint_payload(raw_payload),
                toolchain_fingerprint=tool_fp,
                environment_fingerprint=env_fp,
                raw_artifact_path=str(source_path.relative_to(output_dir)),
            ).to_dict()
        )
    target = output_dir / "native-case-results.json"
    target.write_bytes(_json_bytes({"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": rows}) + b"\n")
    return target


def native_main(owner_id: str, main: Callable[[], Any]) -> int:
    """Run one existing owner entrypoint and emit its producer evidence."""

    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path.cwd())).resolve()
    owner_key = _valid_text(owner_id).removeprefix("model:")
    if owner_key in _STRICT_NATIVE_OWNER_IDS:
        # Strict scenario owners return the typed tuple directly.  No wrapper
        # globals, stdout parser, existing JSON scan, or exit-code inference
        # is entered for this path.
        try:
            value = main()
            if type(value) is not tuple:
                raise NativeCaseProtocolError(
                    "strict native owner must return an exact tuple"
                )
            typed_results = tuple(value)
            result_path = _write_strict_native_results(
                owner_id,
                typed_results,
                output_dir,
            )
            marker_ids = [row.source_case_id for row in typed_results]
            print(
                "FLOWGUARD_EXECUTED_CASE_IDS="
                + json.dumps(marker_ids, ensure_ascii=False)
            )
            return 0 if all(row.outcome == "pass" for row in typed_results) else 1
        except (OSError, TypeError, ValueError, NativeCaseProtocolError) as exc:
            print(
                "strict native producer rejected: " + str(exc),
                file=sys.stderr,
            )
            return 1
    # Establish the file boundary before entering the owner.  Only files
    # created/replaced by this invocation may contribute JSON case rows;
    # retained output from an earlier invocation is evidence history, not a
    # current native case source.
    output_dir.mkdir(parents=True, exist_ok=True)
    before_json = _json_file_state(output_dir)
    captured = io.StringIO()
    structured_reports: list[Any] = []
    # Existing owner entrypoints return only an integer but call one of the
    # typed report producers below.  Wrap that call for this invocation so the
    # exact returned object is captured without executing the producer twice.
    # The original globals are restored in ``finally`` even when a runner
    # raises, so a long-lived interpreter cannot retain a stale wrapper.
    global_namespace = main.__globals__
    wrapped_globals: list[tuple[str, Any]] = []
    call_stack: list[str] = []
    capture_names = tuple(
        dict.fromkeys(
            (
                "run_review",
                "run_formal_workflow_suite",
                "run_bounded_system_benchmark",
                "run_exact_sequence",
                "run_exact_workflow_case",
            )
            + _OWNER_CAPTURE_FUNCTIONS.get(owner_key, ())
        )
    )
    for name in capture_names:
        original = global_namespace.get(name)
        if not callable(original):
            continue

        def _capture(
            *args: Any,
            __name: str = name,
            __original: Callable[..., Any] = original,
            **kwargs: Any,
        ) -> Any:
            parent = call_stack[-1] if call_stack else ""
            start = len(structured_reports)
            call_stack.append(__name)
            try:
                result = __original(*args, **kwargs)
            finally:
                call_stack.pop()
            nested = tuple(structured_reports[start:])
            structured_reports.append(
                _CapturedCall(
                    function_name=__name,
                    args=tuple(args),
                    kwargs=dict(kwargs),
                    result=result,
                    nested=nested,
                    parent_function=parent,
                )
            )
            return result

        wrapped_globals.append((name, original))
        global_namespace[name] = _capture
    # ``main`` is commonly passed as a function object looked up by the
    # owner's module before this bridge enters ``native_main`` (for example,
    # ``native_main("model:alpha", run_review)``).  Replacing the module
    # global alone therefore does not change that already-resolved object;
    # calling it directly would silently bypass the capture wrapper and lose
    # the producer's structured report graph.  Re-resolve the entrypoint by
    # its registered global name after installing wrappers.  An entrypoint
    # that is not a captured global keeps its original callable identity.
    entrypoint_name = _valid_text(getattr(main, "__name__", ""))
    entrypoint = global_namespace.get(entrypoint_name)
    if not callable(entrypoint):
        entrypoint = main
    exit_code = 1
    try:
        with redirect_stdout(captured):
            try:
                value = entrypoint()
                if isinstance(value, int):
                    exit_code = int(value)
                elif isinstance(value, Mapping) and type(value.get("exit_code")) is int:
                    exit_code = int(value["exit_code"])
                else:
                    exit_code = 0
            except SystemExit as exc:
                value = exc.code
                exit_code = int(value) if isinstance(value, int) else (0 if value in (None, "") else 1)
            except BaseException:
                traceback.print_exc()
                exit_code = 1
    finally:
        for name, original in wrapped_globals:
            global_namespace[name] = original
    stdout = captured.getvalue()
    after_json = _json_file_state(output_dir)
    changed_json = tuple(
        path
        for path, state in after_json.items()
        if before_json.get(path) != state
    )
    cases = _captured_structured_cases(structured_reports, owner_id=owner_id)
    cases += _load_existing_json(output_dir, paths=changed_json) + _collect_text_cases(
        stdout,
        include_metadata=True,
    )
    try:
        stdout_payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        stdout_payload = None
    if isinstance(stdout_payload, (Mapping, list, tuple)):
        _collect_json_cases(stdout_payload, cases)
    else:
        # A few established owner runners deliberately keep their readable
        # transcript and append one compact JSON envelope on its own line.
        # Consume only complete line-shaped JSON values; never attempt to
        # parse arbitrary transcript fragments or infer a case from text.
        for line in stdout.splitlines():
            candidate = line.strip()
            if not candidate or candidate[0] not in "[{":
                continue
            try:
                line_payload = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(line_payload, (Mapping, list, tuple)):
                _collect_json_cases(line_payload, cases)
    cases = _deduplicate_cases(cases, owner_id=owner_id)
    result_path = _write_results(
        owner_id,
        cases,
        stdout,
        exit_code,
        output_dir,
        structured_reports=structured_reports,
    )
    print(stdout, end="")
    # The liveness marker names only rows that were actually written to the
    # authoritative native-result envelope.  In particular, a producer may
    # expose supporting/diagnostic observations that are intentionally kept in
    # ``native-source.json`` but are not blueprint leaves.  Seeding the marker
    # from every captured observation would make the parent demand result rows
    # that the mapping explicitly excludes, turning a visible support record
    # into a false ``native_result_missing`` failure.
    marker_ids: list[str] = []
    # ``_write_results`` may add one explicit finite boundary aggregate after
    # projecting the producer's atomic cases.  Include the exact rows written
    # to the current result envelope in the liveness marker so the parent
    # orchestrator cannot mistake a successfully emitted boundary receipt for
    # a missing execution.  The marker is derived from this invocation's
    # immutable output; it does not discover or invent additional selectors.
    try:
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        result_payload = None
    if isinstance(result_payload, Mapping):
        raw_results = result_payload.get("results")
        if isinstance(raw_results, list):
            for row in raw_results:
                if not isinstance(row, Mapping):
                    continue
                source_case_id = _valid_text(row.get("source_case_id"))
                if source_case_id and source_case_id not in marker_ids:
                    marker_ids.append(source_case_id)
    if not marker_ids:
        marker_ids = ["terminal"]
    print(
        "FLOWGUARD_EXECUTED_CASE_IDS="
        + json.dumps(marker_ids, ensure_ascii=False)
    )
    return exit_code


__all__ = ["native_main"]
