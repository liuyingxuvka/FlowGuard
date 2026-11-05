"""Source-bound function references are data, without claiming shared heap copies are safe."""
import importlib.util
import sys
import types

import pytest

from flowguard.native import session

SOURCE = '''class Operators:
    def ge(left, right=2, *, shift=0): return left >= right + shift
OPS = {'ge': Operators.ge, 'alias': Operators.ge}
class Program:
    def __init__(self):
        self.saved = OPS['ge']
        self.alias = self.saved
        self.count = 0
    def run(self, value):
        self.count += 1
        return OPS['ge'](value)
'''


def program(tmp_path, source=SOURCE):
    (tmp_path / 'program.py').write_text(source)
    return {'root': str(tmp_path), 'system': 'program:Program', 'classes': ['program:Program']}


def test_real_dispatch_calls_keep_function_alias_data_and_public_prefix_restore(tmp_path):
    spec = program(tmp_path)
    prefix = [{'name': 'run', 'args': [3]}]
    actual = session.replay(spec, prefix)
    assert actual['steps'][0]['value']['root'] is True
    nodes = actual['initial']['graph']['nodes']
    instance = next(node for node in nodes if node['type'] == 'program:Program')
    fields = dict(instance['attributes'])
    assert fields['saved'] == fields['alias']
    function = nodes[fields['saved']['ref']]
    assert function['module'] == 'program' and function['qualname'] == 'Operators.ge'
    assert function['source'] == 'program.py' and len(function['code_sha256']) == 64
    assert nodes[function['defaults']['ref']]['items'] == [2]
    assert nodes[function['kwdefaults']['ref']]['items'] == [['shift', 0]]
    restored = session.restore(spec, prefix, actual['final'], tail=[{'name': 'run', 'args': [1]}])
    assert restored['steps'][-1]['value']['root'] is False
    assert dict(next(n for n in restored['final']['graph']['nodes'] if n['type'] == 'program:Program')['attributes'])['count'] == 2


@pytest.mark.parametrize('mutation', [
    "OPS['ge'] = replacement",
    "OPS['ge'].__code__ = OPS['ge'].__code__.replace(co_consts=(None, 100))",
    "OPS['ge'].__defaults__ = (100,)",
    "OPS['ge'].__kwdefaults__['shift'] = 100",
    "OPS['ge'].marker = 100",
])
def test_consumed_dispatch_function_changes_remain_ambient_mutations(tmp_path, mutation):
    source = SOURCE.replace('class Program:', 'def replacement(left, right=2, *, shift=0): return False\nclass Program:')
    source = source.replace("self.count += 1", mutation)
    with pytest.raises(session.UnsupportedWorld, match='class/global/closure'):
        session.replay(program(tmp_path, source), [{'name': 'run', 'args': [3]}])


def test_shared_function_checkpoint_remains_rejected(tmp_path, monkeypatch):
    spec = program(tmp_path)
    original = session.run_isolated_process
    def controlled(command, **kwargs):
        command = list(command)
        command[2] = '''from flowguard.native import session as native
reset = native._Session.reset
def checked(self, *args, **kwargs):
    reset(self, *args, **kwargs)
    self.checkpoint()
native._Session.reset = checked
''' + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(session, 'run_isolated_process', controlled)
    with pytest.raises(session.UnsupportedWorld, match='shares mutable state'):
        session.replay(spec, [])


@pytest.mark.parametrize('value', [
    '(lambda: (lambda value: value))()',
    '(lambda state: (lambda value: value + state))(2)',
    'len',
])
def test_closures_local_functions_and_external_callables_remain_unknown(tmp_path, value):
    source = SOURCE.replace("self.saved = OPS['ge']", 'self.saved = ' + value)
    with pytest.raises(session.UnsupportedWorld, match='opaque state'):
        session.replay(program(tmp_path, source), [])


def test_same_code_replacement_has_transient_identity_without_wire_addresses(tmp_path, monkeypatch):
    source = SOURCE + '\nimport sys\ndef frame():\n    OPS\n    return sys._getframe()\n'
    spec = program(tmp_path, source)
    module_spec = importlib.util.spec_from_file_location('program', tmp_path / 'program.py')
    module = importlib.util.module_from_spec(module_spec)
    monkeypatch.setitem(sys.modules, 'program', module)
    module_spec.loader.exec_module(module)
    monkeypatch.setattr(session, '_ACTIVE_SOURCE_ROOT', tmp_path)
    frame = module.frame()
    observed = session._ObservedState(spec, tmp_path)
    before, identities = observed.capture(frame)
    original = module.Operators.ge
    replacement = types.FunctionType(original.__code__, original.__globals__, original.__name__, original.__defaults__)
    replacement.__qualname__ = original.__qualname__
    replacement.__module__ = original.__module__
    replacement.__kwdefaults__ = original.__kwdefaults__
    module.Operators.ge = replacement
    module.OPS.update(ge=replacement, alias=replacement)
    after, changed = observed.capture(frame)
    assert before == after  # Identical code/data has a stable portable observation.
    assert identities != changed  # The existing ambient identity check still sees replacement.
    assert str(id(original)) not in str(before) and str(id(replacement)) not in str(after)

CLASS_CELL_SOURCE = '''class Base:
    def ge(self, other): return self.value >= other
class Operators(Base):
    def __init__(self): self.value = 2
    def ge(self, other): return super().ge(other)
OPS = {'ge': Operators.ge, 'alias': Operators.ge}
class Program:
    def __init__(self):
        self.operator = Operators()
        self.saved = OPS['ge']
        self.alias = self.saved
    def run(self, value): return OPS['ge'](self.operator, value)
'''


def test_compiler_class_cell_is_a_source_declaration_not_business_closure(tmp_path):
    spec = program(tmp_path, CLASS_CELL_SOURCE)
    spec['classes'] += ['program:Base', 'program:Operators']
    prefix = [{'name': 'run', 'args': [1]}]
    actual = session.replay(spec, prefix)
    assert actual['steps'][0]['value']['root'] is True
    function = next(n for n in actual['initial']['graph']['nodes'] if n['type'] == 'builtins:function')
    assert function['class_cell'] == 'program:Operators'
    restored = session.restore(spec, prefix, actual['final'], tail=[{'name': 'run', 'args': [3]}])
    assert restored['steps'][-1]['value']['root'] is False


@pytest.mark.parametrize('mutation', [
    "OPS['ge'].__closure__[0].cell_contents = Base",
    "del OPS['ge'].__closure__[0].cell_contents",
])
def test_class_cell_cannot_point_elsewhere_or_be_empty(tmp_path, mutation):
    source = CLASS_CELL_SOURCE.replace("def run(self, value): return", "def run(self, value):\n        " + mutation + "\n        return")
    spec = program(tmp_path, source)
    spec['classes'] += ['program:Base', 'program:Operators']
    with pytest.raises(session.UnsupportedWorld, match='opaque state: builtins:function'):
        session.replay(spec, [{'name': 'run', 'args': [1]}])
