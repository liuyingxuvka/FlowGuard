from __future__ import annotations

import json
from dataclasses import dataclass, replace
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import flowguard.native_case_runner as native_runner
from flowguard.native_case_protocol import NativeCaseBinding
from flowguard.native_case_runner import (
    _CapturedCall,
    _captured_call_cases,
    _captured_structured_cases,
    _collect_text_cases,
    _deduplicate_cases,
    _path_quality_report_payload,
    _structured_to_payload,
    _write_results,
    native_main,
)
from flowguard.review import OracleReviewResult, ScenarioReviewReport
from flowguard.scenario import Scenario, ScenarioExpectation, ScenarioRun


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


def test_declared_source_export_occurs_once_in_native_episode(tmp_path, monkeypatch):
    from flowguard.model_path_quality import compile_declared_path_quality_source
    fp = "sha256:" + "a" * 64
    declaration = compile_declared_path_quality_source(model_id="fixture",
        model_instance_fingerprint=fp, source_refs=[{"path": "model.py", "source_fingerprint": fp}],
        graph_scope="native_check_contract", declared_contracts={"contract:fixture": {"cases": ["good", "bad"]}})
    calls = []
    def exporter(instance):
        calls.append("export")
        assert instance == fp
        return declaration
    def original_native(owner, main):
        calls.append("native")
        raw = {"owner_id": owner, "declared_path_quality_source": native_runner._DECLARED_SOURCE.get()}
        (tmp_path / "native-source.json").write_text(json.dumps(raw), encoding="utf-8")
        return main()
    def main():
        calls.append("main")
        return 0
    monkeypatch.setenv("FLOWGUARD_MODEL_INSTANCE_FINGERPRINT", fp)
    monkeypatch.setattr(native_runner, "_native_main", original_native)
    assert native_main("model:fixture", main, declared_source_exporter=exporter) == 0
    assert calls == ["export", "native", "main"]
    assert native_runner._DECLARED_SOURCE.get() is None
    raw = json.loads((tmp_path / "native-source.json").read_text(encoding="utf-8"))
    assert raw["declared_path_quality_source"] == declaration.to_dict()
    assert "owner_receipt_id" not in json.dumps(raw)
    monkeypatch.delenv("FLOWGUARD_MODEL_INSTANCE_FINGERPRINT")
    calls.clear()
    assert native_main("model:fixture", main, declared_source_exporter=exporter) == 1
    assert calls == []


def _r6_boundary_mapping(aggregate_count=1):
    fp = "sha256:" + "e" * 64
    leaf = NativeCaseBinding(owner_id="model:fixture", blueprint_case_id="fixture:boundary-leaf",
        blueprint_source_case_id="fixture:leaf", native_case_ids=("case:fixture:leaf",),
        case_kind="boundary", evidence_scope="model_policy",
        covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
        expected_status="pass", expected_observed_status="ok", mapping_fingerprint=fp)
    index = {"model:fixture\x00case:fixture:leaf": leaf}
    for number in range(aggregate_count):
        row = replace(leaf, blueprint_case_id=f"fixture:aggregate:{number}",
            blueprint_source_case_id=f"fixture:aggregate:{number}",
            native_case_ids=(f"case:fixture:aggregate:{number}",), required_child_case_ids=leaf.native_case_ids)
        index["model:fixture\x00" + row.native_case_ids[0]] = row
    return SimpleNamespace(mapping_fingerprint=fp, diagnostic_native_case_ids=()), index, ""


def test_boundary_leaf_is_not_synthetic_aggregate(tmp_path, monkeypatch):
    monkeypatch.setattr(native_runner, "_runtime_case_mapping", lambda owner: _r6_boundary_mapping())
    _write_results("model:fixture", ({"name": "leaf", "ok": True, "observed_status": "ok", "case_kind": "boundary"},), "", 0, tmp_path)
    payload = json.loads((tmp_path / "native-case-results.json").read_text())
    rows = {row["source_case_id"]: row for row in payload["results"]}
    assert set(rows) == {"case:fixture:leaf", "case:fixture:aggregate:0"}
    assert set(rows["case:fixture:leaf"]["executed_dimensions"]) == {"input", "error", "decision", "retry", "timeout", "completion"}
    assert not rows["case:fixture:leaf"]["child_case_ids"]
    assert rows["case:fixture:aggregate:0"]["child_case_ids"] == ["case:fixture:leaf"]
    assert rows["case:fixture:aggregate:0"]["outcome"] == "pass"


def test_native_owner_requires_exactly_one_boundary_aggregate(tmp_path, monkeypatch):
    from flowguard.native_case_protocol import NativeCaseProtocolError
    for count in (0, 2):
        monkeypatch.setattr(native_runner, "_runtime_case_mapping", lambda owner, count=count: _r6_boundary_mapping(count))
        with pytest.raises(NativeCaseProtocolError, match="exactly one boundary aggregate"):
            _write_results("model:fixture", ({"name": "leaf", "ok": True},), "", 0, tmp_path / str(count))
        assert not (tmp_path / str(count) / "native-case-results.json").exists()


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


def _executed_scenario_report(
    *, result_type=OracleReviewResult,
    specs=(("good", "ok", "pass"),
           ("bad", "violation", "expected_violation_observed"),
           ("boundary", "blocked", "known_limitation")),
):
    results = []
    for name, observed, status in specs:
        run = ScenarioRun(
            scenario=Scenario(name, "projection fixture", 0, (), ScenarioExpectation()),
            model_report=SimpleNamespace(to_dict=lambda: {"fixture": "model-report"}),
            traces=(SimpleNamespace(to_dict=lambda: {"initial_state": 0, "steps": []}),),
            final_states=(1,),
            observed_status=observed,
            observed_violation_names=("fixture_violation",) if observed == "violation" else (),
            evidence=("fixture:current-execution",),
        )
        results.append(result_type(name, "expected", observed, status, scenario_run=run))
    return ScenarioReviewReport(
        ok=all(row.ok is True for row in results),
        total_scenarios=len(results),
        passed=sum(row.status == "pass" for row in results),
        expected_violations_observed=sum(row.status == "expected_violation_observed" for row in results),
        unexpected_violations=0,
        missing_expected_violations=0,
        needs_human_review=0,
        known_limitations=sum(row.status == "known_limitation" for row in results),
        oracle_mismatches=0,
        results=tuple(results),
    )


def test_path_quality_selection_skips_exact_nonreports_without_projection(monkeypatch):
    report = _executed_scenario_report()

    def forbidden_projection(_self):
        raise AssertionError("a known non-report must not be expanded")

    monkeypatch.setattr(ScenarioRun, "to_dict", forbidden_projection)
    monkeypatch.setattr(OracleReviewResult, "to_dict", forbidden_projection)
    for value in (
        None, True, 1, 1.5, "terminal", report.results[0],
        report.results[0].scenario_run, {"unrelated": _OversizedProjection()},
    ):
        assert _path_quality_report_payload(value) is None


def test_path_quality_selection_projects_exact_report_once(monkeypatch):
    report = _executed_scenario_report()
    expected = report.to_dict()
    original = ScenarioReviewReport.to_dict
    calls = []

    def counted_projection(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(ScenarioReviewReport, "to_dict", counted_projection)
    assert _path_quality_report_payload(report) == expected
    assert len(calls) == 1
    assert calls[0] is report


@pytest.mark.parametrize("missing", ("results", "name", "run", "traces", "final_states"))
def test_path_quality_selection_rejects_incomplete_exact_report_before_projection(
    missing, monkeypatch
):
    report = _executed_scenario_report(specs=(("good", "ok", "pass"),))
    row = report.results[0]
    if missing == "results":
        report = replace(report, results=())
    else:
        if missing == "name":
            row = replace(row, scenario_name=" ")
        elif missing == "run":
            row = replace(row, scenario_run=None)
        else:
            row = replace(row, scenario_run=replace(row.scenario_run, **{missing: ()}))
        report = replace(report, results=(row,))

    def forbidden_projection(_self):
        raise AssertionError("an incomplete exact report must not be expanded")

    monkeypatch.setattr(ScenarioReviewReport, "to_dict", forbidden_projection)
    assert _path_quality_report_payload(report) is None


def test_path_quality_selection_preserves_custom_and_subclass_projection():
    payload = _executed_scenario_report().to_dict()
    calls = []

    class CustomReport:
        def to_dict(self):
            calls.append("custom")
            return payload

    class CompatibleRun(ScenarioRun):
        def to_dict(self):
            calls.append("subclass")
            return payload

    run = _executed_scenario_report().results[0].scenario_run
    assert _path_quality_report_payload(CustomReport()) == payload
    assert _path_quality_report_payload(CompatibleRun(**vars(run))) == payload
    assert calls == ["custom", "subclass"]


def test_path_quality_exact_report_keeps_invalid_results_fallback():
    report = replace(_executed_scenario_report(), results=1)
    assert _path_quality_report_payload(report) is None


@pytest.mark.parametrize("compatible_member", ("row", "run"))
def test_path_quality_exact_report_preserves_compatible_inner_projection(
    compatible_member,
):
    report = _executed_scenario_report(specs=(("good", "ok", "pass"),))
    expected = report.to_dict()
    calls = []

    class CompatibleRow:
        def to_dict(self):
            calls.append("row")
            return expected["results"][0]

    class CompatibleRun:
        def to_dict(self):
            calls.append("run")
            return expected["results"][0]["scenario_run"]

    row = (
        CompatibleRow()
        if compatible_member == "row"
        else replace(report.results[0], scenario_run=CompatibleRun())
    )
    report = replace(report, results=(row,))
    assert _path_quality_report_payload(report) == expected
    assert calls == [compatible_member]


def test_path_quality_exact_report_does_not_preconsume_results_iterator():
    report = _executed_scenario_report()
    expected = report.to_dict()
    report = replace(report, results=iter(report.results))
    assert _path_quality_report_payload(report) == expected


@pytest.mark.parametrize("field", ("traces", "final_states"))
def test_path_quality_exact_report_keeps_compatible_sequence_projection(field):
    class CompatibleSequence(list):
        def __bool__(self):
            raise AssertionError("a compatible sequence must use its original projection")

    report = _executed_scenario_report(specs=(("good", "ok", "pass"),))
    expected = report.to_dict()
    row = report.results[0]
    run = replace(row.scenario_run, **{
        field: CompatibleSequence(getattr(row.scenario_run, field)),
    })
    report = replace(report, results=(replace(row, scenario_run=run),))
    assert _path_quality_report_payload(report) == expected


@pytest.mark.parametrize("invalid", ("name", "run", "traces", "final_states", "empty_traces"))
def test_path_quality_custom_projection_keeps_original_payload_gate(invalid):
    payload = _executed_scenario_report().to_dict()
    row = payload["results"][0]
    if invalid == "name":
        row["scenario_name"] = ""
    elif invalid == "run":
        row["scenario_run"] = None
    elif invalid == "empty_traces":
        row["scenario_run"]["traces"] = []
    else:
        row["scenario_run"][invalid] = {"wrong": "shape"}

    class CustomReport:
        def to_dict(self):
            return payload

    assert _path_quality_report_payload(CustomReport()) is None


def test_captured_oracle_result_reuses_its_nested_run_projection(monkeypatch):
    report = _executed_scenario_report()
    original = ScenarioRun.to_dict
    calls = {}

    def counted_projection(run):
        calls[id(run)] = calls.get(id(run), 0) + 1
        return original(run)

    monkeypatch.setattr(ScenarioRun, "to_dict", counted_projection)
    rows = _captured_structured_cases((report,), owner_id="model:fixture")
    assert calls == {id(row.scenario_run): 1 for row in report.results}
    assert [row["observed_status"] for row in rows] == ["ok", "violation", "blocked"]
    assert rows[1]["ok"] is True
    assert rows[1]["case_kind"] == "bad"
    assert rows[1]["observed_violation_names"] == ["fixture_violation"]
    assert rows[2]["ok"] is None


def test_captured_custom_result_keeps_separate_run_projection():
    class CustomResult(_ScenarioResult):
        def to_dict(self):
            return {"scenario_name": self.scenario_name, "scenario_run": {"incomplete": True}}

    report = _ScenarioReport((CustomResult("custom", "pass", True, _ScenarioRun("ok")),))
    row = _captured_structured_cases((report,))[0]
    assert row["scenario_run"] == {"observed_status": "ok", "observed_violation_names": []}


def test_path_quality_selector_keeps_bounded_oversized_fallback():
    assert _path_quality_report_payload(_OversizedProjection()) is None


def test_projection_optimization_preserves_good_bad_boundary_wire_evidence(
    tmp_path, monkeypatch
):
    # A subclass retains the old nested-run fallback and provides the same
    # canonical wire fields as the exact leaf type being optimized.
    class CompatibleOracleResult(OracleReviewResult):
        pass

    report = _executed_scenario_report()
    legacy_report = _executed_scenario_report(result_type=CompatibleOracleResult)
    current_cases = _captured_structured_cases((report,), owner_id="model:fixture")
    legacy_cases = _captured_structured_cases((legacy_report,), owner_id="model:fixture")
    assert current_cases == legacy_cases
    monkeypatch.setattr(native_runner, "_runtime_case_mapping", lambda _owner: (None, {}, ""))
    captured = (_CapturedCall("run_review", (), {}, report),)
    current_dir = tmp_path / "current"
    legacy_dir = tmp_path / "legacy"
    _write_results("model:fixture", current_cases, "fixture output", 0, current_dir,
                   structured_reports=captured)

    # For this valid fixture the previous report selector serialized first,
    # then admitted this same payload. Keep its real unoptimized conversion.
    monkeypatch.setattr(native_runner, "_path_quality_report_payload", _structured_to_payload)
    _write_results("model:fixture", legacy_cases, "fixture output", 0, legacy_dir,
                   structured_reports=captured)
    current_files = {p.relative_to(current_dir): p.read_bytes() for p in current_dir.rglob("*.json")}
    legacy_files = {p.relative_to(legacy_dir): p.read_bytes() for p in legacy_dir.rglob("*.json")}
    assert current_files == legacy_files
    source = json.loads(current_files[Path("native-source.json")])
    assert source["report"] == report.to_dict()
    assert [row["scenario_name"] for row in source["report"]["results"]] == ["good", "bad", "boundary"]


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
    boundary_id = "case:fixture:boundary"
    boundary = replace(binding, blueprint_case_id="behavior-case:fixture:boundary",
        blueprint_source_case_id="fixture:boundary", native_case_ids=(boundary_id,),
        case_kind="boundary", covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"), required_child_case_ids=(mapped_id,))
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, {owner + "\x00" + mapped_id: binding, owner + "\x00" + boundary_id: boundary}, ""),
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
    assert {row["source_case_id"] for row in payload["results"]} == {mapped_id, boundary_id}


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
    boundary_id = "case:fixture:boundary"
    boundary = replace(binding, blueprint_case_id="behavior-case:fixture:boundary",
        blueprint_source_case_id="fixture:boundary", native_case_ids=(boundary_id,),
        case_kind="boundary", covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"), required_child_case_ids=(mapped_id,))
    monkeypatch.setattr(
        "flowguard.native_case_runner._runtime_case_mapping",
        lambda _owner: (mapping, {owner + "\x00" + mapped_id: binding, owner + "\x00" + boundary_id: boundary}, ""),
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
    assert set(marker) == {mapped_id, boundary_id}


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


def test_r8_native_source_exports_receipt_free_architecture_material_once(tmp_path, monkeypatch):
    from tests.test_native_case_protocol import _r8_current_material
    from flowguard.native_case_mapping import load_native_case_mapping
    declaration = _r8_current_material(tmp_path / "fixture")
    material = declaration.architecture_material
    calls = []
    monkeypatch.setenv("FLOWGUARD_MODEL_INSTANCE_FINGERPRINT", declaration.source.model_instance_fingerprint)
    mapping = load_native_case_mapping(tmp_path / "fixture")
    index = {row.owner_id + "\x00" + case: row for row in mapping.bindings for case in row.native_case_ids}
    monkeypatch.setattr(native_runner, "_runtime_case_mapping", lambda owner: (mapping, index, ""))
    def exporter(instance):
        calls.append("export")
        return declaration
    def classify(value):
        if type(value) is not int: raise TypeError("integer")
        return "positive" if value > 0 else "nonpositive"
    def main():
        calls.append("main")
        cases = []
        for name, value in (("overlap", 1), ("distinct", 0)):
            checks = native_runner.r8_finite_classification_checks("alpha", name, value, classify(value), "TypeError", classify)
            cases.append({"name": name, "ok": True, "observed_status": "ok", "semantic_checks": checks})
        cases.append({"name": "bad", "ok": True, "case_kind": "bad", "observed_status": "violation", "finding_codes": ["r8-finite:invalid"]})
        native_runner._write_results("model:alpha", tuple(cases), "", 0, tmp_path / "episode")
        return 0
    monkeypatch.setattr(native_runner, "_native_main", lambda owner, callback: callback())
    assert native_main("model:alpha", main, declared_source_exporter=exporter) == 0
    assert calls == ["export", "main"]
    raw = json.loads((tmp_path / "episode/native-source.json").read_text())
    assert raw["architecture_material"] == material
    assert "owner_receipt_id" not in json.dumps(raw["architecture_material"])
    assert native_runner._ARCHITECTURE_MATERIAL.get() is None
    result = json.loads((tmp_path / "episode/native-case-results.json").read_text())
    rows = [row for row in result["results"] if row["source_case_id"] in {"case:alpha:overlap", "case:alpha:distinct"}]
    assert len(rows) == 2
    for row in rows:
        assert len(row["oracle_results"]) == len(row["executed_dimensions"]) == 6
        inputs = [oracle for oracle in row["oracle_results"] if oracle["dimension"] == "input"]
        assert len(inputs) == 1
        checks = inputs[0]["observed"]["semantic_checks"]
        assert checks and all(item["status"] == "pass" for item in checks)
        assert len(checks) in (23, 46)
        original = next(item for item in raw["cases"]
                        if item["qualified_case_id"] == row["source_case_id"])
        assert original["semantic_checks"] == checks
        assert all("semantic_checks" not in oracle["observed"]
                   for oracle in row["oracle_results"] if oracle["dimension"] != "input")
        from flowguard.model_path_quality import (
            ArchitectureResponsibilityFact, _responsibility_native_observation_matches,
        )
        from flowguard.native_case_protocol import NativeModelCaseResult
        responsibility_id = next(item["responsibility_id"]
            for item in material["responsibility_context_rows"]
            if row["source_case_id"] in item["source_case_ids"])
        fact = next(ArchitectureResponsibilityFact.from_dict(item)
            for item in declaration.source.model_facts["responsibilities"]
            if item["responsibility_id"] == responsibility_id)
        observed = {item["path"]: item["sha256"]
                    for item in material["observed_source_inputs"]}
        assert _responsibility_native_observation_matches(
            fact, NativeModelCaseResult.from_dict(row), tmp_path, observed)


@pytest.mark.parametrize("missing_context", (False, True))
def test_r8_architecture_collector_authenticates_original_receipt_store(
    tmp_path, monkeypatch, missing_context,
):
    """The collector preserves the upstream verified context and binds its store."""
    from flowguard.architecture_native_material import collect_architecture_native_evidence
    import flowguard.model_regressions as regressions
    import flowguard.validation_ownership as ownership
    from flowguard.native_case_mapping import load_native_case_mapping
    from tests.test_native_case_protocol import _r8_current_material
    from tests.test_evidence_receipts import receipt, current_context
    root = tmp_path / "fixture"
    declaration = _r8_current_material(root)
    output = root / "episode"
    output.mkdir()
    (output / "native-source.json").write_text(json.dumps({
        "architecture_material": declaration.architecture_material}), encoding="utf-8")
    value = receipt("receipt:validation-owner:model:alpha:collector",
        subject_id="validation-owner:model:alpha", producer_id="validation-owner:model:alpha")
    original_context = current_context(value)
    leaf = SimpleNamespace(receipt=value, verification=SimpleNamespace(ok=True),
                           native_case_results=())
    parent_path = root / "parent.json"
    run = SimpleNamespace(model_id="alpha",
                         native_case_result_artifact_path=output / "native-case-results.json")
    parent = SimpleNamespace(results=(run,), parent_receipt_path=parent_path)
    resolved = SimpleNamespace(parent_artifact_path=parent_path,
                               child_evidence_by_model_id={"alpha": leaf})
    calls = []
    monkeypatch.setattr(regressions, "resolve_current_full_model_regression_parent",
                        lambda *args, **kwargs: resolved)
    import flowguard.native_case_mapping as mappings
    mapping = load_native_case_mapping(root)
    monkeypatch.setattr(mappings, "load_native_case_mapping", lambda path: mapping)
    selected = object()
    store = root / "receipts"
    def build_context(current, original_receipt, receipt_root):
        calls.append((current, original_receipt, receipt_root))
        return None if missing_context else original_context
    monkeypatch.setattr(ownership, "build_owner_receipt_context", build_context)
    observation = SimpleNamespace(current_by_owner={"model:alpha": selected})
    if missing_context:
        with pytest.raises(ValueError, match="no original proof context"):
            collect_architecture_native_evidence(root=root, candidate=None, parent=parent,
                planning_observation=observation, receipt_root=store)
    else:
        evidence = collect_architecture_native_evidence(root=root, candidate=None, parent=parent,
            planning_observation=observation, receipt_root=store)
        context = evidence["receipt_contexts"][value.receipt_id]
        assert context == replace(original_context,
            receipt_store_repository_root=str(root.resolve()),
            receipt_store_output_directory=str(store.resolve()))
        assert evidence["receipts"] == (value,)
        assert all(proof.owner_receipt_id == value.receipt_id
                   and proof.owner_receipt_fingerprint == value.fingerprint
                   for proofs in evidence["responsibility_evidence_bindings"].values()
                   for proof in proofs)
    assert calls == [(selected, value, store.resolve())]


@pytest.mark.parametrize("mutation", ("missing_store", "foreign_store", "tampered_proof"))
def test_r8_semantic_consumer_rejects_unbound_or_foreign_original_store(tmp_path, mutation):
    from tests.test_model_path_quality import _r8_verified_function_material
    from flowguard.model_path_quality import verify_responsibility_semantic_evidence
    fact, _, _, _, material, inputs, positive, _ = _r8_verified_function_material(tmp_path)
    assert positive.ready
    value = material["receipts"][0]
    context = inputs["receipt_contexts"][value.receipt_id]
    if mutation == "missing_store":
        context = replace(context, receipt_store_repository_root="", receipt_store_output_directory="")
    elif mutation == "foreign_store":
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        context = replace(context, receipt_store_output_directory=str(foreign))
    else:
        (Path(context.receipt_store_output_directory) / value.metadata["proof_relpath"]).write_text(
            '{"substituted":true}', encoding="utf-8")
    review = verify_responsibility_semantic_evidence(fact,
        **{**inputs, "receipt_contexts": {value.receipt_id: context}})
    assert not review.ready
    assert "responsibility_native_binding_invalid" in review.gap_ids
    assert review.admitted_binding_fingerprints == ()


def test_r8_required_architecture_check_absence_and_duplicates_block(tmp_path, monkeypatch):
    from tests.test_native_case_protocol import _r8_current_material
    from flowguard.native_case_protocol import NativeCaseProtocolError
    declaration = _r8_current_material(tmp_path)
    source = native_runner._DECLARED_SOURCE.set(declaration.source.to_dict())
    material = native_runner._ARCHITECTURE_MATERIAL.set(declaration.architecture_material)
    try:
        with pytest.raises(NativeCaseProtocolError, match="missing|cover"):
            native_runner._executed_architecture_checks("case:alpha:overlap", {"semantic_checks": []})
        def classify(value): return "positive" if value > 0 else "nonpositive"
        checks = native_runner.r8_finite_classification_checks("alpha", "overlap", 1, "positive", "TypeError", classify)
        assert native_runner._executed_architecture_checks("case:alpha:overlap", {"semantic_checks": checks}) == checks
        with pytest.raises(NativeCaseProtocolError, match="duplicate"):
            native_runner._executed_architecture_checks("case:alpha:overlap", {"semantic_checks": checks + [checks[0]]})
    finally:
        native_runner._ARCHITECTURE_MATERIAL.reset(material)
        native_runner._DECLARED_SOURCE.reset(source)


def test_r8_integration_case_scope_preserves_predecessor_mapping():
    import ast
    root = Path(__file__).resolve().parents[1]
    assert native_runner._qualified_case_id("model:authoritative_model_system", {"name": "r8_public_task_context_read"}) == "native-scenario:authoritative_model_system:r8_public_task_context_read"
    assert native_runner._qualified_case_id("model:model_maturation_loop", {"name": "r8_context_indexed_comparison"}) == "case:model_maturation_loop:r8_context_indexed_comparison"
    assert "run_r8_architecture_review" in native_runner._OWNER_CAPTURE_FUNCTIONS["model_maturation_loop"]
    runner = ast.parse((root / ".flowguard/verification/owners/model_maturation_loop/run_checks.py").read_text())
    main = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run_r8_architecture_review" for node in ast.walk(main))
    original = json.loads((root / ".flowguard/models/native-case-producer-overrides.json").read_text())
    assert original["schema_version"] == "flowguard.native_case_producer_overrides.v2"
    assert all(row["evidence_scope"] == "model_policy" for row in original["bindings"] if row["blueprint_case_id"].rsplit(":", 1)[-1] not in {case[2] for case in native_runner._R8_CASES + native_runner._R9_CASES} and row["owner_id"] in {"model:authoritative_model_system", "model:model_maturation_loop"})


def test_r8_actual_finite_changed_owner_preserves_unaffected_native_receipt():
    root = Path(__file__).resolve().parents[1]
    observed = native_runner._r8_affected_owner_observations(root)
    assert observed["valid"], observed
    assert observed["read_only"] and observed["authority"] and observed["rejected"]
    assert observed["counts"] == {"execute": 1, "reuse": 1}


def test_r8_actual_context_comparison_retains_remaining_contexts():
    observed = native_runner._r8_comparison_observations(Path(__file__).resolve().parents[1])
    assert set(observed) == {"comparison:related_overlap", "comparison:distinct_context"}
    for row in observed.values():
        assert row["valid"] and row["rejected"] and row["read_only"] and row["recovered"] and row["authority"], row
    overlap = observed["comparison:related_overlap"]["result"]
    assert len(overlap["relations"]) == 1
    assert overlap["relations"][0]["input_class_ids"] == ["ordinary"]
    assert {tuple(row["input_class_ids"]) for row in overlap["relations"][0]["remaining_contexts"]} == {("alpha-only",), ("beta-only",)}
    assert observed["comparison:distinct_context"]["result"]["rewrite_candidates"] == []


def test_r8_actual_hard_check_failure_cannot_be_hidden_by_wrapper_pass(tmp_path, monkeypatch):
    from tests.test_native_case_protocol import _r8_current_material
    from flowguard.native_case_mapping import load_native_case_mapping
    declaration = _r8_current_material(tmp_path / "fixture")
    mapping = load_native_case_mapping(tmp_path / "fixture")
    index = {row.owner_id + "\x00" + case: row for row in mapping.bindings for case in row.native_case_ids}
    monkeypatch.setattr(native_runner, "_runtime_case_mapping", lambda owner: (mapping, index, ""))
    source = native_runner._DECLARED_SOURCE.set(declaration.source.to_dict())
    material = native_runner._ARCHITECTURE_MATERIAL.set(declaration.architecture_material)
    try:
        def classify(value): return "positive" if value > 0 else "nonpositive"
        checks = native_runner.r8_finite_classification_checks("alpha", "overlap", 1, "positive", "TypeError", classify)
        checks[0]["status"] = "blocked"
        native_runner._write_results("model:alpha", ({"name": "overlap", "ok": True, "case_kind": "good", "observed_status": "ok", "semantic_checks": checks},), "", 0, tmp_path / "episode")
        payload = json.loads((tmp_path / "episode/native-case-results.json").read_text())
        actual = next(row for row in payload["results"] if row["source_case_id"] == "case:alpha:overlap")
        assert actual["outcome"] == "fail"
        assert all(row["ok"] is False for row in actual["oracle_results"])
    finally:
        native_runner._ARCHITECTURE_MATERIAL.reset(material)
        native_runner._DECLARED_SOURCE.reset(source)


def test_r8_actual_public_read_consumes_verified_task_context_without_writes():
    observations = native_runner._r8_public_read_observations(Path(__file__).resolve().parents[1])
    actual = observations["task:selected_current"]
    assert actual["valid"] and actual["authority"] and actual["rejected"] and actual["recovered"] and actual["read_only"], actual
    result = actual["result"]
    positive = result["public_read"]["functional_understanding"]
    assert positive["stopping_disposition"] == "model_maturation_closed_for_task"
    assert result["public_read"]["producer_count"] == result["public_read"]["write_count"] == 0
    narrow = result["narrowed_read"]["functional_understanding"]
    assert narrow["stopping_disposition"] == "needs_evidence" and narrow["gap_ids"]
    negative = result["unauthenticated_rejection"]
    assert negative["exception_type"] == ""
    rejected = negative["original_public_result"]
    invalid = rejected["functional_understanding"]
    assert invalid["stopping_disposition"] == "needs_evidence"
    assert "functional_task_context_invalid" in invalid["gap_ids"]
    assert invalid["first_gap"]["reason"] == "functional input raw fingerprint changed: " + result["original_task_context_ref"]["path"]
    assert not invalid.get("task_closed", False)
    assert rejected["producer_count"] == rejected["write_count"] == 0


def _r9_current_source_declaration(model_id="authoritative_model_system"):
    """Construction-only typed Source declaration, without native/receipt authority."""
    import importlib.util
    import hashlib
    root = Path(__file__).resolve().parents[1]
    path = root / ".flowguard/models/owners" / model_id / "model.py"
    name = "_r9_construction_owner_" + model_id
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    declaration = module.export_path_quality_source("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    return declaration


def _r9_original_three_construction():
    """Private test construction of three original typed bindings; no authority."""
    from copy import deepcopy
    from flowguard.implementation_inventory import ImplementationSurfaceInventory
    from flowguard.implementation_blueprint import review_model_implementation_bindings
    from flowguard.model_path_quality import parse_architecture_binding_report, derive_retained_elements
    from flowguard.native_case_protocol import parse_native_architecture_material
    declaration = _r9_current_source_declaration()
    raw = deepcopy(declaration.architecture_material)
    inventory = ImplementationSurfaceInventory.from_dict(raw["implementation_inventory"])
    current = parse_architecture_binding_report(raw["binding_report"])
    bindings = tuple(row for row in current.bindings if row.binding_id.startswith("binding:r8:"))
    report = review_model_implementation_bindings(inventory,
        required_model_element_ids=tuple(row.model_element_id for row in bindings),
        required_implementation_surface_ids=tuple(row.implementation_surface_id for row in bindings),
        bindings=bindings,
        semantic_specs=tuple(row for row in current.semantic_specs if row.semantic_spec_id.startswith("semantic-spec:r8:")),
        oracles=tuple(row for row in current.oracles if "r8_" in row.oracle_id))
    raw["binding_report"] = report.to_dict()
    raw["code_contracts"] = [row for row in raw["code_contracts"] if row["code_contract_id"].startswith("code-contract:r8:")]
    raw["native_case_contracts"] = [row for row in raw["native_case_contracts"] if "r8_" in row["source_case_id"]]
    raw["responsibility_context_rows"] = [row for row in raw["responsibility_context_rows"] if row["responsibility_id"].startswith("responsibility:r8:")]
    facts = deepcopy(dict(declaration.source.model_facts))
    facts["function_blocks"] = [row for row in facts["function_blocks"] if not row["id"].startswith("function-block:r9:")]
    facts["responsibilities"] = [row for row in facts["responsibilities"] if row["responsibility_id"].startswith("responsibility:r8:")]
    retained = tuple(row[0] for row in derive_retained_elements(facts))
    source = replace(declaration.source, model_facts=facts,
        element_groundings={key: value for key, value in declaration.source.element_groundings.items() if key in retained},
        declared_element_ids=retained)
    return source, parse_native_architecture_material(raw)


def test_r9_current_source_unmodeled_normal_surfaces_generate_nonempty_real_model_gap():
    source, material = _r9_original_three_construction()
    original = json.dumps(material, sort_keys=True)
    root = Path(__file__).resolve().parents[1]
    observed = native_runner.observe_r9_unmodeled_normal_surfaces(root,
        original_source=source, original_architecture_material=material)
    assert json.dumps(material, sort_keys=True) == original
    assert observed["source_defect_claim"] is False
    assert observed["claim_boundary"] == "source_only_finite_model_coverage_diagnostic_not_accepted_pointer"
    assert set(observed["original_binding_ids"]) == {"binding:r8:" + row[0] for row in native_runner._R8_CASES}
    gaps = {row["surface_id"] for row in observed["model_gaps"] if row["gap_id"].startswith("model_surface_unbound:")}
    assert set(observed["required_normal_surface_ids"]) <= gaps
    expected = {(row[3], row[4]) for row in native_runner._R9_CASES}
    targets = {(row["path"], row["symbol"]): row for row in observed["action_targets"]}
    assert expected <= set(targets)
    for key in expected:
        assert targets[key]["operation"] == "add_model_obligation"
        assert targets[key]["owner_id"] == ""
        assert targets[key]["requires_owner_admission"] is True
        assert targets[key]["surface_id"] in gaps
        assert targets[key]["source_fingerprint"]


def test_r9_minimum_normal_use_native_declarations_preserve_original_three_and_scope():
    from flowguard.model_path_quality import ArchitectureResponsibilityFact, HARD_SEMANTIC_DIMENSIONS, parse_architecture_binding_report
    from flowguard.model_test_alignment import CodeContract
    from flowguard.native_case_protocol import NativeModelCaseContract
    expected_bindings = {"binding:" + namespace + ":" + row[0]
        for namespace, rows in (("r8", native_runner._R8_CASES), ("r9", native_runner._R9_CASES)) for row in rows}
    actual_new_codes = {row.code_contract_id: row.to_dict() for row in native_runner.r9_functional_code_contracts()}
    for model in ("authoritative_model_system", "model_maturation_loop"):
        declaration = _r9_current_source_declaration(model)
        raw = declaration.architecture_material
        report = parse_architecture_binding_report(raw["binding_report"])
        assert report.ok and {row.binding_id for row in report.bindings} == expected_bindings
        codes = {CodeContract(**row).code_contract_id: row for row in raw["code_contracts"]}
        assert {key: codes[key] for key in actual_new_codes} == actual_new_codes
        own = [row for row in native_runner._R8_CASES + native_runner._R9_CASES if row[1] == model]
        contracts = [NativeModelCaseContract.from_dict(row) for row in raw["native_case_contracts"]]
        assert {row.source_case_id for row in contracts} == {
            ("native-scenario:" if model == "authoritative_model_system" else "case:") + model + ":" + row[2] for row in own}
        assert all(row.evidence_scope == "implementation_boundary" for row in contracts)
        facts = [ArchitectureResponsibilityFact.from_dict(row) for row in declaration.source.model_facts["responsibilities"]]
        assert len(facts) == len(own)
        assert len(raw["responsibility_context_rows"]) == len(HARD_SEMANTIC_DIMENSIONS) * sum(len(row[7]) for row in own)
        assert all(row.semantic_evidence_bindings == () for row in facts)
        actual_invariants = {row["invariant_name"] for row in declaration.source.element_groundings.values()
            if row.get("kind") == "native_invariant_binding"}
        expected_new_invariants = {"r8-functional-actual-checks:" + row[2]
            for row in native_runner._R9_CASES if row[1] == model}
        assert expected_new_invariants <= actual_invariants
        # The typed exporter/parser owns nested material validation. Inspect
        # exact episode authority fields here, not substrings of legitimate
        # inventory symbols such as receipt-related production functions.
        episode_authority_keys = {"receipt_id", "owner_receipt_id", "receipt_fingerprint",
            "owner_receipt_fingerprint", "current_context", "accepted_head", "head_id"}
        assert not episode_authority_keys.intersection(raw)
    import ast
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "flowguard/native_case_runner.py").read_text())
    resolver = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_r9_pointer_detail_observations")
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "resolve_architecture_improvement_pointer" for node in ast.walk(resolver))


@pytest.mark.parametrize(
    ("case_name", "responsibility", "input_classes"),
    (
        (
            "r9_finite_growth_observation",
            "responsibility:r9:finite-growth-observation",
            ("growth:finite_present_and_missing", "growth:unknown_admission"),
        ),
        (
            "r9_pointer_detail_navigation",
            "responsibility:r9:pointer-detail-navigation",
            ("pointer:accepted_current", "pointer:wrong_hash_or_head"),
        ),
    ),
)
def test_r9_actual_growth_and_pointer_cases_preserve_semantic_evidence_and_source_authority(
    case_name, responsibility, input_classes
):
    """Run genuine original fixture evidence; declarations alone cannot cover it."""
    from flowguard.model_authority_store import load_current_model_authority_state
    from flowguard.model_path_quality import HARD_SEMANTIC_DIMENSIONS

    root = Path(__file__).resolve().parents[1]
    project = root / ".flowguard/project.toml"
    project_before = project.read_bytes()
    state_before = load_current_model_authority_state(root, reverify_current_sources=False)
    authority_before = (
        state_before.head.fingerprint,
        state_before.snapshot.fingerprint,
        state_before.accepted_revision.fingerprint,
    )
    expected = native_runner.load_r8_hard_semantics(
        root, responsibility, "openspec/specs/task-aware-functional-map/spec.md"
    )

    # This traverses the real two-owner original native producer, current leaf
    # authentication, accepted fixture authority and the production interface.
    # No mock replaces authenticated_scopes or the actual observation function.
    checks = native_runner.run_r8_functional_case(root, case_name)
    assert project.read_bytes() == project_before
    state_after = load_current_model_authority_state(root, reverify_current_sources=False)
    assert (
        state_after.head.fingerprint,
        state_after.snapshot.fingerprint,
        state_after.accepted_revision.fingerprint,
    ) == authority_before

    expected_keys = {
        (responsibility, dimension, context)
        for dimension in HARD_SEMANTIC_DIMENSIONS
        for context in input_classes
    }
    actual_keys = [
        (row["responsibility_id"], row["hard_dimension_id"], row["input_class_id"])
        for row in checks
    ]
    assert len(checks) == len(expected_keys) == 2 * len(HARD_SEMANTIC_DIMENSIONS)
    assert set(actual_keys) == expected_keys
    assert len(actual_keys) == len(set(actual_keys))
    fields = {
        "check_id", "responsibility_id", "hard_dimension_id", "input_class_id",
        "args", "observed", "expected", "status",
    }
    for row, key in zip(checks, actual_keys):
        assert set(row) == fields
        assert row["check_id"] == "semantic-check:" + ":".join(key)
        assert row["expected"] == expected[row["hard_dimension_id"]]
        assert row["args"] and row["observed"]
        assert row["status"] == "pass", row
        assert row["observed"]["condition_met"] is True
        assert row["observed"]["owned_tree_unchanged"] is True
        assert row["observed"]["bounded_effects_valid"] is True

    by_context = {}
    for row in checks:
        result = row["observed"]["actual_production_result"]
        original = by_context.setdefault(row["input_class_id"], result)
        assert result == original
    assert set(by_context) == set(input_classes)

    if case_name == "r9_finite_growth_observation":
        expected_states = {
            "src/deleted.py": "missing",
            "src/new-neighbor.py": "present",
            "src/rename-old.py": "missing",
            "src/rename-new.py": "present",
        }
        for result in by_context.values():
            growth = result["growth"]
            assert growth["live_unregistered_file_detection"] == "FINITE_OBSERVATION"
            assert tuple(growth["checked_observed_paths"]) == tuple(sorted(("src/alpha.py", *expected_states)))
            gaps = {row["path"]: row for row in growth["growth_gaps"]}
            assert set(gaps) == set(expected_states)
            assert {path: row["observed_state"] for path, row in gaps.items()} == expected_states
            assert {"src/deleted.py", "src/rename-old.py"} <= set(result["actual_missing_paths"])
            assert "src/alpha.py" not in gaps
            for path, gap in gaps.items():
                assert not gap["next_owner_id"]
                assert gap["next_action"] == "boundary_admission_required:" + path
            assert result["unobserved"]["live_unregistered_file_detection"] == "NOT_OBSERVED"
            assert not result["unobserved"]["growth_gaps"]
        assert all(row["observed"]["actual_rejected_input_error"] for row in checks)
    else:
        for result in by_context.values():
            resolved = result["resolved_original_pointer"]
            assert result["public_batch"]["status"] == "pass"
            assert resolved["action_targets"]
            assert result["actual_accepted_head_fingerprint"] != result["actual_foreign_head_fingerprint"]
            errors = result["negative_observations"]
            assert set(errors) == {"wrong_hash", "foreign_head", "missing_detail"}
            assert all(errors.values())
        # The recovery hard dimension is a fresh production re-resolution after
        # restoring the exact original detail bytes, not a cached fixture echo.
        recoveries = [row for row in checks if row["hard_dimension_id"] == "recovery"]
        assert len(recoveries) == len(input_classes)
        assert all(row["observed"]["condition_met"] for row in recoveries)
