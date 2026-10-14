"""Run-local execution binding; pytest itself stays in the outer invocation."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from flowguard.model_test_alignment import (
    ModelTestAlignmentPlan,
    ModelObligation,
    CodeContract,
    TestEvidence,
    bind_pytest_execution,
    fingerprint_value,
    pytest_alignment_input_digest,
    review_model_test_alignment,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
)


def run_inputs(tmp_path, outcome="passed", exit_code=0):
    source = tmp_path / "owner.py"
    source.write_text("def pay():\n    return 'paid'\n")
    nodeid = "tests/test_owner.py::test_pay"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_owner.py").write_text("from owner import pay\n\ndef test_pay():\n    assert pay() == 'paid'\n")
    child = {"passed": "", "failed": '<failure message="bad"/>', "skipped": '<skipped message="skip"/>'}[outcome]
    junit = tmp_path / "junit.xml"
    junit.write_text(f'<testsuite><testcase classname="wrong.display" name="test_pay">{child}</testcase></testsuite>')
    manifest = tmp_path / "nodeids.json"
    digest = pytest_alignment_input_digest(tmp_path, ("owner.py", "tests/test_owner.py"))
    metadata = {
        "command": "python -m pytest tests/test_owner.py -p flowguard.pytest_nodeid_recorder --junitxml=junit.xml",
        "exit_code": exit_code,
        "input_paths": ["owner.py", "tests/test_owner.py"],
        "input_digest_before": digest,
        "input_digest_after": digest,
    }
    manifest.write_text(json.dumps({**metadata, "schema_version": "flowguard.pytest_nodeids.v2",
        "run_id": "run-1", "project_root": str(tmp_path.resolve()),
        "junit_digest": hashlib.sha256(junit.read_bytes()).hexdigest(),
        "nodeids": [nodeid], "exit_status": exit_code, "statuses": {nodeid: outcome}}))
    plan = ModelTestAlignmentPlan("owner", test_evidence=(TestEvidence("pay", result_status="passed"),))
    return plan, dict(evidence_nodeids={"pay": nodeid}, junit_path=junit,
                     nodeid_manifest=manifest, run_metadata=metadata, project_root=tmp_path)


@pytest.mark.parametrize("outcome,selected,current_pass", [
    ("passed", True, True), ("failed", True, False),
    ("skipped", True, False), ("passed", False, False),
])
def test_exact_pytest_status_controls_execution_binding(tmp_path, outcome, selected, current_pass):
    plan, kwargs = run_inputs(tmp_path, outcome)
    if not selected:
        kwargs["evidence_nodeids"] = {"pay": "tests/test_owner.py::test_not_collected"}
    bound = bind_pytest_execution(plan, **kwargs)
    row = bound.test_evidence[0]
    assert row.has_current_pass() is current_pass
    assert row.result_status == (outcome if selected else "not_run")
    assert bound.require_executed_evidence and bound.require_source_audit
    # Real execution does not substitute for source audit.
    report = review_model_test_alignment(bound)
    assert not report.ok
    assert "missing_source_audit_report" in {finding.code for finding in report.findings}


def test_current_pass_with_actual_source_audit_closes_alignment(tmp_path):
    _, kwargs = run_inputs(tmp_path)
    contract = CodeContract("pay-code", path="owner.py", symbol="pay", implements_obligations=("paid",))
    evidence = TestEvidence("pay", path="tests/test_owner.py", test_name="test_pay",
                            covered_obligations=("paid",), covered_code_contracts=("pay-code",))
    sources = {path: (tmp_path / path).read_text() for path in (contract.path, evidence.path)}
    audit = review_python_contract_source_audit((contract,), (evidence,),
        audit_python_code_contracts((contract,), sources),
        audit_python_test_assertions((evidence,), (contract,), sources))
    plan = ModelTestAlignmentPlan("owner", obligations=(ModelObligation("paid"),),
        code_contracts=(contract,), test_evidence=(evidence,), source_audit_reports=(audit,))
    report = review_model_test_alignment(bind_pytest_execution(plan, **kwargs))
    assert report.ok, report.format_text()
    assert report.executed_evidence_status == "passed"


@pytest.mark.parametrize("when", ["during", "after"])
def test_changed_inputs_cannot_keep_current_execution_pass(tmp_path, when):
    plan, kwargs = run_inputs(tmp_path)
    (tmp_path / "owner.py").write_text("def pay():\n    return 'wrong'\n")
    if when == "during":
        data = json.loads(kwargs["nodeid_manifest"].read_text())
        data["input_digest_after"] = pytest_alignment_input_digest(tmp_path, ("owner.py", "tests/test_owner.py"))
        kwargs["nodeid_manifest"].write_text(json.dumps(data))
        kwargs["run_metadata"]["input_digest_after"] = data["input_digest_after"]
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert row.result_status == "passed" and not row.has_current_pass()
    assert any(f"changed {when}" in reason for reason in row.stale_reasons)


def test_nonzero_global_run_exit_is_visible_even_for_passed_bound_node(tmp_path):
    plan, kwargs = run_inputs(tmp_path, exit_code=1)
    bound = bind_pytest_execution(plan, **kwargs)
    row = bound.test_evidence[0]
    assert row.result_status == "passed" and not row.has_current_pass()
    report = review_model_test_alignment(bound)
    assert any("pytest run exit code is 1" in str(finding.metadata) for finding in report.findings)


def test_missing_exact_results_do_not_preserve_a_handwritten_pass(tmp_path):
    plan, kwargs = run_inputs(tmp_path)
    kwargs["nodeid_manifest"].unlink()
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert row.result_status == "not_run" and not row.has_current_pass()


def test_recorder_exit_mismatch_cannot_be_overridden_by_run_metadata(tmp_path):
    plan, kwargs = run_inputs(tmp_path, exit_code=1)
    kwargs["run_metadata"]["exit_code"] = 0
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert not row.has_current_pass()
    assert "pytest caller metadata disagrees with recorder: exit_code" in row.stale_reasons


def test_unrelated_input_scope_cannot_inherit_a_bound_node_pass(tmp_path):
    plan, kwargs = run_inputs(tmp_path)
    kwargs["run_metadata"]["input_paths"] = ["owner.py"]
    digest = pytest_alignment_input_digest(tmp_path, ("owner.py",))
    kwargs["run_metadata"]["input_digest_before"] = digest
    kwargs["run_metadata"]["input_digest_after"] = digest
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert not row.has_current_pass()
    assert "pytest caller metadata disagrees with recorder: input_paths" in row.stale_reasons


def test_node_file_must_match_planned_evidence_file(tmp_path):
    plan, kwargs = run_inputs(tmp_path)
    plan = replace(plan, test_evidence=(replace(plan.test_evidence[0], path="owner.py"),))
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert not row.has_current_pass()
    assert "pytest node file does not match the planned evidence path" in row.stale_reasons


def test_missing_bound_input_cannot_pass_even_with_matching_digests(tmp_path):
    plan, kwargs = run_inputs(tmp_path)
    (tmp_path / "tests/test_owner.py").unlink()
    digest = pytest_alignment_input_digest(tmp_path, kwargs["run_metadata"]["input_paths"])
    kwargs["run_metadata"]["input_digest_before"] = digest
    kwargs["run_metadata"]["input_digest_after"] = digest
    row = bind_pytest_execution(plan, **kwargs).test_evidence[0]
    assert not row.has_current_pass()
    assert any("input files are missing" in reason for reason in row.stale_reasons)


def test_fingerprint_value_is_deterministic():
    result = fingerprint_value({"value": 1})
    assert result == "sha256:48208f9428d64634bd8e28ff345bf0eab60d53c18fa2fbdb0b9bc1e84df2b5f6"


def test_no_input_scope_or_evidence_rows_cannot_create_execution_proof(tmp_path):
    plan, kwargs = run_inputs(tmp_path)
    kwargs["run_metadata"]["input_paths"] = []
    assert not bind_pytest_execution(plan, **kwargs).test_evidence[0].has_current_pass()
    with pytest.raises(ValueError, match="planned test evidence"):
        bind_pytest_execution(ModelTestAlignmentPlan("empty"), **kwargs)


def test_input_deletion_invalidates_digest_and_escape_is_rejected(tmp_path):
    _, kwargs = run_inputs(tmp_path)
    before = pytest_alignment_input_digest(tmp_path, ("owner.py",))
    (tmp_path / "owner.py").unlink()
    assert pytest_alignment_input_digest(tmp_path, ("owner.py",)) != before
    with pytest.raises(ValueError, match="escapes"):
        pytest_alignment_input_digest(tmp_path, ("../other.py",))


def test_rollout_runner_describes_declarations_without_claiming_native_execution():
    root = Path(__file__).resolve().parents[1]
    runner = root / ".flowguard/verification/owners/model_test_code_alignment/run_checks.py"
    text = runner.read_text()
    assert "native obligation declaration consistency:" in text
    assert "native execution evidence: NOT PROVIDED" in text
    assert "native_test_obligation_bindings_are_executed" not in text
