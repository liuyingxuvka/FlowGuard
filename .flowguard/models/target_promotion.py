"""Promotion writes the checked merge, removes the target, leaves changed components draft, refuses changed inputs.

It starts where the parent target_life_cycle stands right after a clean check
(project_parent_state). Conformance replays each covering trace on a fresh small
shelf project with a clean target and runs the real promote_target.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.kit import reachable_states

MODEL_ID = "target_promotion"
PARENT = "target_life_cycle"
OUTPUTS = {"outcome": ("promoted", "refused", "no_target")}
IMPLEMENTED_BY = {"Promote": "flowguard/map/target.py:promote_target"}
USES = {
    'Main': 'flowguard/map/cli.py:main',
    'ModelEdits': 'flowguard/map/check.py:model_edit_findings',
    'ModelDigests': 'flowguard/map/mapfile.py:model_digests',
    'CheckedInputs': 'flowguard/map/target_identity.py:_promotion_inputs',
}
TESTED_BY = {
    'promote_prints_owner_block': ['tests/test_requests.py:test_promote_prints_owner_block', 'tests/test_records.py:test_real_promotion_records_checked_plan_rules_and_function_diff'],
    'promote_names_stale_components': ['tests/test_target_life_cycle.py:test_promote_names_stale_component_to_confirm'],
    'promote_makes_current_equal_merged': ['tests/test_target_life_cycle.py:test_target_small_promotion_preserves_map_and_model_bytes'],
    'promote_leaves_no_target': ['tests/test_target_life_cycle.py:test_target_small_promotion_preserves_map_and_model_bytes'],
    'changed_components_become_draft': ['tests/test_target_life_cycle.py:test_target_small_promotion_preserves_map_and_model_bytes'],
    'refusal_shows_findings': ['tests/test_target_life_cycle.py:test_refused_promote_prints_the_report',
                              'tests/test_target_life_cycle.py:test_unavailable_tests_next_names_test_commands'],
    'changed_inputs_refuse_promotion': ['tests/test_target_life_cycle.py:test_promote_refuses_inputs_changed_after_its_check',
                                       'tests/test_model_edits.py:test_in_place_edit_of_staged_model_refused'],
    'promote_names_target_deletion': [
        'tests/test_target_life_cycle.py:test_promote_next_line_names_target_deletion',
        'tests/test_target_life_cycle.py:test_promote_without_git_keeps_usable_next_step',
    ],
}


@dataclass(frozen=True)
class State:
    target_revision: int
    current_map_revision: int
    current_model_revision: int
    expected_model_revision: int
    target_count: int = 1
    edited: bool = False             # the checked inputs changed after the check
    draft: bool = False              # the target's components are draft after promotion
    action: str = ""
    status: str = ""
    outcome: str = ""
    findings_shown: bool = True
    stale_components_named: bool = True
    target_deletion_named: bool = True
    current_edited: bool = False
    owner_block_shown: bool = True
    record_evidence_kept: bool = True


def project_parent_state(state):
    """The child's start: the parent has just checked a target with no error and no to-do."""
    if state.action != "CHECK" or state.errors or state.todos or state.target_count != 1:
        return None
    return State(state.target_revision, state.current_map_revision, state.current_model_revision,
                 state.expected_model_revision)


def _starts():
    import target_life_cycle            # inside the function: the parent imports nothing of its children
    return reachable_states(target_life_cycle.build_explorer(), project_parent_state)


class Promote:
    name = "Promote"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        if event == "REFUSE_UNAVAILABLE" and state.target_count and not (state.edited or state.current_edited):
            new = replace(state, action=event, status="refused_error",
                          findings_shown=self.defect not in ("refuses_silently", "unavailable_tests_point_at_design"))
            return (FunctionResult(new.status, new, label=event),)
        if event == "REFUSE_ERROR" and state.target_count:
            new = replace(state, action=event, status="refused_error", findings_shown=self.defect != "refuses_silently")
            return (FunctionResult(new.status, new, label=event),)
        if event == "EDIT_AFTER_CHECK":
            new = replace(state, action=event, status="edited" if state.target_count else "no_target",
                          edited=state.edited or bool(state.target_count))
            return (FunctionResult(new.status, new, label=event),)
        if event == "EDIT_CURRENT":
            new = replace(state, action=event, status="edited" if state.target_count else "no_target",
                          current_edited=state.current_edited or bool(state.target_count))
            return (FunctionResult(new.status, new, label=event),)
        if not state.target_count:
            new = replace(state, action=event, status="no_target")
        elif (state.edited and self.defect != "promotes_after_edit"
              or state.current_edited and self.defect != "promote_overwrites_in_place_edit"):
            new = replace(state, action=event, status="refused")
        else:
            new = replace(state, action=event, status="promoted", target_count=0, draft=True,
                          current_map_revision=state.target_revision,
                          current_model_revision=state.expected_model_revision)
            if self.defect == "models_only":
                new = replace(new, current_map_revision=state.current_map_revision)
            if self.defect == "retained_target":
                new = replace(new, target_count=1)
            if self.defect == "keeps_components_confirmed":
                new = replace(new, draft=False)
        if new.status == "promoted" and self.defect == "names_drafts_only":
            new = replace(new, stale_components_named=False)
        if new.status == "promoted" and self.defect == "staging_line_omits_target":
            new = replace(new, target_deletion_named=False)
        if new.status == "promoted" and self.defect == "owner_block_omits_line":
            new = replace(new, owner_block_shown=False)
        if new.status == "promoted" and self.defect == "record_omits_evidence":
            new = replace(new, record_evidence_kept=False)
        if event == "PROMOTE":
            new = replace(new, outcome=new.status)
        return (FunctionResult(new.status, new, label=event),)


def _holds(condition, message):
    return InvariantResult.pass_() if condition else InvariantResult.fail(message)


INVARIANTS = (
    Invariant("promote_prints_owner_block", "a promote prints and immutably preserves checked PLAN lines and their old/new rule provenance",
              lambda s,t: _holds(s.status != "promoted" or s.owner_block_shown and s.record_evidence_kept, "owner block or immutable record omitted checked model evidence")),
    Invariant("promote_names_target_deletion",
              "a successful promote names the target deletion with usable staging or no-Git verification guidance",
              lambda s,t: _holds(s.status != "promoted" or s.target_deletion_named,
                                 "the promotion guidance omitted the target deletion or a usable next step")),
    Invariant("promote_names_stale_components", "confirmation guidance includes changed confirmed components",
              lambda s,t: _holds(s.status != "promoted" or s.stale_components_named, "stale component missing from confirmation")),
    Invariant("refusal_shows_findings", "refusal shows the actual error and changes no current bytes; an unavailable test names test_commands",
              lambda s, t: _holds(s.status != "refused_error" or s.findings_shown, "refusal hid its findings")),
    Invariant("promote_makes_current_equal_merged", "both current map and models equal the prepared merge",
              lambda s, t: _holds(s.status != "promoted" or
                                  (s.current_map_revision == s.target_revision and
                                   s.current_model_revision == s.expected_model_revision),
                                  "current map or model differs from the merge")),
    Invariant("promote_leaves_no_target", "successful promotion removes the target",
              lambda s, t: _holds(s.status != "promoted" or s.target_count == 0, "promotion retained the target")),
    Invariant("changed_components_become_draft", "the target's components are draft after promotion",
              lambda s, t: _holds(s.status != "promoted" or s.draft, "a changed component stayed confirmed")),
    Invariant("changed_inputs_refuse_promotion", "promote refused: checked inputs changed",
              lambda s, t: _holds(s.action != "PROMOTE" or not (s.edited or s.current_edited) or s.status == "refused",
                                  "a target whose checked inputs changed was promoted")),
)


def _explorer(defect=""):
    return Explorer(Workflow((Promote(defect),)), _starts(), ("PROMOTE", "EDIT_AFTER_CHECK", "EDIT_CURRENT", "REFUSE_ERROR", "REFUSE_UNAVAILABLE"),
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in
            ("models_only", "retained_target", "keeps_components_confirmed", "promotes_after_edit", "refuses_silently", "names_drafts_only", "staging_line_omits_target", "promote_overwrites_in_place_edit", "unavailable_tests_point_at_design", "owner_block_omits_line", "record_omits_evidence")}


class RealPromotion:
    """A fresh copy of a clean shelf target; PROMOTE runs the real promote_target."""

    def __init__(self, base):
        self.base = base

    def reset(self, initial_state):
        from flowguard.map.mapfile import load_map
        from flowguard.map.targetfile import build_target_view, load_target
        self.directory = TemporaryDirectory(prefix="target-promotion-")
        self.root = Path(shutil.copytree(self.base, Path(self.directory.name) / "project"))
        from flowguard.map.requests import store_request
        store_request(self.root, b"One loan step stays bounded.\n", identifier="RBlock")
        (self.root / ".flowguard/target/PLAN.txt").write_text(
            'changes: shelf_rule.one_loan_step by RBlock "One loan step stays bounded."\n'
            'changes: shelf_rule.no_duplicate_step because "A duplicate step remains rejected."\n', encoding="utf-8")
        self.expected = build_target_view(self.root, load_map(self.root), load_target(self.root)).data
        self.expected_models = {path.name: path.read_bytes() for path in (self.root / ".flowguard/target/models").glob("*.py")}
        self.state, self.edit = initial_state, False
        self.current_edit = False

    def apply_step(self, step):
        from flowguard.map import target as native
        from flowguard.map.mapfile import load_map
        event = step.function_input
        state = replace(self.state, action=event)
        exists = (self.root / ".flowguard/target").exists()
        if event == "REFUSE_UNAVAILABLE" and exists and not (self.edit or self.current_edit):
            import json
            import shlex
            missing = "tests/desk.test.js"
            test = self.root / missing
            test.write_text("// requires the project's declared test command\n")
            maps = [self.root / ".flowguard/map.json", self.root / ".flowguard/target/map.json"]
            saved = {path: path.read_bytes() for path in maps}
            try:
                for path in maps:
                    data = json.loads(path.read_text())
                    next(component for component in data["components"] if component["id"] == "loans")["tests"].append(missing)
                    path.write_text(json.dumps(data))
                paths = [*maps, test, *(self.root / ".flowguard/models").glob("*.py"),
                         *(self.root / ".flowguard/target/models").glob("*.py")]
                before = {path: path.read_bytes() for path in paths}
                output = StringIO()
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    code = native.promote_target(self.root)
                text = output.getvalue()
                next_line = next((line for line in text.splitlines() if line.startswith("next[test_command]: ")), "")
                command = shlex.split(next_line.removeprefix("next[test_command]: "))
                shown = (code == 1 and "ERROR target: selected_tests_unavailable:" in text
                         and 'declare "test_commands" for *.test.js' in text
                         and str(maps[0].resolve()) in text
                         and "or bind them to a test FlowGuard can run" in text
                         and command == ["python", "-m", "flowguard", "target", "promote", "--root", str(self.root.resolve())]
                         and all(path.exists() and path.read_bytes() == content for path, content in before.items()))
            finally:
                for path, content in saved.items():
                    path.write_bytes(content)
                test.unlink()
            state = replace(state, status="refused_error" if code == 1 else "unexpected_success", findings_shown=shown)
        elif event == "REFUSE_ERROR" and exists:
            import json
            target_map = self.root / ".flowguard/target/map.json"
            saved = target_map.read_bytes()
            data = json.loads(saved)
            data["goal"] = ""
            target_map.write_text(json.dumps(data))
            paths = [self.root / ".flowguard/map.json", *(self.root / ".flowguard/models").glob("*.py"),
                     *(self.root / ".flowguard/target/models").glob("*.py"), target_map]
            before = {p: p.read_bytes() for p in paths}
            output = StringIO()
            try:
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    code = native.promote_target(self.root)
                unchanged = all(p.exists() and p.read_bytes() == b for p, b in before.items())
            finally:
                target_map.write_bytes(saved)
            shown = "ERROR" in output.getvalue() and "promote refused: 1 error(s), 0 to-do" in output.getvalue()
            state = replace(state, status="refused_error" if code == 1 else "unexpected_success",
                            findings_shown=shown and unchanged)
        elif event == "EDIT_AFTER_CHECK":
            self.edit = self.edit or exists
            state = replace(state, status="edited" if exists else "no_target", edited=state.edited or exists)
        elif event == "EDIT_CURRENT":
            if exists:
                path = self.root / '.flowguard/models/shelf_rule.py'
                path.write_text(path.read_text() + '\nCURRENT_INTENT = True\n')
            self.current_edit = self.current_edit or exists
            state = replace(state, status="edited" if exists else "no_target",
                            current_edited=state.current_edited or exists)
        elif not exists:
            state = replace(state, status="no_target")
        else:
            original = native.check_target
            if self.edit:
                def check_then_edit(root, **options):        # the checked target model changes after its check
                    report = original(root, **options)
                    model = Path(root) / ".flowguard/target/models/shelf_rule.py"
                    model.write_text(model.read_text(encoding="utf-8") + "\n# edited after the check\n", encoding="utf-8")
                    return report
                native.check_target = check_then_edit
            output = StringIO()
            watched = [self.root / '.flowguard/models/shelf_rule.py', self.root / '.flowguard/target/models/shelf_rule.py',
                       self.root / '.flowguard/map.json', self.root / '.flowguard/target/map.json']
            before = {path: path.read_bytes() for path in watched} if self.current_edit else {}
            try:
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    code = native.promote_target(self.root)
            finally:
                native.check_target = original
            current = load_map(self.root)
            if code == 0:
                import shlex
                lines = output.getvalue().splitlines()
                last = lines[-1] if lines else ""
                names_deletion = "deletion of .flowguard/target/" in output.getvalue()
                if last.startswith('next[commit]: '):
                    argv = shlex.split(last.removeprefix('next[commit]: '))
                    split = argv.index('&&') if '&&' in argv else len(argv)
                    stage, commit = argv[:split], argv[split + 1:]
                    usable = (stage[:3] == ["git", "-C", str(self.root.resolve())] and "add" in stage and ".flowguard" in stage
                              and commit[:5] == ['git', '-C', str(self.root.resolve()), 'commit', '-F']
                              and len(commit) == 6 and Path(commit[-1]).is_file())
                else:
                    argv = shlex.split(last.removeprefix("next[check]: "))
                    usable = ("no Git worktree" in output.getvalue()
                              and argv == ["python", "-m", "flowguard", "map", "check", "--strict", "--root", str(self.root.resolve())])
                from flowguard.map.records import change_records
                stored = change_records(self.root)
                record = stored[-1][1] if stored else {}
                planned = [row['line'] for row in record.get('plan', [])]
                evidence = {row['id']: row for row in record.get('rules', [])}
                kept = (planned == ['changes: shelf_rule.one_loan_step by RBlock "One loan step stays bounded."',
                                     'changes: shelf_rule.no_duplicate_step because "A duplicate step remains rejected."']
                        and evidence.get('shelf_rule.one_loan_step', {}).get('provenance') == 'owner RBlock'
                        and evidence.get('shelf_rule.no_duplicate_step', {}).get('new') is not None)
                loans = next(c for c in current["components"] if c["id"] == "loans")
                same_models = all((self.root / ".flowguard/models" / name).read_bytes() == content
                                  for name, content in self.expected_models.items())
                state = replace(state, status="promoted", target_count=int((self.root / ".flowguard/target").exists()),
                                draft=loans["status"] == "draft" and any("loans" in line.split()[6:] for line in output.getvalue().splitlines()
                                      if line.startswith("next[confirm]: python -m flowguard map confirm ")),
                                stale_components_named=any("catalog" in line.split()[6:] for line in output.getvalue().splitlines()
                                      if line.startswith("next[confirm]: python -m flowguard map confirm ")),
                                target_deletion_named=names_deletion and usable,
                                record_evidence_kept=kept,
                                owner_block_shown=("owner block (paste it unchanged into your final message):" in output.getvalue()
                                    and 'changes: shelf_rule.one_loan_step by RBlock "One loan step stays bounded."' in output.getvalue()
                                    and 'changes: shelf_rule.no_duplicate_step because "A duplicate step remains rejected."' in output.getvalue()
                                    and output.getvalue().count("old rule:") == 2 and output.getvalue().count("new rule:") == 2),
                                current_map_revision=state.target_revision if current == self.expected else -1,
                                current_model_revision=state.expected_model_revision if same_models else -1)
            else:
                if self.current_edit:
                    refused = (code == 1 and 'model_edited_outside_target' in output.getvalue()
                               and all(path.read_bytes() == content for path, content in before.items()))
                else:
                    refused = "promote refused: checked inputs changed" in output.getvalue()
                state = replace(state, status="refused" if refused else f"exit {code}: {output.getvalue()[:200]}")
        if event == "PROMOTE":
            state = replace(state, outcome=state.status)
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=state.status, observed_state=state)

    def observe_state(self):
        return self.state

    def close(self):
        self.directory.cleanup()


def conformance():
    import json
    import target_life_cycle
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map, model_digests
    last = None
    with TemporaryDirectory(prefix="target-promotion-base-") as directory:
        base = target_life_cycle.make_project(Path(directory) / "base")
        from flowguard.map import cli
        with redirect_stdout(StringIO()):
            cli.main(["confirm", "all", "--root", str(base)])
        data = load_map(base)
        data['model_digests'] = model_digests(base)
        (base / '.flowguard/map.json').write_text(json.dumps(data))
        target_life_cycle.stage_target(base)
        target_life_cycle.edit_missing_method(base)
        target_life_cycle.write_method(base)
        model = base / ".flowguard/target/models/shelf_rule.py"
        text = model.read_text().replace("invariants=(RULE,)", "invariants=(RULE, SECOND)")
        text += '\nSECOND = Invariant("no_duplicate_step", "one loan step stays bounded", lambda s,t: s in (0,1))\n'
        model.write_text(text)
        changed = base / "shelf/catalog.py"
        changed.write_text(changed.read_text() + "\n# refreshed documentation\n")
        report = native.check_target(base)
        if report.errors or report.todos:
            raise RuntimeError(f"the base target is not clean: {report.errors + report.todos}")
        for trace in select_covering_traces(build_explorer().explore().traces):
            adapter = RealPromotion(base)
            try:
                last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                    rules=(projected_state_matches(), projected_output_matches()))
            finally:
                adapter.close()
            if not last.ok:
                return last
    return last
