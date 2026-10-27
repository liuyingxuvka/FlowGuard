"""Private cross-component calls are visible without changing code ownership."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,InvariantResult,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='private_use'
PARENT='map-check'
IMPLEMENTED_BY={'PrivateUse':'flowguard/map/lint.py:private_use_findings'}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
}
TESTED_BY = {'private_names_are_flagged': ['tests/test_private_use.py:test_lint_reports_private_names_used_across_components']}
@dataclass(frozen=True)
class State:
    event:str=''
    codes:tuple=()
class Check:
    name='PrivateUse'
    writes=('event','codes')
    def __init__(self,bad=False):self.bad=bad
    def apply(self,event,state):
        codes=('private_cross_component_use',) if event=='private_name_use' and not self.bad else ()
        return (FunctionResult(event,State(event,codes)),)
def _rule(name, events, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in events or predicate(state)
                     else InvariantResult.fail(message))
RULES=(_rule('private_names_are_flagged', {'private_name_use'}, lambda state: 'private_cross_component_use' in state.codes,
          'a private name used across components was not flagged'),)
def make(bad=False):return Explorer(Workflow((Check(bad),)),(State(),),('private_name_use','public'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {'misses_private_use':make(True)}
def conformance():
    from flowguard.map.lint import private_use_findings
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-private-') as directory:
        root=Path(directory)
        (root/'one.py').write_text('def _secret(): return 1\ndef public(): return 1\n')
        data={'components':[dict(id='one',files=['one.py'],depends_on=[]),dict(id='two',files=['two.py'],depends_on=['one'])]}
        facts=[]
        for symbol in ('_secret','public'):
            (root/'two.py').write_text(f'from one import {symbol}\ndef run(): return {symbol}()\n')
            inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
            actual=private_use_findings(root,data,inv)
            facts.append(Fact(symbol,bool(actual)==symbol.startswith('_'),repr(actual)))
        return CodeFactsReport(tuple(facts))
