"""Real history comparisons preserve their first scope; candidate absence is model-only."""
from pathlib import Path
from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('self conflict history',covers=['.flowguard/selfuse/owners.py:HistoryFlow','flowguard/flow/history.py'])
CASES=('complete','capped','smaller','reproduced','missing_obligation')
m.field('history_case',('unseen',*CASES),'unseen',source='R15')
m.field('outcome',('open','retain','model_absent'),'open',source='R15')
m.field('baseline_kept',(True,),True,source='R15')
m.field('claim',('model_only',),'model_only',source='R15')
@m.action(case=CASES,source='R15')
def compare(s,case):
    s['history_case']=case
    s['outcome']='model_absent' if case=='complete' else 'retain'
@m.action(source='R15')
def rediscover(s):
    pass
m.always('capped and smaller scopes retain the original conflict',lambda s:
         s['history_case'] not in ('capped','smaller','reproduced','missing_obligation') or s['outcome']=='retain',source='R15')
m.always('rediscovery preserves the original baseline',lambda s:s['baseline_kept'],source='R15')
m.always('model absence does not claim a native code fix',lambda s:s['claim']=='model_only',source='R15')
m.reach('a complete retained scope is an absence candidate',lambda s:s['outcome']=='model_absent',source='R15')
m.after('the requested stimulus is recorded','compare',lambda before,after,case:after['history_case']==case)
m.bind_adapter({'root':str(Path(__file__).parents[1]/'selfuse'),'system':'owners:HistoryFlow','classes':['owners:HistoryFlow']},
               state=lambda snapshot:fields(snapshot,names=('history_case','outcome','baseline_kept','claim')),
               operations={'compare':'compare','rediscover':'rediscover'})
MODEL=m
