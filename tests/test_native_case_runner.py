from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from flowguard.native_case_protocol import NativeCaseBinding
from flowguard.native_case_runner import (
    _CapturedCall,
    _captured_call_cases,
    _captured_structured_cases,
    _collect_text_cases,
    _deduplicate_cases,
    _structured_to_payload,
    _write_results,
    native_main,
)


@dataclass(frozen=True)
class _ScenarioRun:
    observed_status: str
    observed_violation_names: tuple[str, ...] = ()

    def to_dict(self):
        return {
            "observed_status": self.observed_status,
            "observed_violation_names": list(self.observed_violation_names),
        }


@dataclass(frozen=True)
class _ScenarioResult:
    scenario_name: str
    status: str
    ok: bool
    scenario_run: _ScenarioRun

    def to_dict(self):
        return {
            "scenario_name": self.scenario_name,
            "status": self.status,
            "ok": self.ok,
            "scenario_run": self.scenario_run.to_dict(),
        }


@dataclass(frozen=True)
class _ScenarioReport:
    results: tuple[_ScenarioResult, ...]

    def to_dict(self):
        return {"results": [item.to_dict() for item in self.results]}


@dataclass(frozen=True)
class _FormalCase:
    name: str
    expected_ok: bool
    observed_ok: bool

    @property
    def ok(self):
        return self.expected_ok is self.observed_ok

    def to_dict(self):
        return {
            "name": self.name,
            "expected_ok": self.expected_ok,
            "observed_ok": self.observed_ok,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class _FormalReport:
    case_results: tuple[_FormalCase, ...]


@dataclass(frozen=True)
class _BenchmarkItem:
    family_id: str
    case_id: str
    observed_status: str
    ok: bool = True

    @property
    def report(self):
        return type("Report", (), {"status": self.observed_status})()

    def to_dict(self):
        return {
            "family_id": self.family_id,
            "case_id": self.case_id,
            "observed_status": self.observed_status,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class _BenchmarkReport:
    cases: tuple[_BenchmarkItem, ...]


class _OversizedProjection:
    status = "pass"
    ok = True
    cases = ()

    def to_dict(self):
        raise MemoryError("unbounded test projection")

    def __repr__(self):  # pragma: no cover - proves repr is not the fallback
        raise AssertionError("repr must not be used for captured evidence")


def run_review():
    """Module-global hook so ``native_main`` can wrap a real owner symbol."""

    raise AssertionError("test hook was not installed")


def _owner_main():
    run_review()
    return 0


def test_structured_projectors_keep_oracle_and_model_status_distinct():
    scenario = _ScenarioReport(
        (
            _ScenarioResult(
                "good-flow",
                "pass",
                True,
                _ScenarioRun("ok"),
            ),
            _ScenarioResult(
                "bad-flow",
                "expected_violation_observed",
                True,
                _ScenarioRun("violation", ("expected_failure",)),
            ),
        )
    )
    formal = _FormalReport((_FormalCase("formal-good", True, True), _FormalCase("formal-bad", False, False)))
    benchmark = _BenchmarkReport(
        (
            _BenchmarkItem("family", "repaired", "pass"),
            _BenchmarkItem("family", "bad", "fail", True),
            _BenchmarkItem("family", "missing-semantics", "blocked", True),
        )
    )

    rows = _captured_structured_cases((scenario, formal, benchmark))
    by_name = {row.get("scenario_name", row.get("name")): row for row in rows}

    assert by_name["good-flow"]["case_kind"] == "good"
    assert by_name["good-flow"]["observed_status"] == "ok"
    assert by_name["bad-flow"]["case_kind"] == "bad"
    assert by_name["bad-flow"]["observed_status"] == "violation"
    assert by_name["bad-flow"]["observed_violation_names"] == ["expected_failure"]
    assert by_name["formal-good"]["case_kind"] == "good"
    assert by_name["formal-bad"]["case_kind"] == "bad"
    assert by_name["repaired"]["case_kind"] == "good"
    assert by_name["bad"]["case_kind"] == "bad"
    assert by_name["missing-semantics"]["case_kind"] == "boundary"


def test_structured_payload_uses_bounded_fallback_after_oversized_projection():
    payload = _structured_to_payload(_OversizedProjection())
    assert payload == {
        "type": "_OversizedProjection",
        "status": "pass",
        "ok": True,
        "cases_count": 0,
    }


def test_native_main_calls_registered_report_producer_once_and_writes_leaves(
    tmp_path, monkeypatch, capsys
):
    calls = []
    report = _ScenarioReport(
        (
            _ScenarioResult(
                "good-flow",
                "pass",
                True,
                _ScenarioRun("ok"),
            ),
            _ScenarioResult(
                "bad-flow",
                "expected_violation_observed",
                True,
                _ScenarioRun("violation", ("expected_failure",)),
            ),
        )
    )

    def _run_review():
        calls.append("run")
        return report

    monkeypatch.setattr(sys.modules[__name__], "run_review", _run_review)

    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))
    assert native_main("model:adversarial_scenario_synthesis", _owner_main) == 0
    assert calls == ["run"]
    capsys.readouterr()

    source = json.loads((tmp_path / "native-source.json").read_text(encoding="utf-8"))
    assert len(source["structured_reports"]) == 1
    assert len(source["cases"]) == 2

    payload = json.loads((tmp_path / "native-case-results.json").read_text(encoding="utf-8"))
    rows = {row["source_case_id"]: row for row in payload["results"]}
    good = rows["native-scenario:adversarial_scenario_synthesis:good-flow"]
    bad = rows["native-scenario:adversarial_scenario_synthesis:bad-flow"]
    assert good["outcome"] == "pass"
    assert good["observed_status"] == "ok"
    assert bad["outcome"] == "pass"
    assert bad["observed_status"] == "violation"
    assert bad["observed_finding_codes"] == ["expected_failure"]


def test_native_main_does_not_promote_historical_json_as_current_cases(
    tmp_path, monkeypatch, capsys
):
    historical = tmp_path / "previous-invocation.json"
    historical.write_text(
        json.dumps(
            {
                "cases": [
                    {"name": "stale-case", "status": "pass", "ok": True}
                ]
            }
        ),
        encoding="utf-8",
    )

    def _owner_main_writing_current_json():
        Path(os.environ["FLOWGUARD_OUTPUT_DIR"], "current-invocation.json").write_text(
            json.dumps(
                {
                    "cases": [
                        {"name": "current-case", "status": "pass", "ok": True}
                    ]
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))
    assert native_main("model:unregistered-owner", _owner_main_writing_current_json) == 0
    capsys.readouterr()

    source = json.loads((tmp_path / "native-source.json").read_text(encoding="utf-8"))
    case_ids = {row["qualified_case_id"] for row in source["cases"]}
    assert "case:unregistered-owner:current-case" in case_ids
    assert "case:unregistered-owner:stale-case" not in case_ids


def test_text_projection_preserves_inline_codes_without_parsing_aggregate_summary():
    rows = _collect_text_cases(
        """
green_boundary: PASS codes=[]
forbidden_input_accepted: PASS codes=['boundary_forbidden_input_accepted']
cases: 2
failed: 0
"""
    )
    assert [row["name"] for row in rows] == [
        "green_boundary",
        "forbidden_input_accepted",
    ]
    assert "finding_codes" not in rows[0]
    assert rows[1]["finding_codes"] == ["boundary_forbidden_input_accepted"]


def test_text_projection_keeps_exact_formal_positive_as_one_good_leaf():
    rows = _collect_text_cases("correct_model_maturation_loop: exact model pass\n")
    assert rows == [
        {
            "name": "correct_model_maturation_loop",
            "status": "pass",
            "observed_status": "ok",
            "ok": True,
            "case_kind": "good",
        }
    ]


def test_text_projection_accepts_bounded_formal_trailing_annotation():
    rows = _collect_text_cases(
        "correct_ai_route_handoff: observed=OK expected=OK "
        "match=yes formal=pass exact=yes\n"
    )
    assert rows == [
        {
            "name": "correct_ai_route_handoff",
            "observed_status": "ok",
            "expected_ok": True,
            "match": "yes",
            "ok": True,
            "formal": "pass",
        }
    ]


def test_named_workflow_bool_projection_keeps_exact_positive_leaf():
    call = _CapturedCall(
        function_name="run_exact_workflow_case",
        args=("bounded blueprint path qualified: complete",),
        kwargs={},
        result=True,
    )

    assert _captured_call_cases(
        call,
        owner_id="model:implementation_blueprint",
    ) == [
        {
            "name": "complete",
            "ok": True,
            "status": "pass",
            "observed_status": "ok",
            "case_kind": "good",
            "projection_priority": 44,
            "projection_source": "structured",
        }
    ]


def test_print_case_projects_expected_rejection_as_passing_bad_leaf():
    run = SimpleNamespace(
        model_report=SimpleNamespace(ok=False, violations=()),
        observed_status="violation",
        traces=(),
    )
    call = _CapturedCall(
        function_name="print_case",
        args=("broken-diagram", run, False),
        kwargs={},
        result=None,
    )

    rows = _captured_call_cases(call, owner_id="model:user_facing_model_diagrams")

    assert rows == [
        {
            "name": "broken-diagram",
            "ok": True,
            "observed_status": "violation",
            "observed_finding_codes": [],
            "trace_labels": [],
            "case_kind": "bad",
            "projection_priority": 45,
            "projection_source": "structured",
        }
    ]


def test_tuple_review_projection_keeps_matched_bad_case_as_violation():
    call = _CapturedCall(
        function_name="run_rollout_review",
        args=(),
        kwargs={},
        result=(("green", True, ()), ("broken", True, ("expected_failure",))),
    )
    rows = _captured_structured_cases((call,), owner_id="model:fixture")
    by_name = {row["name"]: row for row in rows}
    assert by_name["green"]["status"] == "pass"
    assert by_name["green"]["observed_status"] == "ok"
    assert by_name["broken"]["status"] == "pass"
    assert by_name["broken"]["observed_status"] == "violation"
    assert by_name["broken"]["finding_codes"] == ["expected_failure"]


def test_benchmark_deduplication_keeps_each_family_variant_leaf():
    rows = []
    for family in ("family-a", "family-b"):
        rows.append({"family_id": family, "case_id": "repaired", "ok": True})
        rows.append({"family_id": family, "case_id": "bad", "ok": True})
    deduplicated = _deduplicate_cases(rows, owner_id="model:bounded_system_composition_benchmark")
    assert [row["family_id"] + ":" + row["case_id"] for row in deduplicated] == [
        "family-a:repaired",
        "family-a:bad",
        "family-b:repaired",
        "family-b:bad",
    ]


def test_current_mapping_keeps_unmapped_native_observations_out_of_authoritative_rows(
    tmp_path, monkeypatch
):
    """Extra producer observations remain diagnostic, never implicit leaves."""

    owner = "model:fixture"
    mapped_id = "case:fixture:declared"
    binding = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:good:declared",
        blueprint_source_case_id="fixture:declared",
        native_case_ids=(mapped_id,),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=("input", "state", "output", "effect", "order", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        mapping_fingerprint="sha256:" + "a" * 64,
    )
    mapping = SimpleNamespace(
        mapping_fingerprint=binding.mapping_fingerprint,
        diagnostic_native_case_ids=(),
    )
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, {owner + "\x00" + mapped_id: binding}, ""),
    )

    _write_results(
        owner,
        (
            {"name": "declared", "ok": True, "observed_status": "ok"},
            {"name": "supporting-helper", "ok": True, "observed_status": "ok"},
        ),
        "",
        0,
        tmp_path,
    )

    source = json.loads((tmp_path / "native-source.json").read_text(encoding="utf-8"))
    unmapped = source["native_case_mapping"]["unmapped_cases"]
    assert [item["qualified_case_id"] for item in unmapped] == [
        "case:fixture:supporting-helper"
    ]
    assert unmapped[0]["disposition"] == "supporting_native_observation"

    payload = json.loads((tmp_path / "native-case-results.json").read_text(encoding="utf-8"))
    assert [row["source_case_id"] for row in payload["results"]] == [mapped_id]


def test_native_main_marker_contains_only_written_mapped_rows(
    tmp_path, monkeypatch, capsys
):
    """Supporting observations must not become parent liveness obligations."""

    owner = "model:fixture"
    mapped_id = "case:fixture:declared"
    fp = "sha256:" + "d" * 64
    binding = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:good:declared",
        blueprint_source_case_id="fixture:declared",
        native_case_ids=(mapped_id,),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=("input", "state", "output", "effect", "order", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        mapping_fingerprint=fp,
    )
    mapping = SimpleNamespace(mapping_fingerprint=fp, diagnostic_native_case_ids=())
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, {owner + "\x00" + mapped_id: binding}, ""),
    )

    monkeypatch.setattr(
        sys.modules[__name__],
        "run_review",
        lambda: (("declared", True, ()), ("supporting-helper", True, ())),
    )
    monkeypatch.setenv("FLOWGUARD_OUTPUT_DIR", str(tmp_path))

    assert native_main(owner, _owner_main) == 0
    output = capsys.readouterr().out
    marker_line = next(
        line for line in output.splitlines()
        if line.startswith("FLOWGUARD_EXECUTED_CASE_IDS=")
    )
    marker = json.loads(marker_line.split("=", 1)[1])
    assert marker == [mapped_id]


def test_current_mapping_emits_finite_boundary_after_all_children(
    tmp_path, monkeypatch
):
    """A boundary is a real aggregate receipt over concrete child rows."""

    owner = "model:fixture"
    fp = "sha256:" + "b" * 64
    child_ids = ("case:fixture:declared", "case:fixture:known-bad")
    child_good = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:good:declared",
        blueprint_source_case_id="fixture:declared",
        native_case_ids=(child_ids[0],),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=("input", "state", "output", "effect", "order", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        mapping_fingerprint=fp,
    )
    child_bad = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:bad:known-bad",
        blueprint_source_case_id="fixture:known-bad",
        native_case_ids=(child_ids[1],),
        case_kind="bad",
        evidence_scope="model_policy",
        covered_dimensions=("input", "state", "effect", "error", "decision", "completion"),
        expected_status="pass",
        expected_observed_status="violation",
        mapping_fingerprint=fp,
    )
    boundary_id = "case:fixture:boundary:finite-domain"
    boundary = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:boundary:boundary",
        blueprint_source_case_id="fixture:boundary",
        native_case_ids=(boundary_id,),
        case_kind="boundary",
        evidence_scope="model_policy",
        covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        required_child_case_ids=child_ids,
        mapping_fingerprint=fp,
    )
    mapping = SimpleNamespace(
        mapping_fingerprint=fp,
        diagnostic_native_case_ids=(),
    )
    index = {
        owner + "\x00" + child_ids[0]: child_good,
        owner + "\x00" + child_ids[1]: child_bad,
        owner + "\x00" + boundary_id: boundary,
    }
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, index, ""),
    )

    _write_results(
        owner,
        (
            {"name": "declared", "ok": True, "observed_status": "ok"},
            {"name": "known-bad", "ok": True, "observed_status": "violation"},
        ),
        "",
        0,
        tmp_path,
    )

    payload = json.loads((tmp_path / "native-case-results.json").read_text(encoding="utf-8"))
    rows = {row["source_case_id"]: row for row in payload["results"]}
    assert rows[boundary_id]["outcome"] == "pass"
    assert rows[boundary_id]["observed_status"] == "ok"
    assert rows[boundary_id]["child_case_ids"] == list(child_ids)
    assert all(item["ok"] for item in rows[boundary_id]["oracle_results"])


def test_current_mapping_blocks_boundary_when_a_frozen_child_is_missing(
    tmp_path, monkeypatch
):
    fp = "sha256:" + "c" * 64
    owner = "model:fixture"
    child_id = "case:fixture:declared"
    boundary_id = "case:fixture:boundary:finite-domain"
    child = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:good:declared",
        blueprint_source_case_id="fixture:declared",
        native_case_ids=(child_id,),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=("input", "state", "output", "effect", "order", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        mapping_fingerprint=fp,
    )
    boundary = NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id="behavior-case:fixture:boundary:boundary",
        blueprint_source_case_id="fixture:boundary",
        native_case_ids=(boundary_id,),
        case_kind="boundary",
        evidence_scope="model_policy",
        covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
        expected_status="pass",
        expected_observed_status="ok",
        required_child_case_ids=(child_id, "case:fixture:missing"),
        mapping_fingerprint=fp,
    )
    mapping = SimpleNamespace(mapping_fingerprint=fp, diagnostic_native_case_ids=())
    index = {
        owner + "\x00" + child_id: child,
        owner + "\x00" + boundary_id: boundary,
    }
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, index, ""),
    )

    _write_results(
        owner,
        ({"name": "declared", "ok": True, "observed_status": "ok"},),
        "",
        0,
        tmp_path,
    )

    payload = json.loads((tmp_path / "native-case-results.json").read_text(encoding="utf-8"))
    rows = {row["source_case_id"]: row for row in payload["results"]}
    assert rows[boundary_id]["outcome"] == "blocked"
    assert rows[boundary_id]["observed_status"] == "blocked"
    assert rows[boundary_id]["observed_finding_codes"] == ["boundary_child_result_missing"]
