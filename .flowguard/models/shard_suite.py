"""Partition, run and aggregate a complete suite; only completed runs update durations."""
from dataclasses import dataclass,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='shard_suite'
PARENT='test-mesh'
IMPLEMENTED_BY={'Run':'flowguard/pytest_shards_cli.py:run','Aggregate':'flowguard/pytest_shards.py:aggregate_pytest_projections'}
OUTPUTS={'suite':('pass','fail','partial','blocked')}
HANDOFF={'shard_partition':{'algorithm':'algorithm'},'shard_run':{'shard':'shard_results'}}
KEEPS=('coverage','collected','suite','recorded','record_written')
TESTED_BY = {'suite_passes_only_when_every_shard_passes': ['tests/test_pytest_shard_runner.py:test_suite_fails_when_one_shard_fails'], 'hash_partition_without_usable_record': ['tests/test_pytest_shard_runner.py:test_no_partial_or_corrupt_record_uses_the_hash_line'], 'durations_recorded_after_a_completed_run': ['tests/test_pytest_shard_runner.py:test_record_is_written_after_a_run_and_not_when_blocked']}
@dataclass(frozen=True)
class Case:
    coverage:str
    collected:str
    algorithm:str
    shards:tuple=('pass','pass')
CASES=tuple(Case(coverage,'ok',algorithm,shards) for coverage,algorithm in (('none','hash'),('partial','hash'),('full','subtrees')) for shards in (('pass','pass'),('pass','fail'),('fail','fail')))+tuple(Case(coverage,'error','hash') for coverage in ('none','full'))+(Case('full','ok','subtrees',('pass','partial')),Case('none','ok','hash',('pass','timeout')))
@dataclass(frozen=True)
class State:
    coverage:str='none'
    collected:str='ok'
    record:str='missing'
    algorithm:str='hash'
    shard_results:tuple=()
    suite:str='pass'
    recorded:bool=True
    record_written:bool=False
    @property
    def fallback(self):return self.collected=='error' or self.algorithm==('subtrees' if self.record=='usable' else 'hash')
class Collect:
    name='Collect'
    reads=()
    writes=('coverage','collected','record','shard_results')
    def apply(self,event,state):return (FunctionResult(event,replace(state,coverage=event.coverage,collected=event.collected,record='usable' if event.coverage=='full' else 'missing',shard_results=())),)
class Partition:
    name='Partition'
    reads=('collected','record')
    writes=('algorithm',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        if state.collected=='error':return (FunctionResult(event,state),)
        algorithm='hash' if self.defect=='hashes_despite_full_record' else event.algorithm
        return (FunctionResult(event,replace(state,algorithm=algorithm),label=algorithm),)
class RunFirst:
    name='RunFirst'
    reads=('collected',)
    writes=('shard_results',)
    def apply(self,event,state):
        if state.collected=='error':return (FunctionResult(event,state),)
        value=event.shards[0]
        return (FunctionResult(event,replace(state,shard_results=state.shard_results+(value,)),label=value),)
class RunSecond:
    name='RunSecond'
    reads=('collected','shard_results')
    writes=('shard_results',)
    def apply(self,event,state):
        if state.collected=='error':return (FunctionResult(event,state),)
        value=event.shards[1]
        return (FunctionResult(event,replace(state,shard_results=state.shard_results+(value,)),label=value),)
class Aggregate:
    name='Aggregate'
    reads=('collected','shard_results')
    writes=('suite','recorded','record_written')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        value='blocked' if state.collected=='error' or 'timeout' in state.shard_results else 'fail' if 'fail' in state.shard_results else 'partial' if 'partial' in state.shard_results else 'pass'
        if self.defect=='passes_with_failed_shard' and value=='fail':value='pass'
        written=value!='blocked' or self.defect=='records_blocked_run'
        # Preserve the moved clause's policy verdict, alongside the actual
        # record decision; the latter is also checked against real files.
        correct_record=written==(value!='blocked')
        return (FunctionResult(value,replace(state,suite=value,recorded=correct_record,record_written=written)),)
RULES=(
 Invariant('hash_partition_without_usable_record','full duration records select subtree balancing; otherwise hash',lambda s,t:s.fallback),
 Invariant('durations_recorded_after_a_completed_run','completed runs record durations; blocked collection does not',lambda s,t:s.recorded),
 Invariant('suite_passes_only_when_every_shard_passes','only every passing shard yields a passing suite',lambda s,t:s.suite!='pass' or s.collected=='ok' and all(value=='pass' for value in s.shard_results)),
)
def make(defect=''):return Explorer(Workflow((Collect(),Partition(defect),RunFirst(),RunSecond(),Aggregate(defect))),(State(),State(suite='blocked')),CASES,invariants=RULES,max_sequence_length=2,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {'hashes_despite_full_record':make('hashes_despite_full_record'),'records_blocked_run':make('records_blocked_run'),'passes_with_failed_shard':make('passes_with_failed_shard')}
def conformance():
    from _shard_fixture import suite_cases
    with TemporaryDirectory(prefix='fg-suite-') as directory:rows=suite_cases(Path(directory))
    return CodeFactsReport((
      Fact('fallback',rows['first_code']==rows['second_code']==0 and rows['first'].get('balance')=='hash' and rows['second'].get('balance')=='seconds',repr(rows)),
      Fact('failed',rows['fail_code']!=0 and rows['failed'].get('status')=='fail',repr(rows['failed'])),
      Fact('recorded',rows['recorded'] and rows['preserved'] and rows['blocked'].get('status')=='blocked',repr(rows)),
    ))
