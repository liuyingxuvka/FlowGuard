"""Map check aggregates severities and prints one row for repeated INFO codes."""
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = 'map_check'
PARENT = 'map-check'
COMPONENTS = ['map-check', 'map-inventory', 'map-file']
IMPLEMENTED_BY = {
    'Check': 'flowguard/map/check.py:run_check',
    'PrintFindings': 'flowguard/map/common.py:print_findings',
    'Lint': 'flowguard/map/lint.py:run_lint',
    'DebtValidity': 'flowguard/map/debts.py:evaluate_debts',
}
USES = {
    'CmdConfirm': 'flowguard/map/cli.py:cmd_confirm',
    'Command': 'flowguard/map/cli.py:cmd_check',
    'Main': 'flowguard/__main__.py:main',
}
NOT_MODELED = {}
OUTPUTS = {'check': ('error', 'stale', 'clean')}
TESTED_BY = {'error_finding_fails_check': ['tests/test_component_pointer.py:test_filled_map_checks_clean_after_confirm'],
 'strict_makes_draft_and_stale_errors': ['tests/test_cli_main.py:test_new_target_file_is_moving_but_strict_remains_an_error'],
 'identical_info_grouped': ['tests/test_map_check.py:test_identical_info_grouped_into_one_line'],
 'debt_needs_reason_and_expiry': ['tests/test_map_check.py:test_debt_without_expiry_refused']}

@dataclass(frozen=True)
class Case:
    mode: str
    errors: tuple = ()
    unconfirmed: str = ''
    count: int = 1

ERRORS = ('anchor_broken', 'component_parent_cycle', 'anchor_outside_home', 'handoff_output_unhandled', 'debt_without_expiry')
CASES = tuple(Case(mode, (), status) for mode in ('check', 'strict') for status in ('', 'draft', 'stale', 'fingerprint_migrate')) + tuple(Case(mode, (code,)) for mode in ('check', 'strict') for code in ERRORS) + tuple(Case(mode, codes, 'stale') for mode in ('check', 'strict') for codes in (ERRORS[:2], ERRORS[2:])) + (Case('check', count=3), Case('check', count=24))

@dataclass(frozen=True)
class State:
    mode: str = 'check'
    errors: tuple = ()
    unconfirmed: str = ''
    raw_info: int = 1
    check: str = ''
    grouped: bool = True
    info_lines: int = 1
    exit_code: int = 0
    phase: int = 0

class TakeRun:
    name = 'TakeRun'
    reads = ()
    writes = ('mode', 'errors', 'unconfirmed', 'raw_info', 'phase')
    def apply(self, event, state):
        return (FunctionResult(event, replace(state, mode=event.mode, errors=event.errors,
                    unconfirmed=event.unconfirmed, raw_info=event.count, phase=1)),)

class Aggregate:
    name = 'Aggregate'
    reads = ('errors', 'mode', 'unconfirmed')
    writes = ('check', 'phase')
    def __init__(self, defect=''): self.defect = defect
    def apply(self, event, state):
        errors = state.errors
        if self.defect == 'ignores_edge_errors':
            errors = tuple(code for code in errors if code != 'handoff_output_unhandled')
        if self.defect == 'debt_without_expiry_passes':
            errors = tuple(code for code in errors if code != 'debt_without_expiry')
        strict = state.mode == 'strict' and bool(state.unconfirmed) and self.defect != 'strict_keeps_stale_warning'
        value = 'error' if errors or strict else 'stale' if state.unconfirmed else 'clean'
        return (FunctionResult(value, replace(state, check=value, phase=2)),)

class Print:
    name = 'Print'
    reads = ('raw_info', 'check')
    writes = ('info_lines', 'grouped', 'exit_code', 'phase')
    def __init__(self, defect=''): self.defect = defect
    def apply(self, event, state):
        count = state.raw_info if self.defect == 'prints_each_info_line' else 1
        return (FunctionResult(int(state.check == 'error'), replace(state, info_lines=count,
                    grouped=count == 1, exit_code=int(state.check == 'error'), phase=3)),)

INVARIANTS = (
    Invariant('debt_needs_reason_and_expiry',
              'an accepted debt without a reason or an expiry is an ERROR in check and lint',
              lambda s,t: s.phase != 3 or 'debt_without_expiry' not in s.errors or s.check == 'error'),
    Invariant('error_finding_fails_check', 'errors fail the check; its exit follows its verdict',
              lambda s,t: s.phase != 3 or s.exit_code == int(s.check == 'error') and (not s.errors or s.check == 'error')),
    Invariant('strict_makes_draft_and_stale_errors', 'strict checks refuse every unconfirmed pointer',
              lambda s,t: s.phase != 3 or s.mode != 'strict' or not s.unconfirmed or s.check == 'error' and s.exit_code == 1),
    Invariant("identical_info_grouped", "three identical INFO codes have one output line", lambda s,t: s.info_lines == 1),
)

def make(defect=''):
    return Explorer(Workflow((TakeRun(), Aggregate(defect), Print(defect))), (State(),), CASES,
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)
def build_explorer(): return make()
def broken_variants():
    return {name: make(name) for name in ('ignores_edge_errors', 'strict_keeps_stale_warning', 'prints_each_info_line', 'debt_without_expiry_passes')}

def conformance():
    from flowguard.__main__ import main
    from flowguard.map.check import run_check
    from flowguard.map.cli import cmd_check, cmd_confirm
    from flowguard.map.common import Finding, print_findings
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map, ignore_patterns
    from flowguard.map.lint import run_lint
    from _target_fixture import make_port_project, write_json

    facts = []
    for case in ('anchor', 'cycle', 'scope', 'edge', 'stale'):
        with TemporaryDirectory(prefix='fg-check-') as directory:
            root = Path(directory)
            data = make_port_project(root)
            with redirect_stdout(StringIO()):
                cmd_confirm(root, SimpleNamespace(ids=['cli', 'loans']))
            data = load_map(root)
            if case == 'anchor':
                data['components'][0]['entrypoints'] = ['shelf/cli.py:missing']
            elif case == 'cycle':
                for component in data['components']:
                    component['parent'] = 'loans' if component['id'] == 'cli' else 'cli'
            elif case == 'scope':
                path = root / '.flowguard/models/lending.py'
                path.write_text(path.read_text().replace('COMPONENTS = ["loans"]', 'COMPONENTS = ["cli"]'))
            elif case == 'edge':
                path = root / '.flowguard/models/desk.py'
                path.write_text(path.read_text().replace('HANDOFF = {"lending":{"answer":"answer"}}', 'HANDOFF = {}'))
            else:
                path = root / 'shelf/cli.py'
                path.write_text(path.read_text() + '\n# changed owned source\n')
            write_json(root / '.flowguard/map.json', data)
            for strict in (False, True):
                inventory = build_inventory(root, ignore_patterns(data), write_cache=False)
                findings = run_check(root, data, inventory, strict=strict)
                expected = int(any(f.level == 'error' for f in findings))
                with redirect_stdout(StringIO()):
                    exit_code = cmd_check(root, SimpleNamespace(strict=strict, json=False, limit=80))
                valid = expected == exit_code and (expected == 1 if case != 'stale' else expected == int(strict))
                if case == 'stale':
                    valid = valid and any(f.code == 'stale' and f.level == ('error' if strict else 'warn')
                                          for f in findings)
                facts.append(Fact(case + str(strict), bool(valid),
                                  repr((exit_code, [(f.code, f.level) for f in findings]))))
    for case in ('missing_expiry', 'missing_reason'):
        with TemporaryDirectory(prefix='fg-debt-check-') as directory:
            root = Path(directory)
            data = make_port_project(root)
            with redirect_stdout(StringIO()):
                cmd_confirm(root, SimpleNamespace(ids=['cli', 'loans']))
            data = load_map(root)
            debt = dict(code='unmodeled_owner', component='cli', reason='the entry is checked elsewhere')
            if case == 'missing_reason':
                debt.pop('reason')
                debt['expires'] = '9999-12-31'
            data['accepted_debts'] = [debt]
            write_json(root / '.flowguard/map.json', data)
            inventory = build_inventory(root, ignore_patterns(data), write_cache=False)
            try:
                lint = run_lint(root, data, inventory)
            except Exception as error:
                lint = []
                facts.append(Fact(case + '_lint_exception', False, type(error).__name__ + ': ' + str(error)))
            for strict in (False, True):
                output = StringIO()
                with redirect_stdout(output):
                    try:
                        findings = run_check(root, data, inventory, strict=strict)
                        code = main(['map', '--root', str(root), 'check', *(['--strict'] if strict else [])])
                    except Exception as error:
                        findings = []
                        code = None
                        print(type(error).__name__ + ': ' + str(error))
                valid = (code == 1 and any(f.code == 'debt_without_expiry' and f.level == 'error' for f in findings)
                         and any(f.code == 'debt_without_expiry' and f.level == 'error' for f in lint))
                facts.append(Fact(case + str(strict), valid, output.getvalue()))
    output = StringIO()
    with redirect_stdout(output):
        print_findings([Finding('info', 'same', str(i), 'note') for i in range(3)], 'check', as_json=False, limit=80)
    rows = [line for line in output.getvalue().splitlines() if line.startswith('INFO')]
    facts.append(Fact('grouped_info', len(rows) == 1 and 'x3:' in rows[0], output.getvalue()))
    return CodeFactsReport(tuple(facts))
