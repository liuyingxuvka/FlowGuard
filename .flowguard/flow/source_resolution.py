"""A source change retires a requirement; it never claims the code was fixed."""
from flowguard.flow import Model, need
m=Model('source-bound requirement resolution')
CASES=('new_relevant_supersedes','old_quote_only','unrelated_quote','retired_new','edited_new','missing_supersedes','unchanged_bug','incomplete','native_mismatch','native_unknown')
m.field('phase',('open','changed','held'),'open')
m.field('case',('none',*CASES),'none')
m.field('original_kept',(True,),True)
m.field('code_fixed',(False,),False)
@m.action(case=CASES)
def reconsider(s,case):
    need(s['phase']=='open')
    s['case']=case
    s['phase']='changed' if case=='new_relevant_supersedes' else 'held'
@m.action()
def next_session(s):
    need(s['phase']!='open')
    s['phase'],s['case']='open','none'
m.always('old baseline remains',lambda s:s['original_kept'])
m.always('requirement change is not code repair',lambda s:not s['code_fixed'])
m.always('waivers cannot substitute for a source change',lambda s:s['phase']!='changed' or s['case']=='new_relevant_supersedes')
MODEL=m
