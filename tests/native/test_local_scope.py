"""Per-invocation helper cells are temporary; escaped/global cells stay guarded."""
import pytest
from flowguard.native import session


def program(tmp_path, helpers, call):
    (tmp_path/'program.py').write_text(helpers+f'''
class Program:
    def __init__(self): self.value=0
    def run(self):
        self.value={call}
        return self.value
''')
    return {'root':str(tmp_path),'system':'program:Program','classes':['program:Program']}


@pytest.mark.parametrize('helpers,call,expected',[
    ('''def collect():
    findings=[]
    def add(value): findings.append(value)
    add(1); add(2)
    return sum(findings)
''','collect()',3),
    ('''def collect():
    count=0
    def add():
        nonlocal count
        count+=1
    add(); add()
    return count
''','collect()',2),
    ('''def collect(depth):
    findings=[]
    def add(value): findings.append(value)
    add(1)
    if depth: add(collect(depth-1))
    return sum(findings)
''','collect(3)',4),
])
def test_fresh_live_lexical_cells_can_change(tmp_path,helpers,call,expected):
    result=session.replay(program(tmp_path,helpers,call),[{'name':'run'},{'name':'run'}])
    assert [row['value']['root'] for row in result['steps']]==[expected,expected]


@pytest.mark.parametrize('helpers,call',[
    ('''def factory():
    values=[]
    def change():
        values.append(1)
        return len(values)
    return change
change=factory()
''','change()'),
    ('''def factory():
    count=0
    def change():
        nonlocal count
        count+=1
        return count
    return change
change=factory()
''','change()'),
    ('''VALUES=[]
def collect():
    values=VALUES
    def change(): values.append(1)
    change()
    return len(values)
''','collect()'),
])
def test_persistent_or_global_alias_cells_remain_unsupported(tmp_path,helpers,call):
    with pytest.raises(session.UnsupportedWorld,match='class/global/closure'):
        session.replay(program(tmp_path,helpers,call),[{'name':'run'}])
