"""Removed interface literals and promises name their consumers or new owners."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _literal_fixture import native_case
MODEL_ID='literal_consumers'
PARENT = 'change_selection'
IMPLEMENTED_BY={'Sites':'flowguard/map/discover.py:literal_sites'}
USES={'Impact':'flowguard/map/impact.py:compute_impact','Rules':'flowguard/map/facets.py:target_goal_rules'}
TESTED_BY = {'removed_literal_names_consumers': ['tests/test_flowguard_map_discover.py:test_s4a_rename_names_the_consumers'], 'removed_promise_is_named': ['tests/test_flowguard_map_discover.py:test_removed_rule_known_bad_and_test_are_promises'], 'moved_rule_is_not_a_removed_promise': ['tests/test_flowguard_map_discover.py:test_moved_rule_prints_moved_not_promise']}
@dataclass(frozen=True)
class Observation:
    edit:str=''
    literals:str='none'
    removed:bool=False
    moved:bool=False
class Inspect:
    name='Inspect'
    reads=()
    writes=('edit','literals','removed','moved')
    def __init__(self,defect=''): self.defect=defect
    def apply(self,event,state):
        value=Observation(event,'sites' if event=='literal' else 'too_common' if event=='common' else 'none',event=='removed',event=='moved')
        if self.defect=='ignores_removed_literal' and event=='literal': value=Observation(event)
        if self.defect=='drops_rule_silently' and event=='removed': value=Observation(event)
        if self.defect=='reports_moved_rule_as_removed' and event=='moved': value=Observation(event,removed=True)
        return (FunctionResult(value.literals,value),)
RULES=(
 Invariant('removed_literal_names_consumers','a removed produced literal names real consumers',lambda s,t:s.edit!='literal' or s.literals=='sites'),
 Invariant('removed_promise_is_named','removed rules are named',lambda s,t:s.edit!='removed' or s.removed),
 Invariant('moved_rule_is_not_a_removed_promise','a moved rule is named as moved, not retired',lambda s,t:s.edit!='moved' or s.moved and not s.removed),
)
def make(defect=''): return Explorer(Workflow((Inspect(defect),)),(Observation(),Observation(literals='sites')),('literal','removed','moved','common'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(name) for name in ('ignores_removed_literal','drops_rule_silently','reports_moved_rule_as_removed')}
def conformance():
    facts=[]
    for case in ('literal','removed','moved'):
        with TemporaryDirectory(prefix='fg-literal-consumers-') as folder:
            impact,text=native_case(Path(folder),case)
            correct=(text.count("consumes 'stale' (produced by producer):")>=2 if case=='literal' else 'promises: policy:' in text and '-rule safe' in text if case=='removed' else 'moved:' in text and 'from policy to recipient' in text and 'promises: policy:' not in text)
            facts.append(Fact(case,correct,text))
    with TemporaryDirectory(prefix='fg-common-literal-') as folder:
        from _literal_fixture import fixture, write
        from flowguard.map.inventory import build_inventory
        from flowguard.map.common import DEFAULT_IGNORE
        from flowguard.map.impact import compute_impact, render_impact
        root=Path(folder);data=fixture(root)
        for index in range(21): write(root,f'consumer_{index}.py','def use(value): return value == "stale"\n')
        write(root,'producer.py','def emit(): return "updated"\n')
        impact=compute_impact(root,data,build_inventory(root,DEFAULT_IGNORE,write_cache=False),['producer.py'],base='HEAD')
        text=render_impact(impact)
        facts.append(Fact('too_common','too common to list' in text,text))
    return CodeFactsReport(tuple(facts))

COMPONENTS = ['map-discover']

OUTPUTS = {'literals': ('sites', 'too_common', 'none')}
