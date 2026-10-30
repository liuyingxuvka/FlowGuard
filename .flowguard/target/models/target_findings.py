"""Target check sends design mistakes to ERROR, missing code to TO-DO and planned breakage to INFO.

Each event is one source of a finding (a CASES row). Route sends it to error,
todo, info, warn or no finding; the rules say which kind of finding goes where.
Conformance builds each case fresh on the small shelf project and reads the bucket
that the real check_target, moving_to_target and map check --strict give it.
Independent check under the parent (no project_parent_state): routing does not
start from a parent state.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.map import cli as map_cli
from flowguard.map import target as native
from flowguard.map.check import run_check
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import ignore_patterns, load_map
from flowguard.map.targetfile import build_target_view, load_target
from _target_fixture import REGULAR_CONTRACT, make_project, stage_target, write_json, probe_regular_model

MODEL_ID = "target_findings"
PARENT = "target_life_cycle"
OUTPUTS = {"bucket": ("error", "todo", "info", "warn", "none")}
IMPLEMENTED_BY = {
    "Downgrade": "flowguard/map/target.py:moving_to_target",
    "Classify": "flowguard/map/target.py:check_target",
}
USES = {
    'KeepOwners': 'flowguard/map/lint.py:dropped_owner_findings',
    'CmdCheck': 'flowguard/map/cli.py:cmd_check',
    'Main': 'flowguard/map/cli.py:main',
    'RunModelInProcess': 'flowguard/map/proof.py:run_model_in_process',
    'TargetMain': 'flowguard/map/target.py:main',
    'Impact': 'flowguard/map/impact.py:compute_impact',
    'ChangedFiles': 'flowguard/map/impact.py:changed_files',
}
TESTED_BY = {
    'port_change_needs_parent': [
        'tests/test_target_life_cycle.py:test_port_change_without_parent_is_an_error',
        'tests/test_target_life_cycle.py:test_changed_port_fails_short_form_consumer',
    ],
    'design_mistakes_are_errors': [
        'tests/test_target_life_cycle.py:test_dropping_a_responsibility_is_owner_dropped',
        'tests/test_target_life_cycle.py:test_existing_similar_duty_does_not_hide_a_dropped_responsibility',
    ],
    'missing_code_is_todo': ['tests/test_target_life_cycle.py:test_target_check_reports_unwritten_code_as_todo'],
    'only_changed_subjects_move': ['tests/test_target_life_cycle.py:test_copied_but_unchanged_entry_stays_an_error'],
    'strict_never_moves': ['tests/test_target_life_cycle.py:test_change_marks_only_planned_breakage_and_keeps_tests'],
    'old_findings_do_not_block': ['tests/test_target_life_cycle.py:test_old_findings_of_unchanged_models_do_not_block',
                                 'tests/test_target_life_cycle.py:test_promote_blocks_failure_of_model_reaching_changed_file'],
    'warnings_never_block': [
        'tests/test_target_life_cycle.py:test_target_check_warns_about_debts_it_makes_stale',
        'tests/test_target_life_cycle.py:test_reworded_duty_is_not_owner_dropped',
    ],
    'noop_target_is_an_error': ['tests/test_target_life_cycle.py:test_unchanged_target_is_target_noop'],
}


@dataclass(frozen=True)
class Case:
    name: str
    provenance: str
    replaced: bool
    phase: str
    disposition: str
    gap: str = "no_rule_change"
    port: str | None = None
    parent_in_target: bool = False


# These are concrete promises about ten fact origins, not code-set copies.
CASES = (
    Case("no_finding", "a confirmed unchanged project has no findings", True, "target", "none"),
    Case("planned_current", "retired real current entrypoint", True, "current", "info"),
    Case("unplanned_current", "broken real catalog entrypoint", False, "current", "error"),
    Case("strict_current", "retired real current entrypoint", True, "strict-current", "error"),
    Case("design_failure", "real known-bad Explorer wrongly passes", True, "target", "error"),
    Case("code_gap", "real anchor disagrees with a sound regular contract", True, "target", "todo"),
    Case("owner_dropped", "real old catalog promise loses its owner", True, "target", "error"),
    Case("owner_reworded", "a responsibility reworded with the same words is advice, not owner_dropped", True, "target", "warn"),
    Case("entrypoint_owner", "loan component claims a catalog file anchor", True, "target", "error"),
    Case("unbound_invariant", "real valid regular contract lacks TESTED_BY", True, "target", "warn"),
    Case("responsibility_dropped", "real old loans duty is on no target component and not retired", True, "target", "error"),
    Case("behaviour_without_rule", "target adds a loans entrypoint and changes no model rule", True, "target", "error"),
    Case("old_finding_in_unchanged_model", "a model the target imports but does not change keeps an old uncovered "
         "invariant over unchanged code", True, "target", "warn"),
    Case("reaches_changed_file", "an unchanged renewal model reaches the uncommitted shared capacity edit", False, "target", "error"),
    Case("debt_made_stale", "the target gives catalog tests, so its accepted untested_component debt matches nothing",
         True, "target", "warn"),
    Case("unchanged_copy_breakage", "target copies loans unchanged; the real current loans entrypoint breaks", True,
         "current", "error"),
    Case("port_parent_missing", "a target child output changes without its parent", True, "target", "error"),
    Case("port_consumer_unhandled", "a target producer output changes; a short-form consumer outside the target never receives the new value", True, "target", "error", port="escalated"),
    Case("child_start_new_value", "a sibling starts at a newly received value it does not read", True, "target", "warn"),
)


# Each known-bad variant routes one case to the wrong bucket.
DEFECTS = {
    "reworded_is_owner_dropped": ("owner_reworded", "error"),
    "sibling_start_blocks": ("child_start_new_value", "error"),
    "consumer_failure_is_old": ("port_consumer_unhandled", "warn"),
    "parent_missing_is_todo": ("port_parent_missing", "todo"),
    "unplanned_error_downgraded": ("unplanned_current", "info"),
    "strict_error_downgraded": ("strict_current", "info"),
    "design_error_as_todo": ("design_failure", "todo"),
    "code_gap_as_error": ("code_gap", "error"),
    "dropped_owner_as_todo": ("owner_dropped", "todo"),
    "entrypoint_owner_as_todo": ("entrypoint_owner", "todo"),
    "untested_warning_as_gate": ("unbound_invariant", "error"),
    "dropped_responsibility_ignored": ("responsibility_dropped", "none"),
    "untied_goal_accepted": ("behaviour_without_rule", "none"),
    "unchanged_subject_downgraded": ("unchanged_copy_breakage", "info"),
    "old_finding_blocks": ("old_finding_in_unchanged_model", "error"),
    "reached_failure_is_old": ("reaches_changed_file", "warn"),
    "stale_debt_hidden": ("debt_made_stale", "none"),
}
NATIVE_CASES=CASES
CASES += tuple(Case('gap_'+gap,'received gap',True,'target',bucket,gap) for gap,bucket in (('expected_gap','todo'),('no_gap','warn'),('moved_only','info'),('no_rule_change','info')))
CASES += (Case('port_unchanged','received port',True,'target','none',port='unchanged'),Case('port_uncertain','received port',True,'target','warn',port='uncertain'),Case('port_parent_present','received port',True,'target','info',port='escalated',parent_in_target=True),Case('noop_target','unchanged target',True,'target','error'))
BY_NAME = {case.name: case for case in CASES}
DESIGN = {"design_failure", "owner_dropped", "responsibility_dropped", "entrypoint_owner", "behaviour_without_rule"}
CHANGED = {"planned_current": "info", "unplanned_current": "error", "unchanged_copy_breakage": "error"}


@dataclass(frozen=True)
class State:
    event: str = ""
    bucket: str = "none"
    parent_in_target: bool = False
    gap: str = "no_rule_change"
    port: str | None = "unchanged"


class Take:
    name='Take'
    reads=()
    writes=('event','parent_in_target','gap','port')
    def apply(self,event,state):
        case=BY_NAME[event]
        gap='expected_gap' if event=='code_gap' else case.gap
        port='escalated' if event=='port_parent_missing' else case.port
        return (FunctionResult(event,replace(state,event=event,parent_in_target=case.parent_in_target,gap=gap,port=port),label=port if port is not None else gap),)
class Route:
    name='Route'
    reads=('event','parent_in_target','gap','port')
    writes=('bucket',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        if state.event.startswith('gap_') or state.event=='code_gap':
            bucket={'expected_gap':'todo','no_gap':'warn','moved_only':'info','no_rule_change':'info'}[state.gap]
        elif state.port=='escalated': bucket='info' if state.parent_in_target else 'error'
        elif state.port=='uncertain':bucket='warn'
        elif state.port=='unchanged':bucket='none'
        else:bucket=BY_NAME[event].disposition
        if self.defect=='passes_unchanged_copy' and event=='noop_target':bucket='none'
        elif self.defect and self.defect in DEFECTS and DEFECTS[self.defect][0]==event:bucket=DEFECTS[self.defect][1]
        return (FunctionResult(bucket,replace(state,bucket=bucket),label=bucket),)


def _rule(name, events, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in events or predicate(state)
                     else InvariantResult.fail(message))


INVARIANTS = (
    _rule("noop_target_is_an_error", {"noop_target"}, lambda state: state.bucket == "error", "an unchanged target must fail check"),
    _rule("port_change_needs_parent", {"port_parent_missing", "port_parent_present", "port_consumer_unhandled"}, lambda state: state.bucket == ("info" if state.parent_in_target else "error"),
          "a changed output that its parent or a consumer outside the target does not receive must be ERROR"),
    _rule("design_mistakes_are_errors", DESIGN, lambda state: state.bucket == "error",
          "a design mistake of the target was not an ERROR"),
    _rule("missing_code_is_todo", {"code_gap", "gap_expected_gap"}, lambda state: state.gap != "expected_gap" or state.bucket == "todo",
          "code the target still needs was not a TO-DO"),
    _rule("only_changed_subjects_move", set(CHANGED), lambda state: state.bucket == CHANGED[state.event],
          "breakage was moved to target although the target does not change its subject, or planned breakage was not"),
    _rule("strict_never_moves", {"strict_current"}, lambda state: state.bucket == "error",
          "map check --strict downgraded a current error"),
    _rule("old_findings_do_not_block", {"old_finding_in_unchanged_model", "reaches_changed_file"},
          lambda state: state.bucket == ("error" if state.event == "reaches_changed_file" else "warn"),
          "findings of models whose files and reached files are unchanged since the base are WARN old_finding; "
          "a model that reaches a changed file is judged as release judges it"),
    _rule("warnings_never_block", {"unbound_invariant", "debt_made_stale", "child_start_new_value", "owner_reworded"}, lambda state: state.bucket == "warn",
          "an untested rule, a stale debt, a sibling start or a reworded responsibility is a warning, never a block"),
)


def _explorer(defect=""):
    return Explorer(Workflow((Take(), Route(defect))), (State(),State(bucket="error")), tuple(BY_NAME), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {
        'reworded_is_owner_dropped': _explorer('reworded_is_owner_dropped'),
        'parent_missing_is_todo': _explorer('parent_missing_is_todo'),
        'unplanned_error_downgraded': _explorer('unplanned_error_downgraded'),
        'strict_error_downgraded': _explorer('strict_error_downgraded'),
        'design_error_as_todo': _explorer('design_error_as_todo'),
        'code_gap_as_error': _explorer('code_gap_as_error'),
        'dropped_owner_as_todo': _explorer('dropped_owner_as_todo'),
        'entrypoint_owner_as_todo': _explorer('entrypoint_owner_as_todo'),
        'untested_warning_as_gate': _explorer('untested_warning_as_gate'),
        'dropped_responsibility_ignored': _explorer('dropped_responsibility_ignored'),
        'untied_goal_accepted': _explorer('untied_goal_accepted'),
        'unchanged_subject_downgraded': _explorer('unchanged_subject_downgraded'),
        'old_finding_blocks': _explorer('old_finding_blocks'),
        'reached_failure_is_old': _explorer('reached_failure_is_old'),
        'stale_debt_hidden': _explorer('stale_debt_hidden'),
        'passes_unchanged_copy': _explorer('passes_unchanged_copy'),
        'consumer_failure_is_old': _explorer('consumer_failure_is_old'),
        'sibling_start_blocks': _explorer('sibling_start_blocks'),
    }


OLD_CONTRACT = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "shelf_old"
from shelf_bridge import RULE as CURRENT_RULE
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
        if case.name == "reaches_changed_file":
            from _target_fixture import reached_failure_target
            from flowguard.map.impact import changed_files, compute_impact
            root = reached_failure_target(Path(directory))
            data = load_map(root)
            inv = build_inventory(root, ignore_patterns(data), write_cache=False)
            impact = compute_impact(root, data, inv, changed_files(root, "HEAD", data=data, inv=inv), base="HEAD")
            report = native.check_target(root, impact=impact)
            findings = [(bucket, finding) for bucket, items in (("error", report.errors), ("todo", report.todos), ("warn", report.warnings))
                        for finding in items if finding.node == "model renew_rule" and finding.code in {"model_proof", "old_finding"}]
            buckets = {bucket for bucket, _ in findings}
            return next(iter(buckets)) if len(buckets) == 1 else "absent-or-conflicting", repr(report)
        if case.name == "child_start_new_value":
            from _target_fixture import slicing_project
            root = slicing_project(Path(directory))
            report = native.check_target(root)
            return _unique_bucket(report, code="child_start_new_value"), repr(report)
        if case.name == "port_consumer_unhandled":
            from _target_fixture import make_port_project, call_target
            root = Path(directory)
            make_port_project(root, "short_consumer")
            assert map_cli.main(["confirm", "all", "--root", str(root)]) == 0
            assert call_target(root, "start", "extend lending outputs") == 0
            assert call_target(root, "add", "lending") == 0
            path = root / ".flowguard/target/models/lending.py"
            path.write_text(path.read_text().replace('("lent","refused")}', '("lent","refused","waitlisted")}'))
            report = native.check_target(root)
            return _unique_bucket(report, code="port_changed_consumer_unhandled"), repr(report)
        if case.name == "port_parent_missing":
            from _target_fixture import make_port_project, call_target
            root = Path(directory)
            make_port_project(root)
            assert call_target(root, "start", "extend lending outputs") == 0
            assert call_target(root, "add", "lending") == 0
            path = root / ".flowguard/target/models/lending.py"
            path.write_text(path.read_text().replace('("lent","refused")}', '("lent","refused","waitlisted")}'))
            report = native.check_target(root, models=False)
            return _unique_bucket(report, code="port_changed_parent_missing"), repr(report)
        root = make_project(Path(directory))
        if case.phase in ("current", "strict-current"):
            return _current_case(root, case)
        if case.name == "no_finding":
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                map_cli.main(["confirm", "all", "--root", str(root)])
            stage_target(root)
            report = native.check_target(root)
            return ("none" if not report.errors and not report.todos and not report.warnings else "unexpected-findings"), repr(report)
        stage_target(root, with_model=case.name in {"code_gap", "design_failure", "unbound_invariant", "old_finding_in_unchanged_model"})
        target_path = root / ".flowguard/target/map.json"
        target = load_target(root).data
        if case.name == "owner_dropped":
            target["remove"] = ["component:catalog"]
            target["components"][0]["depends_on"] = []
            write_json(target_path, target)
        elif case.name == "owner_reworded":
            target["components"][0]["responsibilities"] = ["maintain the active loans"]
            write_json(target_path, target)
            report = native.check_target(root)
            matches = [
                (bucket, finding.code)
                for bucket, findings in (("error", report.errors), ("todo", report.todos), ("warn", report.warnings))
                for finding in findings
                if finding.code in {"owner_dropped", "responsibility_reworded"}
                and finding.message.startswith("responsibility 'maintain loans'")
            ]
            if len(matches) != 1:
                observed = "absent-or-conflicting:" + repr(matches)
            else:
                observed, code = matches[0]
                if observed == "warn" and code != "responsibility_reworded":
                    observed = "wrong-warning-code:" + code
            return observed, repr(report)
        elif case.name == "responsibility_dropped":
            target["components"][0]["responsibilities"] = ["lend one book at a time"]
            write_json(target_path, target)
            report = native.check_target(root)
            return _unique_bucket(report, code="owner_dropped", prefix="responsibility 'maintain loans'"), repr(report)
        elif case.name == "old_finding_in_unchanged_model":
            # A current child of shelf_rule with an old uncovered invariant over unchanged code: the target
            # changes shelf_rule, so target check selects the child without changing it.
            for logical in (".flowguard/models/shelf_rule.py", ".flowguard/target/models/shelf_rule.py"):
                path = root / logical
                path.write_text(path.read_text().replace('PARENT = "loans"', 'PARENT = "shelf_bridge"'))
            bridge = REGULAR_CONTRACT.replace('MODEL_ID = "shelf_rule"', 'MODEL_ID = "shelf_bridge"\nfrom shelf_rule import RULE as PARENT_RULE').replace('PARENT = "loans"', 'PARENT = "shelf_old"')
            (root / ".flowguard/models/shelf_bridge.py").write_text(bridge, encoding="utf-8")
            (root / ".flowguard/models/shelf_old.py").write_text(OLD_CONTRACT.replace('PARENT = "shelf_rule"', 'PARENT = "loans"'), encoding="utf-8")
            report = native.check_target(root)
            return _unique_bucket(report, code="old_finding", prefix="uncovered_invariant"), repr(report)
        elif case.name == "debt_made_stale":
            current = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
            current["accepted_debts"] = [dict(code="untested_component", component="catalog",
                                              reason="catalog is covered through the loans tests", expires="9999-12-31")]
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
        elif case.name in ("code_gap", "design_failure", "unbound_invariant"):
            if case.name == "code_gap":
                path = root / "shelf/loans.py"
                path.write_text(path.read_text(encoding="utf-8").replace("value + capacity()", "value + capacity() + 1"), encoding="utf-8")
            elif case.name == "design_failure":
                path = root / ".flowguard/target/models/shelf_rule.py"
                source = path.read_text(encoding="utf-8")
                assert source.count('return {"advance_twice": make(2)}') == 1
                path.write_text(source.replace('return {"advance_twice": make(2)}', 'return {"advance_twice": make(1)}'), encoding="utf-8")
            if case.name == "unbound_invariant":
                path = root / ".flowguard/target/models/shelf_rule.py"
                source = path.read_text(encoding="utf-8").replace(
                    "invariants=(RULE,)", "invariants=(RULE, SECOND)")
                source += ('\nTESTED_BY = {"one_loan_step": ["tests/test_shelf.py:test_advance"]}\n'
                           'SECOND = Invariant("at_most_one", "no double advance", lambda s,t: s <= 1)\n')
                path.write_text(source, encoding="utf-8")
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
    facts=[]
    for case in NATIVE_CASES:
        bucket,detail=observe_case(case)
        facts.append(Fact(case.name,bucket==case.disposition,detail))
    with TemporaryDirectory(prefix='fg-noop-bucket-') as directory:
        root=make_project(Path(directory))
        from _target_fixture import call_target
        call_target(root,'start','unchanged copy');call_target(root,'add','component:loans')
        report=native.check_target(root,models=False)
        facts.append(Fact('noop_target',any(f.code=='target_noop' for f in report.errors),repr(report)))
    return CodeFactsReport(tuple(facts))

HANDOFF = {'gap_lines': {'gap': 'gap'}, 'port_escalation': {'port': ('port', {'unchanged': 'unchanged', 'escalated': 'escalated', 'uncertain': 'uncertain', 'none': None})}}

KEEPS = ('event', 'parent_in_target', 'bucket')
