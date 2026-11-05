"""The production lexical owner checks the original request bytes, not invented authority."""
from pathlib import Path
from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('self owner words',covers=['.flowguard/selfuse/owners.py:OwnerWords','flowguard/map/requests.py'])
CASES=('verbatim','elided','forged','unrelated')
m.field('quote_case',('unseen',*CASES),'unseen',source='R15')
m.field('quoted',(False,True),False,source='R15')
m.field('subject',(False,True),False,source='R15')
m.field('bytes_kept',(True,),True,source='R15')
@m.action(case=CASES,source='R15')
def inspect(s,case):
    s['quote_case']=case
    s['quoted']=case!='forged'
    s['subject']=case!='unrelated'
m.always('invented words do not become the owner quote',lambda s:s['quote_case']!='forged' or not s['quoted'],source='R15')
m.always('an unrelated quote does not license this subject',lambda s:s['quote_case']!='unrelated' or not s['subject'],source='R15')
m.always('actual verbatim and elided words are accepted',lambda s:s['quote_case'] not in ('verbatim','elided') or (s['quoted'] and s['subject']),source='R15')
m.always('original owner bytes remain unchanged',lambda s:s['bytes_kept'],source='R15')
m.after('the requested stimulus is recorded','inspect',lambda before,after,case:after['quote_case']==case)
m.bind_adapter({'root':str(Path(__file__).parents[1]/'selfuse'),'system':'owners:OwnerWords','classes':['owners:OwnerWords']},
               state=lambda snapshot:fields(snapshot,names=('quote_case','quoted','subject','bytes_kept')),operations={'inspect':'inspect'})
MODEL=m
