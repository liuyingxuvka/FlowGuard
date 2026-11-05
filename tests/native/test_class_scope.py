"""Executed business class cells are observed; unused toolchain metadata is not instance state."""
from pathlib import Path

import pytest
from flowguard.native import session


def program(tmp_path, operation='self.schema.count += 1; return self.schema.count'):
    (tmp_path / 'program.py').write_text(f'''from abc import ABC
class Schema(ABC):
    counter = 0
    values = []
    def __init__(self): self.count = 0
    @classmethod
    def validate(cls): return cls()
class Program:
    def __init__(self): self.schema = Schema.validate()
    def run(self):
        {operation}
''')
    return {'root':str(tmp_path), 'system':'program:Program', 'classes':['program:Program','program:Schema','abc:ABC']}


def test_unused_abc_class_metadata_does_not_replace_the_business_instance_graph(tmp_path):
    spec = program(tmp_path)
    result = session.replay(spec, [{'name':'run'}])
    assert result['steps'][0]['outcome'] == 'success'
    nodes = result['steps'][0]['after']['graph']['nodes']
    schema = next(node for node in nodes if node['type']=='program:Schema')
    assert dict(schema['attributes'])['count'] == 1
    assert all(node['type']!='_abc:_abc_data' for node in nodes)
    restored = session.restore(spec, [{'name':'run'}], result['final'], tail=[{'name':'run'}])
    assert restored['steps'][1]['value']['root'] == 2


@pytest.mark.parametrize('operation', [
    'Schema.counter += 1; return Schema.counter',
    'Schema.values.append(1); return len(Schema.values)',
])
def test_business_class_cell_mutation_remains_unsupported(tmp_path, operation):
    with pytest.raises(session.UnsupportedWorld, match='class/global/closure'):
        session.replay(program(tmp_path, operation), [{'name':'run'}])


def test_explicitly_consumed_opaque_class_cell_remains_unknown(tmp_path):
    with pytest.raises(session.UnsupportedWorld, match='opaque state: _abc:_abc_data'):
        session.replay(program(tmp_path, 'return Schema._abc_impl'), [{'name':'run'}])


def test_dynamic_class_namespace_access_has_no_fabricated_snapshot(tmp_path):
    with pytest.raises(session.UnsupportedWorld, match='dynamic class namespace'):
        session.replay(program(tmp_path, "getattr(Schema, 'values').append(1); return 1"), [{'name':'run'}])
