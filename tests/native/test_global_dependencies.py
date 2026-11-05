"""Global bytecode accesses stay distinct from same-named instance attributes."""
import calendar
import hashlib
from pathlib import Path

import pytest

from flowguard.native import session


def program(tmp_path, source):
    (tmp_path / 'program.py').write_text(source, encoding='utf-8')
    return {'root': str(tmp_path), 'system': 'program:Program', 'classes': ['program:Program']}


def test_actual_calendar_keeps_unread_module_method_alias_outside_instance_state(tmp_path):
    source = Path(calendar.__file__).read_bytes()
    target = tmp_path / 'calendar_subject.py'
    target.write_bytes(source)
    spec = {'root': str(tmp_path), 'system': 'calendar_subject:Calendar',
            'classes': ['calendar_subject:Calendar'], 'capture_shape': {'wire': 2, 'queries': {}}}
    calls = [{'name': 'getfirstweekday'}, {'name': 'setfirstweekday', 'args': [-8]},
             {'name': 'getfirstweekday'}, {'name': 'setfirstweekday', 'args': [8]},
             {'name': 'getfirstweekday'}]
    actual = session.replay(spec, calls)
    assert [row['value']['root'] for row in actual['steps']] == [0, None, 6, None, 1]
    assert all(row['outcome'] == 'success' for row in actual['steps'])
    assert actual['rule_captures']['native_evidence']['status'] == 'current'
    functions = {event['function'] for row in actual['steps'] for event in row['events']}
    assert {'Calendar.getfirstweekday', 'Calendar.setfirstweekday'} <= functions
    instance = next(node for node in actual['final']['graph']['nodes']
                    if node['type'] == 'calendar_subject:Calendar')
    assert dict(instance['attributes']) == {'_firstweekday': 8}
    assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(source).digest()


def test_attribute_read_and_write_do_not_consume_same_named_global_method(tmp_path):
    spec = program(tmp_path, '''class Other:
    def value(self): raise AssertionError('unused ambient method was called')
value = Other().value
class Program:
    def __init__(self): self.value = 0
    def run(self):
        self.value += 1
        return self.value
''')
    actual = session.replay(spec, [{'name': 'run'}, {'name': 'run'}])
    assert [row['value']['root'] for row in actual['steps']] == [1, 2]


@pytest.mark.parametrize('body', [
    'return value()',
    'class Selected:\n            result = value\n        return 1',
])
def test_actual_global_and_name_reads_keep_opaque_method_unknown(tmp_path, body):
    spec = program(tmp_path, '''class Other:
    def value(self): raise AssertionError('opaque method must not be invoked')
value = Other().value
class Program:
    def run(self):
        ''' + body + '\n')
    with pytest.raises(session.UnsupportedWorld, match='opaque state: builtins:method'):
        session.replay(spec, [{'name': 'run'}])


@pytest.mark.parametrize('body', [
    'global VALUE\n        VALUE = 2\n        return 1',
    'VALUE.append(2)\n        return len(VALUE)',
    'helper.marker = 2\n        return helper()',
    'def nested():\n            VALUE.append(2)\n        nested()\n        return 1',
])
def test_actual_global_writes_function_data_and_nested_reads_stay_guarded(tmp_path, body):
    spec = program(tmp_path, '''VALUE = []
def helper(): return 1
class Program:
    def run(self):
        ''' + body + '\n')
    with pytest.raises(session.UnsupportedWorld, match='class/global/closure'):
        session.replay(spec, [{'name': 'run'}])


def test_nested_function_can_read_actual_scalar_global(tmp_path):
    spec = program(tmp_path, '''VALUE = 7
def helper(): return VALUE
class Program:
    def run(self):
        def nested(): return helper()
        return nested()
''')
    actual = session.replay(spec, [{'name': 'run'}])
    assert actual['steps'][0]['value']['root'] == 7
    assert any(event['function'] == 'helper' for event in actual['steps'][0]['events'])


def test_bound_method_actually_held_in_instance_state_remains_unknown(tmp_path):
    spec = program(tmp_path, '''class Program:
    def __init__(self): self.saved = self.run
    def run(self): return 1
''')
    with pytest.raises(session.UnsupportedWorld, match='opaque state: builtins:method'):
        session.replay(spec, [])


@pytest.mark.parametrize('body,expected', [
    ('import json\n        return json.loads("1")', 1),
    ('import json as codec\n        return codec.loads("1")', 1),
    ('from json import decoder\n        return len(decoder.WHITESPACE_STR)', 4),
    ('import os.path as paths\n        return paths.basename("dir/leaf")', 'leaf'),
    ('from json.decoder import JSONDecoder\n        return JSONDecoder().decode("1")', 1),
])
def test_known_local_import_binding_does_not_change_ambient_state(tmp_path, body, expected):
    spec = program(tmp_path, '''class Program:
    def run(self):
        ''' + body + '\n')
    spec['classes'].append('json.decoder:JSONDecoder')
    actual = session.replay(spec, [{'name': 'run'}, {'name': 'run'}])
    assert [row['value']['root'] for row in actual['steps']] == [expected, expected]


@pytest.mark.parametrize('body', [
    'import json\n        json.CONSUMED.append(2)\n        return 1',
    'from json.decoder import JSONDecoder\n        JSONDecoder.CONSUMED.append(2)\n        return 1',
])
def test_consumed_imported_module_and_class_mutation_remains_unknown(tmp_path, body):
    spec = program(tmp_path, '''import json
json.CONSUMED = [1]
json.decoder.JSONDecoder.CONSUMED = [1]
class Program:
    def run(self):
        ''' + body + '\n')
    spec['classes'].append('json.decoder:JSONDecoder')
    with pytest.raises(session.UnsupportedWorld, match='class/global/closure'):
        session.replay(spec, [{'name': 'run'}])


@pytest.mark.parametrize('lazy', [
    "Lazy('lazy_subject')",
    "types.ModuleType('lazy_subject')",
])
def test_unreached_local_import_does_not_invoke_a_lazy_module_attribute(tmp_path, lazy):
    spec = program(tmp_path, '''import json, types
class Lazy(types.ModuleType):
    def __getattribute__(self, name):
        raise AssertionError('opaque module attribute was invoked')
def opaque(name): raise AssertionError('opaque module attribute was invoked')
json.lazy_subject = LAZY
json.lazy_subject.__getattr__ = opaque
class Program:
    def __init__(self): self.enabled = False
    def run(self):
        if self.enabled:
            from json import lazy_subject
        return 1
'''.replace('LAZY', lazy))
    actual = session.replay(spec, [{'name': 'run'}])
    assert actual['steps'][0]['outcome'] == 'success'
    assert actual['steps'][0]['value']['root'] == 1


@pytest.mark.parametrize('field', ['__module__', '__qualname__', '__dict__', '__mro__', '__class__'])
def test_unreached_import_class_does_not_invoke_metaclass_getattribute(tmp_path, field):
    spec = program(tmp_path, '''import json
class Trap(type):
    def __getattribute__(self, name):
        if name == SELECTED_FIELD:
            raise AssertionError('unselected metaclass getter invoked:' + name)
        return type.__getattribute__(self, name)
class Opaque(metaclass=Trap): pass
json.review_lazy_class = Opaque
class Program:
    def __init__(self): self.enabled = False
    def run(self):
        if self.enabled:
            from json import review_lazy_class
        return 17
'''.replace('SELECTED_FIELD', repr(field)))
    actual = session.replay(spec, [{'name': 'run'}])
    assert actual['steps'][0]['outcome'] == 'success'
    assert actual['steps'][0]['value']['root'] == 17


@pytest.mark.parametrize('field', ['__module__', '__dict__', '__mro__', '__class__'])
def test_unreached_import_class_does_not_invoke_metaclass_descriptor(tmp_path, field):
    spec = program(tmp_path, '''import json
class Trap(type):
    @property
    def DESCRIPTOR_FIELD(self):
        raise AssertionError('unselected metaclass descriptor invoked')
class Opaque(metaclass=Trap): pass
json.review_lazy_class = Opaque
class Program:
    def __init__(self): self.enabled = False
    def run(self):
        if self.enabled:
            from json import review_lazy_class
        return 17
'''.replace('DESCRIPTOR_FIELD', field))
    actual = session.replay(spec, [{'name': 'run'}])
    assert actual['steps'][0]['outcome'] == 'success'
    assert actual['steps'][0]['value']['root'] == 17


@pytest.mark.parametrize('field', ['__name__', '__file__'])
def test_unreached_import_module_does_not_evaluate_custom_metadata_values(tmp_path, field):
    spec = program(tmp_path, '''import json, types
class Text(str):
    def startswith(self, *args): raise AssertionError('opaque module path invoked')
    def __radd__(self, other): raise AssertionError('opaque module name invoked')
subject = types.ModuleType('review_subject')
setattr(subject, SELECTED_FIELD, Text('review_subject'))
json.review_subject = subject
class Program:
    def __init__(self): self.enabled = False
    def run(self):
        if self.enabled:
            from json import review_subject
        return 17
'''.replace('SELECTED_FIELD', repr(field)))
    actual = session.replay(spec, [{'name': 'run'}])
    assert actual['steps'][0]['outcome'] == 'success'
    assert actual['steps'][0]['value']['root'] == 17
