"""Independent finding-policy child with fresh native report provenance.

Exercise check_target's bucket logic and map.cli.cmd_check's strict boundary,
including real proof code gaps, design failures and unbound-invariant warnings.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.map import cli as map_cli
from flowguard.map import target as native
from flowguard.map.check import run_check
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import ignore_patterns, load_map
from flowguard.map.targetfile import build_target_view, load_target
from target_life_cycle import make_project, stage_target, write_json, probe_regular_model

MODEL_ID = "target_findings"
PARENT = "target_life_cycle"
IMPLEMENTED_BY = {
    "Downgrade": "flowguard/map/target.py:moving_to_target",
    "Classify": "flowguard/map/target.py:check_target",
}
TESTED_BY = {
    "each_defect_rejected": [
        "tests/test_flowguard_target.py:test_change_marks_only_planned_breakage_and_keeps_tests",
        "tests/test_flowguard_target.py:test_unplanned_catalog_breakage_stays_an_error_with_a_target",
        "tests/test_flowguard_target.py:test_target_real_proof_dispositions_and_hard_boundaries",
        "tests/test_flowguard_target.py:test_dropping_a_responsibility_is_owner_dropped",
    ],
    "every_defect_reported": [
        "tests/test_flowguard_target.py:test_change_marks_only_planned_breakage_and_keeps_tests",
        "tests/test_flowguard_target.py:test_unplanned_catalog_breakage_stays_an_error_with_a_target",
        "tests/test_flowguard_target.py:test_target_real_proof_dispositions_and_hard_boundaries",
        "tests/test_flowguard_target.py:test_dropping_a_responsibility_is_owner_dropped",
    ],
}


@dataclass(frozen=True)
class Case:
    name: str
    provenance: str
    replaced: bool
    phase: str
    disposition: str


# These are concrete promises about ten fact origins, not code-set copies.
CASES = (
    Case("planned_current", "retired real current entrypoint", True, "current", "info"),
    Case("unplanned_current", "broken real catalog entrypoint", False, "current", "error"),
    Case("strict_current", "retired real current entrypoint", True, "strict-current", "error"),
    Case("design_failure", "real known-bad Explorer wrongly passes", True, "target", "error"),
    Case("code_gap", "real anchor disagrees with a sound regular contract", True, "target", "todo"),
    Case("owner_dropped", "real old catalog promise loses its owner", True, "target", "error"),
    Case("entrypoint_owner", "loan component claims a catalog file anchor", True, "target", "error"),
    Case("design_only_model", "real current contract declares DESIGN_ONLY=False", False, "target", "error"),
    Case("runner_model", "actual legacy runner path, never executed", False, "target", "error"),
    Case("unbound_invariant", "real valid regular contract lacks TESTED_BY", True, "target", "warn"),
    Case("responsibility_dropped", "real old loans duty is on no target component and not retired", True, "target", "error"),
)


@dataclass(frozen=True)
class Policy:
    decisions: tuple = ()

    def route(self, case):
        return dict(self.decisions).get(case.name, case.disposition)


def _wrong_decision(case, disposition):
    def apply(policy):
        return replace(policy, decisions=policy.decisions + ((case, disposition),))
    return apply


FEATURES = (
    Feature("unplanned_error_downgraded", True, ("unplanned_current",),
            _wrong_decision("unplanned_current", "info")),
    Feature("strict_error_downgraded", True, ("strict_current",),
            _wrong_decision("strict_current", "info")),
    Feature("design_error_as_todo", True, ("design_failure",),
            _wrong_decision("design_failure", "todo")),
    Feature("code_gap_as_error", True, ("code_gap",),
            _wrong_decision("code_gap", "error")),
    Feature("dropped_owner_as_todo", True, ("owner_dropped",),
            _wrong_decision("owner_dropped", "todo")),
    Feature("entrypoint_owner_as_todo", True, ("entrypoint_owner",),
            _wrong_decision("entrypoint_owner", "todo")),
    Feature("design_only_as_todo", True, ("design_only_model",),
            _wrong_decision("design_only_model", "todo")),
    Feature("runner_as_todo", True, ("runner_model",),
            _wrong_decision("runner_model", "todo")),
    Feature("untested_warning_as_gate", True, ("unbound_invariant",),
            _wrong_decision("unbound_invariant", "error")),
    Feature("dropped_responsibility_ignored", True, ("responsibility_dropped",),
            _wrong_decision("responsibility_dropped", "none")),
)


def build_explorer():
    return feature_explorer(FEATURES, max_features=1, codes="all")


def broken_variants():
    return feature_variants(FEATURES, max_features=1, codes="all")


def probe_model_and_target(root):
    """Actual ModelResult plus a fresh complete target check of the same bytes.

    Both native calls execute; the probe is never supplied to check_target as a
    verdict. Retain code_gaps and all bucket facts instead of constructing a DTO.
    """
    view = build_target_view(root, load_map(root), load_target(root))
    result = probe_regular_model(root, root / ".flowguard/models/shelf_rule.py", view=view)
    report = native.check_target(root)
    return result, report


def _unique_bucket(report, *, code, message=None, prefix=None):
    found = []
    for bucket, name in (("errors", "error"), ("todos", "todo"), ("warnings", "warn")):
        for finding in getattr(report, bucket):
            if finding.code == code and (message is None or finding.message == message) \
                    and (prefix is None or finding.message.startswith(prefix)):
                found.append(name)
    if prefix is not None and not found:
        return "none"
    buckets = set(found)
    return next(iter(buckets)) if len(buckets) == 1 else "absent-or-conflicting:" + repr(found)


def _current_case(root, case):
    stage_target(root)
    planned = case.name != "unplanned_current"
    path = root / ("shelf/loans.py" if planned else "shelf/catalog.py")
    old, new = ("advance", "advance_next") if planned else ("capacity", "capacity_next")
    path.write_text(path.read_text(encoding="utf-8").replace("def " + old + "(", "def " + new + "("), encoding="utf-8")
    if planned:
        target = load_target(root).data
        target["components"][0]["entrypoints"] = ["shelf/loans.py:advance_next"]
        target["remove"] = ["entrypoint:shelf/loans.py:advance", "flow:borrow"]
        write_json(root / ".flowguard/target/map.json", target)
        model = root / ".flowguard/target/models/shelf_rule.py"
        model.write_text(model.read_text(encoding="utf-8").replace("shelf/loans.py:advance", "shelf/loans.py:advance_next"), encoding="utf-8")
    strict = case.phase == "strict-current"
    data = load_map(root)
    findings = run_check(root, data, build_inventory(root, ignore_patterns(data), write_cache=False), strict=strict)
    relevant = [f for f in findings if f.code == "anchor_broken" and old in f.message]
    assert relevant, "fresh current fixture did not expose its broken entrypoint"
    # The real function has no strict parameter. Only cmd_check bypasses it.
    downgraded = native.moving_to_target(findings, root, data, load_target(root))
    after = [f for f in downgraded if f.code == "anchor_broken" and old in f.message]
    assert after
    if not planned:
        assert after == relevant, "unplanned Finding identities or contents changed"
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(StringIO()):
        status = map_cli.cmd_check(root, SimpleNamespace(strict=strict, json=True, limit=1000))
    actual = json.loads(output.getvalue())
    matches = [f for f in actual["findings"] if f["code"] == "anchor_broken" and old in f["message"]]
    levels = {f["level"] for f in matches}
    assert matches and status == (1 if actual["counts"]["error"] else 0)
    observed = next(iter(levels)) if len(levels) == 1 else "conflicting:" + repr(levels)
    if planned and not strict:
        assert all(f["message"].startswith("moving to target:") for f in matches)
    return observed, repr(dict(exit=status, findings=matches, direct_downgrade=after))


def observe_case(case):
    """One fresh bounded native filesystem/proof case, no fixture verdict reuse."""
    with TemporaryDirectory(prefix="target-findings-") as directory:
        root = make_project(Path(directory))
        if case.phase in ("current", "strict-current"):
            return _current_case(root, case)
        stage_target(root, with_model=case.name in {"code_gap", "design_failure", "unbound_invariant"})
        target_path = root / ".flowguard/target/map.json"
        target = load_target(root).data
        if case.name == "owner_dropped":
            target["remove"] = ["component:catalog"]
            target["components"][0]["depends_on"] = []
            write_json(target_path, target)
        elif case.name == "responsibility_dropped":
            target["components"][0]["responsibilities"] = ["lend one book at a time"]
            write_json(target_path, target)
            report = native.check_target(root)
            return _unique_bucket(report, code="owner_dropped", prefix="responsibility 'maintain loans'"), repr(report)
        elif case.name == "entrypoint_owner":
            target["components"][0]["entrypoints"].append("shelf/catalog.py:capacity")
            write_json(target_path, target)
        elif case.name == "design_only_model":
            path = root / ".flowguard/models/shelf_rule.py"
            path.write_text(path.read_text(encoding="utf-8") + "\nDESIGN_ONLY = False\n", encoding="utf-8")
        elif case.name == "runner_model":
            marker = root / "legacy-runner-was-executed.marker"
            runner = root / ".flowguard/verification/owners/legacy/run_checks.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\nraise RuntimeError('legacy runner executed')\n", encoding="utf-8")
        elif case.name in ("code_gap", "design_failure", "unbound_invariant"):
            if case.name == "code_gap":
                path = root / "shelf/loans.py"
                path.write_text(path.read_text(encoding="utf-8").replace("value + capacity()", "value + capacity() + 1"), encoding="utf-8")
            elif case.name == "design_failure":
                path = root / ".flowguard/target/models/shelf_rule.py"
                source = path.read_text(encoding="utf-8")
                assert source.count('return {"advance_twice": make(2)}') == 1
                path.write_text(source.replace('return {"advance_twice": make(2)}', 'return {"advance_twice": make(1)}'), encoding="utf-8")
            result, report = probe_model_and_target(root)
            if case.name == "unbound_invariant":
                assert result.status == "pass" and not result.problems and not result.code_gaps
                assert any(w.startswith("invariant_untested:") for w in result.warnings)
                return _unique_bucket(report, code="invariant_untested"), repr((result, report))
            assert result.problems, "native proof must expose actual failing provenance"
            if case.name == "code_gap":
                assert result.code_gaps and set(result.code_gaps) <= set(result.problems)
                messages = result.code_gaps
            else:
                assert not result.code_gaps
                assert any("known-bad variant" in p and "passed" in p for p in result.problems)
                messages = [p for p in result.problems if "known-bad variant" in p and "passed" in p]
            buckets = {_unique_bucket(report, code="model_proof", message=message) for message in messages}
            actual = next(iter(buckets)) if len(buckets) == 1 else "conflicting:" + repr(buckets)
            return actual, repr(dict(actual_ModelResult=result, actual_TargetReport=report))
        else:
            raise ValueError("undeclared native finding scenario " + case.name)
        report = native.check_target(root)
        if case.name == "runner_model":
            assert not marker.exists(), "legacy runner sentinel really executed"
        return _unique_bucket(report, code=case.name), repr(report)


def conformance():
    # Each concrete row is executed fresh once in this operation. The policy
    # feature comparison below consumes these observed report buckets; it never
    # supplies a stored verdict to a native check or skips native proof work.
    observed, facts = {}, []
    for case in CASES:
        bucket, detail = observe_case(case)
        observed[case.name] = bucket
        facts.append(Fact(case.name, bucket == case.disposition, detail))

    def review(policy):
        wrong = tuple(case.name for case in CASES if policy.route(case) != observed[case.name])
        return not wrong, wrong

    report = feature_conformance(FEATURES, Policy, review, max_features=1, codes="all")
    facts.append(Fact("actual_buckets_reject_wrong_policies", report.ok, report.format_text()))
    return CodeFactsReport(tuple(facts))
