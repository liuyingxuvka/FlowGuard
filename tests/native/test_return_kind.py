"""Completed return kinds describe exact builtins without touching custom values."""
from flowguard.native import session


def test_exact_return_kinds_preserve_scalar_facts_and_do_not_classify_unwind(tmp_path):
    (tmp_path/'program.py').write_text('''class Failure:
    def __getattribute__(self,name): raise AssertionError('custom attribute touched')
    def __bool__(self): raise AssertionError('custom bool touched')
def value(kind):
    if kind=='dict': return {'body':'private result body'}
    if kind=='list': return []
    if kind=='tuple': return ()
    if kind=='set': return set()
    if kind=='frozenset': return frozenset()
    if kind=='str': return ''
    if kind=='bytes': return b''
    if kind=='bool': return False
    if kind=='int': return 2
    if kind=='float': return 1.5
    if kind=='complex': return 1j
    if kind=='none': return None
    return Failure()
class Program:
    def run(self):
        for kind in ('dict','list','tuple','set','frozenset','str','bytes','bool','int','float','complex','none','other'):
            value(kind)
        return 2
    def crash(self): raise LookupError('actual SUT failure')
''')
    result=session.replay(dict(root=str(tmp_path),system='program:Program',classes=['program:Program']),
                          [dict(name='run'),dict(name='crash')])
    events=[event for event in result['steps'][0]['events'] if event['kind']=='return' and event['function']=='value']
    assert [event['return_kind'] for event in events]==['dict','list','tuple','set','frozenset','str','bytes','bool','int','float','complex','none','other']
    assert events[0]['result']['status']=='unknown' and 'return_fields' not in events[0]
    assert events[8]['result']=={'status':'current','value':2}
    assert events[-1]['result']['status']=='unknown'
    assert 'private result body' not in repr(events)
    unwind=[event for event in result['steps'][1]['events'] if event['kind']=='return' and event['function']=='Program.crash']
    assert unwind and all(event['return_status']=='raised' and 'return_kind' not in event for event in unwind)
