"""Release warns on an open target, checks every gate and runs shards only after clean gates."""
from dataclasses import dataclass,replace
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='release_gate'
PARENT='cli'
IMPLEMENTED_BY={'Verify':'flowguard/map/cli.py:cmd_verify'}
USES = {'Main': 'flowguard/__main__.py:main',
        'ShapeFindings': 'flowguard/map/lint.py:shape_findings',
        'ApplyDebts': 'flowguard/map/lint.py:apply_accepted_debts'}
KEEPS = ('expired_debt',)
HANDOFF={'map_check':{'check':('check',{'error':'error','stale':None,'clean':'clean'})},'model_runs':{'models':'models'},'shard_suite':{'suite':'suite'}}
TESTED_BY = {'release_passes_only_when_every_gate_passes': ['tests/test_flowguard_map_proof.py:test_strict_check_and_verify_gate',
 'tests/test_release_gate.py:test_release_refuses_deleted_unstaged_target'],
 'suite_runs_only_after_clean_gates': ['tests/test_pytest_shard_runner.py:test_release_runs_the_whole_suite_in_shards'],
 'open_target_is_warned': ['tests/test_cli_main.py:test_release_warns_first_but_runs_the_same_current_models',
 'tests/test_release_gate.py:test_open_target_is_release_warning'],
 'advice_never_gates': ['tests/test_map_check.py:test_shape_findings_are_advice'],
 'expired_debt_fails_release': ['tests/test_map_check.py:test_expired_debt_fails_release']}
@dataclass(frozen=True)
class Case:
    target_open:bool
    shards:bool
    lint:str
    check:str
    models:str
    suite:str
    expired_debt: bool = False
CASES=tuple(Case(target,shards,lint,check,models,suite,expired) for target in (False,True) for lint in ('clean','advice','error') for check in ('clean','error') for models in ('pass','fail') for shards,suites in ((False,('pass',)),(True,('pass','fail','partial','blocked'))) for suite in suites for expired in (False,True))
CASES += tuple(Case(False, True, 'clean', reason, 'pass', 'pass')
               for reason in ('target_already_promoted', 'target_deleted_not_staged'))
@dataclass(frozen=True)
class State:
    target_open:bool=False
    shards:bool=False
    lint:str='clean'
    check:str='clean'
    models:str='pass'
    suite:str='pass'
    suite_ran:bool=False
    warned:bool=False
    verdict:str='pass'
    exit_code:int=0
    expired_debt: bool = False
class TakeRequest:
    name='TakeRequest'
    reads=()
    writes = ('target_open', 'shards', 'lint', 'expired_debt')

    def apply(self, event, state):
        return (FunctionResult(event, replace(state, target_open=event.target_open,
                                              shards=event.shards, lint=event.lint,
                                              expired_debt=event.expired_debt)),)
class Warn:
    name='Warn'
    reads=('target_open',)
    writes=('warned',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):return (FunctionResult(event,replace(state,warned=state.target_open and self.defect!='silent_on_open_target')),)
class CheckGate:
    name='CheckGate'
    reads=()
    writes=('check',)
    def apply(self, event, state):
        check = 'error' if event.check in ('target_already_promoted', 'target_deleted_not_staged') else event.check
        return (FunctionResult(event, replace(state, check=check), label=check),)
class ModelsGate:
    name='ModelsGate'
    reads=()
    writes=('models',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,models=event.models),label=event.models),)
class Suite:
    name='Suite'
    reads=('shards','lint','check','models','expired_debt')
    writes=('suite','suite_ran')
    def __init__(self,defect=''):self.defect=defect
    def apply(self, event, state):
        gates_clean = (state.lint in ('clean', 'advice') and state.check == 'clean'
                       and state.models == 'pass' and not state.expired_debt)
        ran = state.shards and (gates_clean or self.defect == 'runs_suite_after_failure')
        if not ran:
            return (FunctionResult(event, replace(state, suite_ran=False), label='not run'),)
        return (FunctionResult(event, replace(state, suite=event.suite, suite_ran=True), label=event.suite),)
class Verdict:
    name='Verdict'
    reads=('lint','check','models','shards','suite','expired_debt')
    writes=('verdict','exit_code')
    def __init__(self,defect=''):self.defect=defect
    def apply(self, event, state):
        lint_clean = state.lint in ('clean', 'advice')
        if self.defect == 'advice_gates_release' and state.lint == 'advice':
            lint_clean = False
        passed = (lint_clean and state.check == 'clean'
                  and (not state.expired_debt or self.defect == 'expired_debt_passes_release')
                  and (state.models == 'pass' or self.defect == 'ignores_failed_model')
                  and (not state.shards or not state.suite_ran or state.suite == 'pass'))
        return (FunctionResult(int(not passed), replace(state, verdict='pass' if passed else 'fail',
                                                        exit_code=int(not passed))),)
RULES=(
 Invariant('expired_debt_fails_release', 'release fails while an accepted debt has expired',
           lambda s,t: not s.expired_debt or s.verdict == 'fail'),
 Invariant('advice_never_gates',
           'size and count lint findings are advice: release never fails on them and they need no accepted debt',
           lambda s,t: s.expired_debt or s.lint != 'advice' or s.check != 'clean' or s.models != 'pass'
           or (s.shards and s.suite != 'pass') or s.verdict == 'pass'),
 Invariant('release_passes_only_when_every_gate_passes','release reflects checks, lint, model proof and requested suite',lambda s,t:(s.verdict=='pass')==(not s.expired_debt and s.check == 'clean' and s.lint in ('clean', 'advice') and s.models=='pass' and (not s.shards or s.suite=='pass')) and s.exit_code==int(s.verdict!='pass')),
 Invariant('suite_runs_only_after_clean_gates','a suite starts only after every earlier gate passes',lambda s,t:not s.suite_ran or s.shards and not s.expired_debt and s.check == 'clean' and s.lint in ('clean', 'advice') and s.models=='pass'),
 Invariant('open_target_is_warned','the current tree release names any open target first',lambda s,t:not s.target_open or s.warned),
)
def make(defect=''):return Explorer(Workflow((TakeRequest(),Warn(defect),CheckGate(),ModelsGate(),Suite(defect),Verdict(defect))),(State(),),CASES,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():
    return {name: make(name) for name in ('ignores_failed_model', 'runs_suite_after_failure',
                                        'silent_on_open_target', 'advice_gates_release', 'expired_debt_passes_release')}
def conformance():
    import json
    import shutil
    import subprocess
    from datetime import date, timedelta
    from contextlib import nullcontext
    from unittest.mock import patch
    from flowguard.__main__ import main
    from flowguard.map import lint
    from flowguard.map.cli import _context, main as map_main
    from _target_fixture import make_project, call_target

    facts = []
    for case in ('clean', 'failed', 'target', 'suite_blocked', 'advice', 'expired', 'target_already_promoted', 'target_deleted_not_staged'):
        with TemporaryDirectory(prefix='fg-release-gate-') as directory:
            root = make_project(Path(directory))
            if case in ('failed', 'suite_blocked'):
                path = root / 'shelf/loans.py'
                path.write_text(path.read_text().replace('value + capacity()', 'value + capacity() + 1'))
            if case == 'advice':
                path = root / '.flowguard/map.json'
                data = json.loads(path.read_text())
                data['components'][0]['responsibilities'].append('advance the active quantity')
                data['components'][1]['tests'] = ['tests/test_shelf.py']
                path.write_text(json.dumps(data))
                model = root / '.flowguard/models/shelf_rule.py'
                model.write_text(model.read_text().replace(
                    'TESTED_BY = {}',
                    "TESTED_BY = {'one_loan_step': ['tests/test_shelf.py:test_advance']}"))
            if case == 'expired':
                path = root / '.flowguard/map.json'
                data = json.loads(path.read_text())
                data['accepted_debts'] = [dict(code='untested_component', component='catalog',
                    reason='covered through loans', expires=(date.today() - timedelta(days=1)).isoformat())]
                path.write_text(json.dumps(data))
            with redirect_stdout(StringIO()):
                map_main(['confirm', 'all', '--root', str(root)])
            if case == 'target':
                call_target(root, 'start', 'open plan')
            if case in ('target_already_promoted', 'target_deleted_not_staged'):
                def git(*args):
                    subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
                git('init', '-q')
                git('add', '.')
                git('-c', 'user.name=probe', '-c', 'user.email=probe@example.invalid', 'commit', '-qm', 'seed')
                assert call_target(root, 'start', 'unchanged target') == 0
                assert call_target(root, 'add', 'component:loans') == 0
                git('add', '.flowguard/target')
                git('-c', 'user.name=probe', '-c', 'user.email=probe@example.invalid', 'commit', '-qm', 'target')
                if case == 'target_deleted_not_staged':
                    shutil.rmtree(root / '.flowguard/target')
            args = ['release', '--root', str(root)]
            if case in ('suite_blocked', 'expired', 'target_already_promoted', 'target_deleted_not_staged'):
                args += ['--shards', '2']
            limits = lint.Limits(max_component_loc=1, max_file_loc=1,
                                 max_responsibilities=1, max_fan_out=0)
            output = StringIO()
            fixture_limits = patch.object(lint, 'Limits', return_value=limits) if case == 'advice' else nullcontext()
            with fixture_limits, redirect_stdout(output), redirect_stderr(output):
                code = main(args)
                shape = []
                if case == 'advice':
                    data, inventory = _context(root)
                    shape = [finding for finding in lint.run_lint(root, data, inventory)
                             if finding.code in {'large_component', 'large_file',
                                                 'too_many_responsibilities', 'high_fan_out'}]
            text = output.getvalue()
            failing = case in ('failed', 'suite_blocked', 'expired', 'target_already_promoted', 'target_deleted_not_staged')
            valid = code == int(failing) and ('verify: FAIL' if failing else 'verify: PASS') in text
            if case == 'target':
                valid = valid and text.startswith('warning: target "open plan" exists:')
            if case in ('suite_blocked', 'expired', 'target_already_promoted', 'target_deleted_not_staged'):
                valid = valid and 'suite: not run' in text
            if case == 'advice':
                valid = (valid and {finding.code for finding in shape}
                         == {'large_component', 'large_file', 'too_many_responsibilities', 'high_fan_out'}
                         and all(finding.level == 'info' and '(advice, not a gate)' in finding.message
                                 for finding in shape)
                         and 'lint: 0 error(s) gating; 0 warning(s),' in text)
            if case == 'expired':
                valid = valid and 'debt_expired' in text
            if case in ('target_already_promoted', 'target_deleted_not_staged'):
                valid = valid and case in text
            facts.append(Fact(case, bool(valid), text))
    return CodeFactsReport(tuple(facts))
