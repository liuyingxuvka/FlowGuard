"""Target check sends design mistakes to ERROR, missing code to TO-DO and planned breakage to INFO.

Each event is one source of a finding (a CASES row). Route sends it to error,
todo, info, warn or no finding; the rules say which kind of finding goes where.
Conformance builds each case fresh on the small shelf project and reads the bucket
that the real check_target, moving_to_target and map check --strict give it.
Independent check under the parent (no project_parent_state): routing does not
start from a parent state.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map import cli as map_cli
from flowguard.map import target as native
from flowguard.map.check import run_check
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
    "design_mistakes_are_errors": [
        "tests/test_flowguard_target.py:test_dropping_a_responsibility_is_owner_dropped",
        "tests/test_flowguard_target.py:test_behaviour_target_without_a_rule_is_untied",
    ],
    "missing_code_is_todo": [
        "tests/test_flowguard_target.py:test_target_real_proof_dispositions_and_hard_boundaries",
    ],
    "only_changed_subjects_move": [
        "tests/test_flowguard_target.py:test_unplanned_catalog_breakage_stays_an_error_with_a_target",
        "tests/test_flowguard_target.py:test_copied_but_unchanged_entry_stays_an_error",
    ],
    "strict_never_moves": [
        "tests/test_flowguard_target.py:test_change_marks_only_planned_breakage_and_keeps_tests",
    ],
    "old_findings_do_not_block": [
        "tests/test_flowguard_target.py:test_old_findings_of_unchanged_models_do_not_block",
    ],
    "warnings_never_block": [
        "tests/test_flowguard_target.py:test_target_check_warns_about_debts_it_makes_stale",
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
    Case("behaviour_without_rule", "target adds a loans entrypoint and changes no model rule", True, "target", "error"),
    Case("old_finding_in_unchanged_model", "a model the target imports but does not change keeps an old uncovered "
         "invariant over unchanged code", True, "target", "warn"),
    Case("debt_made_stale", "the target gives catalog tests, so its accepted untested_component debt matches nothing",
         True, "target", "warn"),
    Case("unchanged_copy_breakage", "target copies loans unchanged; the real current loans entrypoint breaks", True,
         "current", "error"),
)


# Each known-bad variant routes one case to the wrong bucket.
DEFECTS = {
    "unplanned_error_downgraded": ("unplanned_current", "info"),
    "strict_error_downgraded": ("strict_current", "info"),
    "design_error_as_todo": ("design_failure", "todo"),
    "code_gap_as_error": ("code_gap", "error"),
    "dropped_owner_as_todo": ("owner_dropped", "todo"),
    "entrypoint_owner_as_todo": ("entrypoint_owner", "todo"),
    "design_only_as_todo": ("design_only_model", "todo"),
    "runner_as_todo": ("runner_model", "todo"),
    "untested_warning_as_gate": ("unbound_invariant", "error"),
    "dropped_responsibility_ignored": ("responsibility_dropped", "none"),
    "untied_goal_accepted": ("behaviour_without_rule", "none"),
    "unchanged_subject_downgraded": ("unchanged_copy_breakage", "info"),
    "old_finding_blocks": ("old_finding_in_unchanged_model", "error"),
    "stale_debt_hidden": ("debt_made_stale", "none"),
}
BY_NAME = {case.name: case for case in CASES}
DESIGN = {"design_failure", "owner_dropped", "responsibility_dropped", "entrypoint_owner", "design_only_model",
          "runner_model", "behaviour_without_rule"}
CHANGED = {"planned_current": "info", "unplanned_current": "error", "unchanged_copy_breakage": "error"}


@dataclass(frozen=True)
class State:
    event: str = ""
    bucket: str = ""


class Route:
    name = "Route"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        bucket = BY_NAME[event].disposition
        if self.defect and DEFECTS[self.defect][0] == event:
            bucket = DEFECTS[self.defect][1]
        return (FunctionResult(bucket, State(event, bucket), label=event),)


def _rule(name, events, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in events or predicate(state)
                     else InvariantResult.fail(message))


INVARIANTS = (
    _rule("design_mistakes_are_errors", DESIGN, lambda state: state.bucket == "error",
          "a design mistake of the target was not an ERROR"),
    _rule("missing_code_is_todo", {"code_gap"}, lambda state: state.bucket == "todo",
          "code the target still needs was not a TO-DO"),
    _rule("only_changed_subjects_move", set(CHANGED), lambda state: state.bucket == CHANGED[state.event],
          "breakage was moved to target although the target does not change its subject, or planned breakage was not"),
    _rule("strict_never_moves", {"strict_current"}, lambda state: state.bucket == "error",
          "map check --strict downgraded a current error"),
    _rule("old_findings_do_not_block", {"old_finding_in_unchanged_model"}, lambda state: state.bucket == "warn",
          "an old finding of a model the target does not change blocked the target"),
    _rule("warnings_never_block", {"unbound_invariant", "debt_made_stale"}, lambda state: state.bucket == "warn",
          "an untested rule or a stale debt was not a warning"),
)


def _explorer(defect=""):
    return Explorer(Workflow((Route(defect),)), (State(),), tuple(BY_NAME), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in DEFECTS}


OLD_CONTRACT = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "shelf_old"
PARENT = "shelf_rule"
IMPLEMENTED_BY = {"Capacity": "shelf/loans.py:advance"}
class Capacity:
    name = "Capacity"
    def __init__(self, value=1): self.value = value
    def apply(self, event, state):
        return (FunctionResult(self.value, self.value, label="capacity"),)
ONE = Invariant("one_copy", "capacity is one", lambda s, t:
    InvariantResult.pass_() if s in (0, 1) else InvariantResult.fail("not one"))
ANY = Invariant("never_negative", "capacity is never negative", lambda s, t:
    InvariantResult.pass_() if s >= 0 else InvariantResult.fail("negative"))
def make(value):
    return Explorer(Workflow((Capacity(value),)), (0,), ("capacity",), invariants=(ONE, ANY),
                    max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {"two_copies": make(2)}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Capacity"], root=Path.cwd())(0)
    return CodeFactsReport((Fact("native_capacity", actual == 1, repr(actual)),))
'''


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
    planned = case.name not in ("unplanned_current", "unchanged_copy_breakage")
    path = root / ("shelf/catalog.py" if case.name == "unplanned_current" else "shelf/loans.py")
    old, new = ("capacity", "capacity_next") if case.name == "unplanned_current" else ("advance", "advance_next")
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
    if case.name == "unplanned_current":
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
        stage_target(root, with_model=case.name in {"code_gap", "design_failure", "unbound_invariant", "old_finding_in_unchanged_model"})
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
        elif case.name == "old_finding_in_unchanged_model":
            # A current child of shelf_rule with an old uncovered invariant over unchanged code: the target
            # changes shelf_rule, so target check selects the child without changing it.
            (root / ".flowguard/models/shelf_old.py").write_text(OLD_CONTRACT, encoding="utf-8")
            report = native.check_target(root)
            return _unique_bucket(report, code="old_finding", prefix="uncovered_invariant"), repr(report)
        elif case.name == "debt_made_stale":
            current = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
            current["accepted_debts"] = [dict(code="untested_component", component="catalog",
                                              reason="catalog is covered through the loans tests")]
            write_json(root / ".flowguard/map.json", current)
            catalog = dict(next(c for c in current["components"] if c["id"] == "catalog"), tests=["tests/test_shelf.py"])
            catalog.pop("status", None)
            target["components"].append(catalog)
            write_json(target_path, target)
            report = native.check_target(root, models=False)
            return _unique_bucket(report, code="debt_stale", prefix="accepted debt matches no finding"), repr(report)
        elif case.name == "behaviour_without_rule":
            target["components"][0]["entrypoints"].append("shelf/loans.py:hold")
            write_json(target_path, target)
            report = native.check_target(root, models=False)
            return _unique_bucket(report, code="target_goal_untied", prefix="the target changes a promise"), repr(report)
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


class RealRouting:
    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, step):
        bucket, _detail = observe_case(BY_NAME[step.function_input])
        self.state = State(step.function_input, bucket)
        return ReplayObservation(function_name=step.function_name, observed_output=bucket, observed_state=self.state)

    def observe_state(self):
        return self.state


def conformance():
    # Every case is built fresh and checked by the real code; no stored verdict is reused.
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=RealRouting(), invariants=INVARIANTS,
                            rules=(projected_output_matches(), projected_state_matches()))
        if not last.ok:
            return last
    return last
