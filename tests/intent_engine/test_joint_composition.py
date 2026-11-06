"""A lower outcome must hide detail jointly, not just one witness at a time."""
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from flowguard.intent import cli
from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load


def project(tmp_path, children=2, *, coupled=False, detail_enum=False, unreadable=False):
    root = tmp_path / ('joint_' + uuid.uuid4().hex)
    root.mkdir()
    module = 'joint_app_' + uuid.uuid4().hex
    names = ('left', 'right', 'third')[:children]
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('Each gate returns flag; detail is incidental.\nApproval is exactly the conjunction of the gate outcomes.\n')
    gates = ''.join(f'def {name}_gate(flag, detail):\n    if flag:\n        return True\n    return False\n' for name in names)
    approved = ' and '.join(f'{name}_gate({name}.flag, {name}.detail)' for name in names)
    hidden = ' + '.join(f'int({name}.detail)' for name in names)
    limit = children * (2 if detail_enum else 1)
    answer = f'({hidden} != {limit})' if coupled else 'True'
    code = gates + f'def approve({", ".join(names)}):\n    approved = {approved}\n    if not approved:\n        return False\n    return {answer}\n'
    (root / (module + '.py')).write_text(code)
    enum = 'from enum import IntEnum\nclass Detail(IntEnum):\n    ZERO=0\n    ONE=1\n    TWO=2\n' if detail_enum else ''
    detail_type, literal = ('Detail', 'Detail.ZERO') if detail_enum else ('bool', 'False')
    if unreadable:
        detail_type, literal = 'float', '0.0'
    intent = 'from flowguard.intent import rule,row\n' + enum
    for name in names:
        identifier = name.upper()
        predicate = 'flag and detail * detail < 4' if unreadable else 'flag'
        intent += f'''@rule('{identifier}',decides='{name}_ok',source='doc SPEC.txt "Each gate returns flag; detail is incidental."',fields={{'flag':bool,'detail':{detail_type}}})
def {identifier}(flag,detail): return {predicate}
{identifier}.rows(row(flag=True,detail={literal},expect=True,why='approval with baseline detail'),row(flag=False,detail={literal},expect=False,why='refusal with baseline detail'))
@{identifier}.home('{module}:{name}_gate')
def {name}(c,fn): return fn(c.flag,c.detail)
'''
    fields = ','.join(f"'{name}_ok':bool" for name in names)
    arguments = ','.join(name + '_ok' for name in names)
    uses = ','.join(name.upper() for name in names)
    condition = ' and '.join(name + '_ok' for name in names)
    row = ','.join(name + '_ok=True' for name in names)
    witnesses = ','.join(f'c.witness({name.upper()})' for name in names)
    intent += f'''@rule('TOP',decides='approved',source='doc SPEC.txt "Approval is exactly the conjunction of the gate outcomes."',fields={{{fields}}},uses=[{uses}])
def TOP({arguments}): return {condition}
TOP.rows(row({row},expect=True,why='approved outcomes are sufficient together'))
@TOP.home('{module}:approve')
def top(c,fn): return fn({witnesses})
'''
    (root / 'tests/intent/policy.py').write_text(intent)
    model = load(load_config(root))
    assert not model.errors, model.errors
    return model, Engine(model)


def parts(model, engine, identifier):
    rule = model.rules[identifier]
    return [engine.run_rules(rule), *(engine.run_home(rule, rule.homes[0], part) for part in ('rows', 'cells')),
            engine.run_live(rule, rule.homes[0])]


@pytest.mark.parametrize('children', [2, 3])
def test_independent_lower_outcomes_still_work_together(tmp_path, children):
    model, engine = project(tmp_path, children)
    actual = parts(model, engine, 'TOP')
    assert all(item['verdict'] == 'ok' for item in actual), actual
    assert actual[2]['n'] == 2 ** children
    assert actual[2]['composition'] == dict(scope='finite', parent_calls=4 ** children,
                                            checked_all_witnesses=True, finite_domain=True)


@pytest.mark.parametrize('children', [2, 3])
def test_joint_detail_dependency_is_a_real_contract_failure(tmp_path, children):
    model, engine = project(tmp_path, children, coupled=True)
    for identifier in tuple(model.rules)[:-1]:
        assert all(item['verdict'] == 'ok' for item in parts(model, engine, identifier))
    actual = parts(model, engine, 'TOP')
    assert actual[2]['verdict'] == 'red', actual
    assert any('depends on more' in reason for reason in actual[2]['red'])
    hidden = next(site for site in actual[3]['sites'] if '!=' in site['text'])
    assert hidden['realized'] and hidden['mutable'], hidden


def test_the_third_verified_input_is_not_discarded(tmp_path):
    model, engine = project(tmp_path, coupled=True, detail_enum=True)
    result = engine.run_home(model.rules['TOP'], model.rules['TOP'].homes[0], 'cells')
    assert result['verdict'] == 'red', result
    assert any('depends on more' in reason for reason in result['red'])
    assert result['composition']['parent_calls'] == 36
    assert result['composition']['finite_domain']


def test_an_unreadable_lower_domain_does_not_claim_joint_coverage(tmp_path):
    model, engine = project(tmp_path, unreadable=True)
    result = engine.run_home(model.rules['TOP'], model.rules['TOP'].homes[0], 'cells')
    assert result['verdict'] == 'grey', result
    assert any('complete rules' in reason for reason in result['grey'])
    assert not result['composition']['checked_all_witnesses']
    assert not result['composition']['finite_domain']


def test_joint_detail_choices_continue_through_nested_uses(tmp_path):
    model, _ = project(tmp_path, coupled=True)
    root = model.cfg.root
    app = next(root.glob('joint_app_*.py'))
    code = app.read_text()
    for leaf, middle in (('left', 'first'), ('right', 'second')):
        code = code.replace('def approve(',
            f'def {middle}(flag, detail, spare):\n    if {leaf}_gate(flag, detail):\n        return True\n    return False\n\ndef approve(', 1)
        code = code.replace(f'{leaf}_gate({leaf}.flag, {leaf}.detail)',
                            f'{middle}({leaf}.flag, {leaf}.detail, {leaf}.spare)')
    app.write_text(code)
    policy = root / 'tests/intent/policy.py'
    lower = policy.read_text().split("@rule('TOP'", 1)[0]
    for leaf, middle in (('left', 'first'), ('right', 'second')):
        lower += f'''@rule('{middle.upper()}',decides='{middle}_ok',source='doc SPEC.txt "Each gate returns flag; detail is incidental."',fields={{'{leaf}_ok':bool,'spare':bool}},uses=[{leaf.upper()}])
def {middle.upper()}({leaf}_ok,spare): return {leaf}_ok
@{middle.upper()}.home('{app.stem}:{middle}')
def {middle}_home(c,fn):
    w=c.witness({leaf.upper()})
    return fn(w.flag,w.detail,c.spare)
'''
    lower += f'''from types import SimpleNamespace
@rule('TOP',decides='approved',source='doc SPEC.txt "Approval is exactly the conjunction of the gate outcomes."',fields={{'first_ok':bool,'second_ok':bool}},uses=[FIRST,SECOND])
def TOP(first_ok,second_ok): return first_ok and second_ok
@TOP.home('{app.stem}:approve')
def top(c,fn):
    first=c.witness(FIRST)
    second=c.witness(SECOND)
    left=first.witness(LEFT)
    right=second.witness(RIGHT)
    return fn(SimpleNamespace(flag=left.flag,detail=left.detail,spare=first.spare),SimpleNamespace(flag=right.flag,detail=right.detail,spare=second.spare))
'''
    policy.write_text(lower)
    model = load(load_config(root))
    assert not model.errors, model.errors
    engine = Engine(model)
    for identifier in ('LEFT', 'RIGHT', 'FIRST', 'SECOND'):
        assert all(result['verdict'] == 'ok' for result in parts(model, engine, identifier))
    result = engine.run_home(model.rules['TOP'], model.rules['TOP'].homes[0], 'cells')
    assert result['verdict'] == 'red', result
    assert any('depends on more' in reason for reason in result['red'])
    assert result['composition'] == dict(scope='finite', parent_calls=64,
                                          checked_all_witnesses=True, finite_domain=True)


def test_joint_counterexample_reaches_the_same_pytest_and_cli_rejection(tmp_path):
    model, _ = project(tmp_path, coupled=True)
    (model.cfg.root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    command = [sys.executable, '-c',
               'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
               str(Path(cli.__file__).resolve().parents[2]), '-q', '-p', 'flowguard.intent.plugin',
               'tests/intent', 'tests/test_flowguard_intent.py']
    plain = subprocess.run(command, cwd=model.cfg.root, capture_output=True, text=True)
    assert plain.returncode == 1, plain.stdout + plain.stderr
    assert 'depends on more' in plain.stdout + plain.stderr
    assert cli.check(model.cfg, everything=True) == 1
