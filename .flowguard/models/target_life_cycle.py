"""One target at a time; promote only a clean target and leave current equal to the merge.

Protect single-target storage, clean-only promotion and target removal through real
target commands and filesystem observations. HANDOFF receives outputs from the
child models: target check (target_findings) turns a written target into a report,
and only a clean report reaches promotion (target_promotion, which starts from this
model's clean checked states and owns the merge rules).
"""
from contextlib import chdir, redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map import target as native
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.map.mapfile import load_map
from flowguard.map.proof import run_model_in_process
from flowguard.map.targetfile import build_target_view, load_target
from _target_fixture import REGULAR_CONTRACT, make_project, stage_target, write_json, probe_regular_model, call_target

MODEL_ID = "target_life_cycle"
PARENT = "map-target"
IMPLEMENTED_BY = {'Target': 'flowguard/map/target.py:main', 'Start': 'flowguard/map/target.py:start_target', 'Drop': 'flowguard/map/target.py:drop_target'}
USES = {
    'MovingToTarget': 'flowguard/map/target.py:moving_to_target',
}
NOT_MODELED = {'flowguard/map/target.py:add_to_target': 'requires an open target and calls _add, which target_add anchors'}
TESTED_BY = {'linked_request_done_at_promote': ['tests/test_requests.py:test_promote_marks_linked_request_done'], 'promote_runs_one_full_check': ['tests/test_target_life_cycle.py:test_target_check_runs_no_pytest_and_promote_runs_one_check'], 'one_target_at_a_time': ['tests/test_target_life_cycle.py:test_target_start_add_drop_and_read_line'], 'promote_only_when_clean': ['tests/test_target_life_cycle.py:test_target_small_promotion_preserves_map_and_model_bytes', 'tests/test_cli_main.py:test_json_verdict_only_with_flag'], 'check_runs_own_bound_tests_after_code': ['tests/test_target_life_cycle.py:test_target_check_runs_no_pytest_and_promote_runs_one_check', 'tests/test_target_life_cycle.py:test_target_check_runs_own_bound_tests_after_code']}

PROGRAMS = (
    ("json_error", ("START", "ADD_COMPONENT", "EDIT_ERROR", "PROMOTE")),
    ("storage", ("START", "ADD_COMPONENT", "ADD_MODEL", "START_AGAIN", "CHECK", "DROP_PREVIEW", "DROP_YES")),
    ("todo", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "CHECK", "PROMOTE")),
    ("error", ("START", "ADD_COMPONENT", "EDIT_ERROR", "CHECK", "PROMOTE")),
    ("clean", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "WRITE_CODE", "CHECK", "PROMOTE")),
    ("linked_request", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "WRITE_CODE", "CHECK", "PROMOTE")),
    # A copied component and nothing else changed: CHECK reports target_noop, PROMOTE is refused.
    ("noop", ("START", "ADD_COMPONENT", "CHECK", "PROMOTE")),
    ("planned", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_PLANNED", "CHECK", "DROP_YES")),
    ("warned", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_WARNING", "CHECK", "DROP_YES")),
    ("no_target", ("PROMOTE",)),
)


@dataclass(frozen=True)
class State:
    scenario: str
    position: int = 0
    target_count: int = 0
    target_revision: int = 0
    current_map_revision: int = 0
    current_model_revision: int = 0
    expected_map_revision: int = 0
    expected_model_revision: int = 0
    errors: int = 0
    todos: int = 0
    action: str = ""
    added: str = "copied"
    bucket: str = "none"
    promotion: str = ""
    changed: bool = False      # the target differs from the current tree (a comment-only model copy does not)
    bound_test_runs: int = 0
    code_written: bool = False
    linked_done: bool = False
    unlinked_done: bool = False


def _revisions(state):
    return (state.target_count, state.target_revision,
            state.current_map_revision, state.current_model_revision)


HANDOFF = {'target_add': {'added': 'added'}, 'target_findings': {'bucket': 'bucket'}, 'target_promotion': {'outcome': 'promotion'}}
KEEPS = ("scenario", "position", "changed", "expected_map_revision", "bound_test_runs", "code_written", "linked_done", "unlinked_done")

class Advance:
    name = "Advance"
    writes = ("position", "target_count", "target_revision", "current_map_revision", "current_model_revision",
              "expected_map_revision", "expected_model_revision", "errors", "todos", "action", "added", "bucket", "promotion", "changed", "bound_test_runs", "code_written", "linked_done", "unlinked_done")
    def __init__(self, defect=""):
        self.defect = defect
    def apply(self, event, state):
        program = dict(PROGRAMS)[state.scenario]
        if state.position == len(program):
            return (FunctionResult("done", state, label="done"),)
        action = program[state.position]
        new = replace(state, position=state.position+1, action=action)
        output = "ok"
        if action == "START":
            new = replace(new, target_count=1, target_revision=1)
        elif action == "START_AGAIN":
            if self.defect == "second_target":
                new = replace(new, target_count=2, target_revision=state.target_revision+1)
            output = "refused"
        elif action in ("ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "EDIT_ERROR", "EDIT_PLANNED", "EDIT_WARNING"):
            new = replace(new, target_revision=state.target_revision+1)
            if action in ("ADD_COMPONENT", "ADD_MODEL"):
                new=replace(new,added="moved" if state.scenario=="storage" and action=="ADD_MODEL" else "copied")
                output=new.added
            if action == "ADD_MODEL":
                new = replace(new, expected_model_revision=1)
            elif action == "EDIT_MISSING":
                new = replace(new, todos=1, changed=True)
            elif action == "EDIT_ERROR":
                new = replace(new, errors=1, changed=True)
            elif action in ("EDIT_PLANNED", "EDIT_WARNING"):
                new = replace(new, changed=True)
        elif action == "WRITE_CODE":
            new = replace(new, todos=0, code_written=True)
        elif action == "CHECK":
            # One received verdict per finite native program, not a replay of
            # target_findings' routing or gap/port details.
            bucket = {"storage":"error","todo":"todo","error":"error","clean":"none","linked_request":"none","noop":"error","planned":"info","warned":"warn"}[state.scenario]
            new = replace(new, bucket=bucket, errors=int(bucket == "error"), todos=int(bucket == "todo"))
            output = bucket
            runs = int(state.code_written)
            if self.defect == "check_runs_bound_tests":
                runs = 1
            elif self.defect == "check_skips_tests_after_code":
                runs = 0
            new = replace(new, bound_test_runs=state.bound_test_runs+runs)
        elif action == "DROP_PREVIEW":
            output = "refused"
        elif action == "DROP_YES":
            new = replace(new, target_count=0)
        elif action == "PROMOTE":
            outcome = ("no_target" if not state.target_count else "refused" if (state.errors or state.todos) and self.defect != "unclean_promote" else "promoted")
            new = replace(new, promotion=outcome)
            output = outcome
            if outcome == "promoted":
                new = replace(new, target_count=0, expected_map_revision=state.target_revision,
                              current_map_revision=state.target_revision, current_model_revision=state.expected_model_revision,
                              bound_test_runs=state.bound_test_runs+(2 if self.defect == "promote_checks_twice" else 1),
                              linked_done=state.scenario == "linked_request" and self.defect != "promote_leaves_request_open")
        return (FunctionResult(output, new, label=action),)


def _previous(state, trace):
    return trace.steps[-1].old_state if trace and trace.steps else state


def _holds(condition, message):
    return InvariantResult.pass_() if condition else InvariantResult.fail(message)


INVARIANTS = (
    Invariant("linked_request_done_at_promote", "successful promotion completes linked non-part requests through an immutable record; unrelated and partial requests stay open",
              lambda s,t: _holds(s.scenario != "linked_request" or s.action != "PROMOTE" or s.promotion != "promoted" or s.linked_done and not s.unlinked_done, "linked request was not recorded as done")),
    Invariant("check_runs_own_bound_tests_after_code", "design CHECK runs the target models bound tests only after their code changed since target start",
              lambda s,t: _holds(s.action != "CHECK" or s.bound_test_runs == _previous(s,t).bound_test_runs + (1 if s.code_written else 0), "CHECK bound test phase mismatch")),
    Invariant("promote_runs_one_full_check", "a clean promotion runs its full bound check once",
              lambda s,t: _holds(s.action != "PROMOTE" or s.promotion != "promoted" or s.bound_test_runs == _previous(s,t).bound_test_runs+1, "PROMOTE repeated its full check")),
    Invariant("one_target_at_a_time", "a second start refuses without any revision change",
              lambda s,t: _holds(s.action != "START_AGAIN" or _revisions(s) == _revisions(_previous(s,t)), "second start replaced an existing target")),
    Invariant("promote_only_when_clean", "ERROR and TODO each block all promotion writes",
              lambda s,t: _holds(s.action != "PROMOTE" or not (s.errors or s.todos) or s.promotion == "refused" and _revisions(s) == _revisions(_previous(s,t)), "an unclean target was promoted")),
)


def _explorer(defect=""):
    return Explorer(Workflow((Advance(defect),)),
                    tuple(State(name) for name, _ in PROGRAMS), ("advance",),
                    invariants=INVARIANTS, max_sequence_length=7, progress_steps=0)





def build_explorer():
    return _explorer()


def broken_variants():
    return {name:_explorer(name) for name in ("check_runs_bound_tests","check_skips_tests_after_code","promote_checks_twice","second_target","unclean_promote","promote_leaves_request_open")}


# This is an executable regular contract, not a runner, DTO or design-only model.
# Its deliberate lack of binding produces a genuine fixture WARN, recorded in
# observations. It invokes the actual shelf anchor to obtain its conformance.










def edit_missing_method(root):
    path = root / ".flowguard/target/map.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    loans = target["components"][0]
    loans["entrypoints"].append("shelf/loans.py:hold")
    loans["responsibilities"].append("record a reservation")
    target["remove"].append("flow:borrow")
    write_json(path, target)
    model = root / ".flowguard/target/models/shelf_rule.py"
    if model.is_file():      # the new entrypoint is tied to a new known-bad variant of the target model
        source = model.read_text(encoding="utf-8")
        model.write_text(source.replace('return {"advance_twice": make(2)}',
                                        'return {"advance_twice": make(2), "advance_thrice": make(3)}'), encoding="utf-8")


def write_method(root):
    path = root / "shelf/loans.py"
    path.write_text(path.read_text(encoding="utf-8") +
                    "\ndef hold(member):\n    return member\n", encoding="utf-8")


def snapshot(root):
    """Exact contents, including presence; missing files never equal empty bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}




def _native_replay(scenario, program):
    facts = []
    with TemporaryDirectory(prefix="target-lifecycle-") as directory:
        root = make_project(Path(directory))
        for action in program:
            before = snapshot(root)
            code = None
            if action == "START":
                code = call_target(root, "start", "extend the shelf")
                ok = code == 0 and (root / ".flowguard/target/map.json").is_file()
            elif action == "ADD_COMPONENT":
                code = call_target(root, "add", "component:loans")
                ok = code == 0 and load_target(root).data["components"][0]["id"] == "loans"
            elif action == "ADD_MODEL":
                code = call_target(root, "add", "model:shelf_rule")
                path = root / ".flowguard/target/models/shelf_rule.py"
                ok = code == 0 and path.read_bytes() == (root / ".flowguard/models/shelf_rule.py").read_bytes()
                path.write_text(path.read_text(encoding="utf-8") + "\n# revised target shelf contract\n", encoding="utf-8")
            elif action == "START_AGAIN":
                code = call_target(root, "start", "second target")
                ok = code == 2 and snapshot(root) == before
            elif action == "EDIT_MISSING":
                edit_missing_method(root)
                ok = "shelf/loans.py:hold" in load_target(root).data["components"][0]["entrypoints"]
            elif action == "EDIT_ERROR":
                path = root / ".flowguard/target/map.json"
                target = json.loads(path.read_text(encoding="utf-8"))
                target["components"][0]["depends_on"].append("unknown-owner")
                write_json(path, target)
                ok = "unknown-owner" in load_target(root).data["components"][0]["depends_on"]
            elif action == "WRITE_CODE":
                write_method(root)
                ok = "def hold(" in (root / "shelf/loans.py").read_text(encoding="utf-8")
            elif action == "EDIT_PLANNED":
                target_path = root / ".flowguard/target/map.json"
                target = load_target(root).data
                target["components"][0]["entrypoints"] = ["shelf/loans.py:advance_next"]
                target["remove"] += ["entrypoint:shelf/loans.py:advance", "flow:borrow"]
                write_json(target_path, target)
                path = root / "shelf/loans.py"
                path.write_text(path.read_text().replace("def advance(", "def advance_next("))
                path = root / ".flowguard/target/models/shelf_rule.py"
                path.write_text(path.read_text().replace("shelf/loans.py:advance", "shelf/loans.py:advance_next").replace("one_loan_step", "extended_step"))
                ok = True
            elif action == "EDIT_WARNING":
                path = root / ".flowguard/target/models/shelf_rule.py"
                source = path.read_text().replace("invariants=(RULE,)", "invariants=(RULE, SECOND)")
                source += ('\nTESTED_BY = {"one_loan_step": ["tests/test_shelf.py:test_advance"]}\n'
                           'SECOND = Invariant("at_most_one", "no double advance", lambda s,t: s <= 1)\n')
                path.write_text(source)
                ok = True
            elif action == "CHECK":
                report = native.check_target(root)
                ok = (bool(report.todos) and not report.errors if scenario == "todo" else
                      bool(report.errors) if scenario == "error" else
                      any(f.code == "target_noop" for f in report.errors) if scenario in ("storage", "noop") else
                      not report.errors and not report.todos)
                if scenario == "planned":
                    from flowguard.map.inventory import build_inventory
                    from flowguard.map.check import run_check
                    from flowguard.map.mapfile import ignore_patterns
                    data = load_map(root)
                    inv = build_inventory(root, ignore_patterns(data), write_cache=False)
                    findings = native.moving_to_target(run_check(root, data, inv, view=build_target_view(root, data, load_target(root))), root, data, load_target(root))
                    ok = not report.errors and not report.todos and any(f.level == "info" and f.message.startswith("moving to target:") for f in findings)
                elif scenario == "warned":
                    ok = not report.errors and not report.todos and any(f.code == "invariant_untested" for f in report.warnings)
                facts.append(Fact(scenario + ":actual_check_buckets", ok,
                                  repr((report.errors, report.todos, report.warnings))))
                ok = ok and snapshot(root) == before
            elif action == "DROP_PREVIEW":
                code = call_target(root, "drop")
                ok = code == 1 and snapshot(root) == before
            elif action == "DROP_YES":
                current = {n: v for n, v in before.items() if not n.startswith(".flowguard/target/")}
                code = call_target(root, "drop", "--yes")
                ok = code == 0 and not (root / ".flowguard/target").exists() and snapshot(root) == current
            elif action == "PROMOTE":
                target = load_target(root)
                if target is None:
                    code = call_target(root, "promote")
                    facts.append(Fact(scenario+":PROMOTE", code == 2 and snapshot(root) == before, str(code)))
                    continue
                expected = build_target_view(root, load_map(root), target).data
                models = {name: (root / rel).read_bytes() for name, rel in target.models.items()}
                output = StringIO()
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    try:
                        code = (native.main(['promote', '--json', '--root', str(root)])
                                if scenario == 'json_error' else native.promote_target(root))
                    except SystemExit as error:
                        code = error.code
                if scenario in ("todo", "error", "noop", "json_error"):
                    ok = code == 1 and snapshot(root) == before
                    if scenario == 'json_error':
                        text = output.getvalue()
                        try:
                            payload = json.loads(text)
                            ok = (ok and len(text.splitlines()) == 1 and payload['command'] == 'target promote'
                                  and payload['verdict'] == 'FAIL'
                                  and any(item['level'] == 'error' for item in payload['codes'])
                                  and payload['next']['id'] == 'design')
                        except (ValueError, TypeError, KeyError):
                            ok = False
                else:
                    ok = (code == 0 and load_map(root) == expected and
                          all((root / ".flowguard/models" / name).read_bytes() == content
                              for name, content in models.items()) and
                          not (root / ".flowguard/target").exists() and
                          not any(flow["id"] == "borrow" for flow in load_map(root)["flows"]) and
                          all(c["status"] == "draft" and "fingerprint" not in c
                              for c in load_map(root)["components"] if c["id"] == "loans"))
            else:
                raise ValueError("unknown finite replay operation " + action)
            after = snapshot(root)
            changed = sorted(name for name in before.keys() | after.keys()
                             if before.get(name) != after.get(name))
            detail = dict(native_exit=code, changed_files=changed,
                          target_exists=(root / ".flowguard/target").exists(),
                          current_map_sha256=hashlib.sha256((root / ".flowguard/map.json").read_bytes()).hexdigest(),
                          current_model_sha256=hashlib.sha256((root / ".flowguard/models/shelf_rule.py").read_bytes()).hexdigest())
            facts.append(Fact(scenario + ":" + action, bool(ok), json.dumps(detail, sort_keys=True)))
    return facts


def _bound_counts():
    from flowguard.map import proof
    with TemporaryDirectory(prefix="target-counts-") as directory:
        root = make_project(Path(directory))
        stage_target(root)
        edit_missing_method(root)
        calls, actual = [], proof.run_bound_tests
        def counted(*args, **kwargs):
            calls.append(True)
            return actual(*args, **kwargs)
        proof.run_bound_tests = counted
        try:
            native.check_target(root)
            before_code = len(calls)
            write_method(root)
            native.check_target(root)
            design = len(calls)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = native.promote_target(root)
            total = len(calls)
        finally:
            proof.run_bound_tests = actual
        return [Fact("check_runs_own_bound_tests_after_code", before_code == 0 and design == 1, f"bound calls before/after code: {before_code}/{design}"),
                Fact("promote_runs_one_full_check", code == 0 and total - design == 1,
                     f"bound calls in PROMOTE: {total - design}; exit {code}")]


def conformance():
    return CodeFactsReport(tuple(_bound_counts()) + tuple(_request_replay(partial) for partial in (False, True)) + tuple(fact for scenario, program in PROGRAMS if scenario != "linked_request"
                                 for fact in _native_replay(scenario, program)))


def _request_replay(partial):
    from flowguard.__main__ import main
    with TemporaryDirectory(prefix="target-request-") as directory:
        root = make_project(Path(directory) / "project")
        source = Path(directory) / "owner.md"
        source.write_bytes(b"Keep linked requests visible.\r\n")
        output = StringIO()
        code = None
        try:
            with redirect_stdout(output), redirect_stderr(output):
                assert main(["req", "add", str(source), "--id", "R1", "--root", str(root)]) == 0
                assert main(["req", "add", str(source), "--id", "R2", "--root", str(root)]) == 0
                originals = {p.name: p.read_bytes() for p in (root / ".flowguard/requests").glob("R*.*")}
                code = call_target(root, "start", "extend the shelf", "--request", "R1:part" if partial else "R1")
                if code == 0:
                    assert call_target(root, "add", "component:loans") == 0
                    assert call_target(root, "add", "model:shelf_rule") == 0
                    edit_missing_method(root)
                    write_method(root)
                    code = native.promote_target(root)
                    main(["read", "--root", str(root)])
            paths = list((root / ".flowguard/changes").glob("*.json"))
            record = json.loads(paths[0].read_bytes()) if len(paths) == 1 else {}
            text = output.getvalue()
            expected = "R1 open since" if partial else "R1 done (change "
            ok = (code == 0 and expected in text and "R2 open since" in text
                  and record.get("requests") == [{"id": "R1", "part": partial}]
                  and {p.name: p.read_bytes() for p in (root / ".flowguard/requests").glob("R*.*")} == originals)
        except (AssertionError, SystemExit, OSError, ValueError) as error:
            ok = False
            text = repr(error) + output.getvalue()
        return Fact("linked_request_partial" if partial else "linked_request_done_at_promote", ok,
                    "native exit=" + str(code) + "; " + text[-500:])
