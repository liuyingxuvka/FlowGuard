"""One shard executes its assigned nodes once, unless its invocation deadline has elapsed."""
from dataclasses import dataclass,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='shard_run'
PARENT='shard_suite'
IMPLEMENTED_BY={'RunShard':'flowguard/pytest_shards_cli.py:_run_one_shard'}
OUTPUTS={'shard':('pass','fail','partial','timeout')}
TESTED_BY = {'exit_code_decides_the_shard': ['tests/test_pytest_shard_runner.py:test_one_shard_status_follows_its_tests'], 'deadline_marks_timeout': ['tests/test_pytest_shard_runner.py:test_one_shard_past_its_deadline_is_a_timeout'], 'runs_exactly_the_assigned_nodes': ['tests/test_pytest_shard_runner.py:test_one_shard_runs_exactly_its_nodes']}
EXPECTED={'all_pass':'pass','one_fails':'fail','one_skips':'partial','past_deadline':'timeout'}
@dataclass(frozen=True)
class State:
    outcome:str='all_pass'
    nodes_run:str='none'
    shard:str='timeout'
class RunShard:
    name='RunShard'
    reads=('outcome',)
    writes=('nodes_run','shard')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        shard=EXPECTED[state.outcome]
        nodes='none' if state.outcome=='past_deadline' else 'assigned'
        if self.defect=='passes_on_nonzero_exit' and state.outcome=='one_fails':shard='pass'
        if self.defect=='runs_past_the_deadline' and state.outcome=='past_deadline':shard='pass';nodes='assigned'
        if self.defect=='runs_unassigned_nodes' and state.outcome!='past_deadline':nodes='extra'
        return (FunctionResult(shard,replace(state,nodes_run=nodes,shard=shard)),)
RULES=(
 Invariant('exit_code_decides_the_shard','failures and required skips keep their status',lambda s,t:s.outcome=='past_deadline' or s.shard==EXPECTED[s.outcome]),
 Invariant('deadline_marks_timeout','an expired deadline starts no pytest',lambda s,t:s.outcome!='past_deadline' or s.shard=='timeout' and s.nodes_run=='none'),
 Invariant('runs_exactly_the_assigned_nodes','a started shard executes only its assigned nodes',lambda s,t:s.outcome=='past_deadline' or s.nodes_run=='assigned'),
)
def make(defect=''):return Explorer(Workflow((RunShard(defect),)),tuple(State(outcome=outcome,shard=initial) for outcome in EXPECTED for initial in ('pass','timeout')),('run',),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('passes_on_nonzero_exit','runs_past_the_deadline','runs_unassigned_nodes')}
def conformance():
    from _shard_fixture import one_shard
    facts=[]
    for case,value in EXPECTED.items():
        with TemporaryDirectory(prefix='fg-one-shard-') as directory:
            row,projection,nodes=one_shard(Path(directory),case)
            actual='timeout' if row['status']=='blocked' and row['deadline_exhausted'] else row['status']
            valid=actual==value and row['executed_count']==(0 if case=='past_deadline' else len(nodes))
            valid &= (projection is None and not Path(row['stdout_path']).exists() if case=='past_deadline' else row['exact_selection'] and set(projection['node_ids'])==set(nodes))
            facts.append(Fact(case,bool(valid),repr(row)))
    return CodeFactsReport(tuple(facts))
