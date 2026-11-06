"""A lower outcome must hide detail jointly, not just one witness at a time."""
from pathlib import Path
from contextlib import contextmanager
import subprocess
import sys
import uuid

import pytest

from flowguard.intent import cli
from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load


def project(tmp_path, children=2, *, coupled=False, detail_enum=False, unreadable=False,
            nested=False, detail_kind=None):
    """Real functions plus an ordinary native scenario, with no call adapter."""
    root = tmp_path / ('joint_' + uuid.uuid4().hex)
    root.mkdir()
    module = 'joint_app_' + uuid.uuid4().hex
    definitions = 'joint_types_' + uuid.uuid4().hex
    names = ('left', 'right', 'third')[:children]
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('Each gate returns flag; detail is incidental.\nApproval is exactly the conjunction of the gate outcomes.\n')
    enum = 'from enum import IntEnum\nclass Detail(IntEnum):\n    ZERO=0\n    ONE=1\n    TWO=2\n' if detail_enum else ''
    if enum:
        (root / (definitions + '.py')).write_text(enum)
    detail_type, literal = ('Detail', 'Detail.ZERO') if detail_enum else ('bool', 'False')
    if unreadable:
        detail_type, literal = 'float', '0.0'
    elif detail_kind is not None:
        detail_type = detail_kind.__name__
        literal = '0' if detail_kind is int else 'False'
    shared = f'from {definitions} import Detail\n' if detail_enum else ''
    source = 'from __future__ import annotations\n' + shared
    intent = 'from flowguard.intent import rule,row,flow,Node,Read,Relation\n' + shared
    native = 'import pytest\nfrom types import SimpleNamespace\n' + shared + f'import {module} as app\n'
    fields = [name + '_' + field for name in names for field in (('flag', 'detail', 'spare') if nested else ('flag', 'detail'))]
    parameters = ', '.join(field + ': ' + (detail_type if field.endswith('_detail') else 'bool') for field in fields)
    testnode = 'tests/test_native_' + module + '.py::test_case'
    for name in names:
        identifier = name.upper()
        source += f'''# flowguard: sensor gate_{name}(flag: flag, detail: detail) -> accepted: bool
 def {name}_gate(flag: bool, detail: {detail_type}) -> bool:
    if flag:
        return True
    return False
'''.replace('\n def ', '\ndef ')
        predicate = 'flag and detail * detail < 4' if unreadable else 'flag'
        binding = '' if detail_enum else f",anchor='gate_{name}'"
        intent += f'''@rule('{identifier}',decides='{name}_ok',source='doc SPEC.txt "Each gate returns flag; detail is incidental."',fields={{'flag':bool,'detail':{detail_type}}}{binding})
def {identifier}(flag,detail): return {predicate}
{identifier}.rows(row(flag=True,detail={literal},expect=True,why='approval with baseline detail'),row(flag=False,detail={literal},expect=False,why='refusal with baseline detail'))
'''
    levels = list(names)
    if nested:
        levels = ['first', 'second']
        for leaf, middle in zip(names, levels):
            source += f'''# flowguard: sensor gate_{middle}(flag: flag, detail: detail, spare: spare) -> accepted: bool calibrated_by={testnode}
def {middle}(flag: bool, detail: {detail_type}, spare: bool) -> bool:
    if {leaf}_gate(flag, detail):
        return True
    return False
'''
            intent += f'''@rule('{middle.upper()}',decides='{middle}_ok',source='doc SPEC.txt "Each gate returns flag; detail is incidental."',fields={{'{leaf}_ok':bool,'spare':bool}},uses=[{leaf.upper()}])
def {middle.upper()}({leaf}_ok,spare): return {leaf}_ok
'''
    gates = ' and '.join((f'{level}({leaf}.flag, {leaf}.detail, {leaf}.spare)' if nested
                          else f'{leaf}_gate({leaf}.flag, {leaf}.detail)')
                         for leaf, level in zip(names, levels))
    hidden = ' + '.join(f'int({name}.detail)' for name in names)
    limit = children * (2 if detail_enum else 1)
    answer = f'({hidden} != {limit})' if coupled else 'True'
    source += f'''# flowguard: sensor approve({', '.join(name + ': data' for name in names)}) -> approved: bool calibrated_by={testnode}
def approve({', '.join(name + ': object' for name in names)}) -> bool:
    approved = {gates}
    if not approved:
        return False
    return {answer}
'''
    for field in fields:
        default = literal if field.endswith('_detail') else 'True' if field.endswith('_flag') else 'False'
        native += f'@pytest.fixture\ndef {field}(): return {default}\n'
    native += '# flowguard: event CASE(' + parameters + ') calibrated_by=' + testnode + '\n'
    native += 'def test_case(' + parameters + '):\n'
    for name in names:
        native += f'    {name}=SimpleNamespace(flag={name}_flag,detail={name}_detail' + (f',spare={name}_spare' if nested else '') + ')\n'
        native += f'    app.{name}_gate({name}_flag,{name}_detail)\n'
    if nested:
        for leaf, middle in zip(names, levels):
            native += f'    app.{middle}({leaf}_flag,{leaf}_detail,{leaf}_spare)\n'
    native += '    assert type(app.approve(' + ','.join(names) + ')) is bool\n'
    schema = ','.join(repr(name + '_ok') + ':bool' for name in levels)
    arguments = ','.join(name + '_ok' for name in levels)
    condition = ' and '.join(name + '_ok' for name in levels)
    intent += f'''@rule('TOP',decides='approved',source='doc SPEC.txt "Approval is exactly the conjunction of the gate outcomes."',fields={{{schema}}},uses=[{','.join(name.upper()for name in levels)}])
def TOP({arguments}): return {condition}
TOP.rows(row({','.join(name + '_ok=True'for name in levels)},expect=True,why='approved outcomes are sufficient together'))
'''
    nodes = ["Node('case','CASE')"]
    nodes += [f"Node('{name}','gate_{name}',phase='return',model='{name.upper()}',caller='case')" for name in names]
    if nested:
        nodes += [f"Node('{name}','gate_{name}',phase='return',model='{name.upper()}',caller='case')" for name in levels]
    nodes += ["Node('approval','approve',phase='return',caller='case')", "Node('done','CASE',phase='return')"]
    chain = ['case', *names, *(levels if nested else []), 'approval', 'done']
    relations = [f"Relation('{name.upper()}',{{'flag':Read('case','arg.{name}_flag'),'detail':Read('case','arg.{name}_detail')}},Read('{name}'),on='{name}')" for name in names]
    if nested:
        relations += [f"Relation('{middle.upper()}',{{'{leaf}_ok':Read('{leaf}'),'spare':Read('case','arg.{leaf}_spare')}},Read('{middle}'),on='{middle}')" for leaf,middle in zip(names,levels)]
    relations += ["Relation('TOP',{" + ','.join(repr(name + '_ok') + f":Read('{name}')"for name in levels) + "},Read('approval'),on='approval')"]
    intent += "flow('JOINT',source='doc SPEC.txt \"Approval is exactly the conjunction of the gate outcomes.\"',nodes=[" + ','.join(nodes) + '],edges=' + repr(list(zip(chain,chain[1:]))) + ',relations=[' + ','.join(relations) + '])\n'
    (root / (module + '.py')).write_text(source)
    (root / testnode.split('::')[0]).write_text(native)
    (root / 'tests/intent/policy.py').write_text(intent)
    model = load(load_config(root))
    assert not model.errors, model.errors
    return model, Engine(model)


@contextmanager
def native(engine):
    """Use the same verified source and calibration lifetime as the pytest plugin."""
    from flowguard.intent.anchors import _execution_session as actual_session
    from flowguard.intent import calibration
    facts = engine.__dict__.setdefault('_native_test_facts', {})
    with actual_session(engine.m.cfg.root), calibration._execution_session(engine.m.cfg.root, facts=facts):
        for rule in engine.m.rules.values():
            for binding in rule.homes:
                if hasattr(binding, 'scenario'):
                    prepared = calibration._prepare_scenario(engine.m.cfg.root, binding)
                    assert prepared['status'] == 'ok', (rule.id, prepared)
        yield

def parts(model, engine, identifier):
    rule = model.rules[identifier]
    with native(engine):
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
    with native(engine):
        result = engine.run_home(model.rules['TOP'], model.rules['TOP'].homes[0], 'cells')
    assert result['verdict'] == 'red', result
    assert any('depends on more' in reason for reason in result['red'])
    assert result['composition']['parent_calls'] == 36
    assert result['composition']['finite_domain']


def test_an_unreadable_lower_domain_does_not_claim_joint_coverage(tmp_path):
    model, engine = project(tmp_path, unreadable=True)
    with native(engine):
        result = engine.run_home(model.rules['TOP'], model.rules['TOP'].homes[0], 'cells')
    assert result['verdict'] == 'grey', result
    assert any('complete rules' in reason for reason in result['grey'])
    assert not result['composition']['checked_all_witnesses']
    assert not result['composition']['finite_domain']


def test_joint_detail_choices_continue_through_nested_uses(tmp_path):
    model, engine = project(tmp_path, coupled=True, nested=True)
    assert not model.errors, model.errors
    for identifier in ('LEFT', 'RIGHT', 'FIRST', 'SECOND'):
        assert all(result['verdict'] == 'ok' for result in parts(model, engine, identifier))
    with native(engine):
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
