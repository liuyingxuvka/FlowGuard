"""Check verdicts come from the production owner, including finished UNKNOWN."""
from pathlib import Path
from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('self check workflow',covers=['.flowguard/selfuse/owners.py:CheckFlow','flowguard/flow/cli.py','flowguard/flow/jobs.py:Outcome'])
CASES=('running','clean','conflict','error','capped','native_unknown')
m.field('check_case',('unseen',*CASES),'unseen',source='R15')
m.field('exit',(0,1,2,3,4),4,source='R15')
m.field('finished',(False,True),False,source='R15')
@m.action(case=CASES,source='R15')
def inspect(s,case):
    s['check_case']=case
    s['exit']={'running':4,'clean':0,'conflict':1,'error':2,'capped':3,'native_unknown':3}[case]
    s['finished']=case!='running'
m.always('running work has no final verdict',lambda s:s['finished'] or s['exit']==4,source='R15')
m.always('conflicts and errors block a clean result',lambda s:
         s['check_case'] not in ('conflict','error') or s['exit'] in (1,2),source='R15')
m.always('finished uncertainty remains visible',lambda s:
         s['check_case'] not in ('capped','native_unknown') or (s['finished'] and s['exit']==3),source='R15')
m.progress('work can finish cleanly',lambda s:not s['finished'],lambda s:s['exit']==0,source='R15')
m.after('the requested stimulus is recorded','inspect',lambda before,after,case:after['check_case']==case)
m.bind_adapter({'root':str(Path(__file__).parents[1]/'selfuse'),'system':'owners:CheckFlow','classes':['owners:CheckFlow']},
               state=lambda snapshot:fields(snapshot,names=('check_case','exit','finished')),operations={'inspect':'inspect'})
MODEL=m
