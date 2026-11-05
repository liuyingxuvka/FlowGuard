"""Compiled regex values are immutable data; source, flags and aliases remain evidence."""
from pathlib import Path
import pytest
from flowguard.native import session


def program(tmp_path):
    (tmp_path/'program.py').write_text('''import re
PATTERN = re.compile('abc', re.IGNORECASE)
class Program:
    def __init__(self):
        self.pattern = PATTERN
        self.alias = self.pattern
        self.binary = re.compile(b'abc', re.IGNORECASE)
        self.count = 0
    def match(self, text):
        self.count += 1
        return bool(self.pattern.fullmatch(text))
    def binary_match(self): return bool(self.binary.fullmatch(b'ABC'))
''')
    return {'root':str(tmp_path),'system':'program:Program','classes':['program:Program']}


def test_actual_regex_flags_bytes_aliases_and_public_prefix_restore(tmp_path):
    spec=program(tmp_path)
    result=session.replay(spec,[{'name':'match','args':['ABC']},{'name':'binary_match'}])
    assert [step['value']['root'] for step in result['steps']]==[True,True]
    nodes=result['initial']['graph']['nodes']
    instance=next(node for node in nodes if node['type']=='program:Program')
    attrs=dict(instance['attributes'])
    assert attrs['pattern']==attrs['alias']
    assert nodes[attrs['pattern']['ref']]['pattern']=='abc'
    assert nodes[attrs['pattern']['ref']]['flags'] & 2
    assert nodes[attrs['binary']['ref']]['pattern']=={'bytes':'YWJj'}
    restored=session.restore(spec,[{'name':'match','args':['ABC']},{'name':'binary_match'}],result['final'],tail=[{'name':'match','args':['x']}])
    assert restored['steps'][-1]['value']['root'] is False


def test_run_local_checkpoint_allows_shared_immutable_regex_but_preserves_aliases(tmp_path,monkeypatch):
    spec=program(tmp_path)
    original=session.run_isolated_process
    def controlled(command,**kwargs):
        command=list(command)
        command[2]='''from flowguard.native import session as native
reset=native._Session.reset
def checked(self,*args,**kwargs):
    reset(self,*args,**kwargs)
    checkpoint=self.checkpoint()
    self.step({'name':'match','args':['ABC']})
    self.restore_checkpoint(checkpoint)
    assert self.objects['system'].pattern is self.objects['system'].alias
    return self.current
native._Session.reset=checked
'''+command[2]
        return original(command,**kwargs)
    monkeypatch.setattr(session,'run_isolated_process',controlled)
    result=session.replay(spec,[{'name':'match','args':['ABC']}])
    assert result['steps'][0]['value']['root'] is True
    instance=next(node for node in result['final']['graph']['nodes'] if node['type']=='program:Program')
    assert dict(instance['attributes'])['count']==1


@pytest.mark.parametrize('value',['object()', 'lambda text: text'])
def test_regex_support_does_not_admit_opaque_objects_or_callbacks(tmp_path,value):
    spec=program(tmp_path)
    path=Path(spec['root'])/'program.py'
    path.write_text(path.read_text().replace('self.count = 0','self.count = 0\n        self.callback = '+value))
    with pytest.raises(session.UnsupportedWorld,match='opaque state'):
        session.replay(spec,[])
