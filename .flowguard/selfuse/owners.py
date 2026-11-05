"""Finite input stimuli around production owners; no verdict/history/quote policy lives here.

History observations are explicit API inputs, not registered computation evidence.
Integration controls also feed receipts derived by the real checker through the same driver.
"""
from copy import deepcopy
import json
from pathlib import Path
from flowguard.flow.cli import Assembled, ModelView, verdict
from flowguard.flow.jobs import Outcome, Planned
from flowguard.flow.parts import PartResult, PartSpec
from flowguard.flow.checks import CONFLICT, ERROR_CLS, make_finding
from flowguard.flow import history
from flowguard.map.requests import quote_matches, literal_subject_match

_REQUEST = Path(__file__).parent.parent/'requests'/'R15.md'


class CheckFlow:
    def __init__(self):
        self.check_case, self.exit, self.finished = 'unseen', 4, False
        self.line = ''

    def inspect(self, case):
        item = Planned(PartSpec('core','self'), '.flowguard/flow/self.py')
        part = PartResult('core','self','contract-input',case!='capped',[],
                          {'loaded':True,'reach':{'cut':0},'unknown':[],
                           'native':{'status':'unknown' if case=='native_unknown' else 'conformant'}},[])
        outcome = Outcome([item],[None if case=='running' else part],[False],[None],case!='running')
        view = ModelView('self',[(item,outcome.results[0],False,None)])
        conflicts = [make_finding('BROKEN',CONFLICT,'self','self verdict','finite conflict input',sources=['R15'])] if case=='conflict' else []
        errors = [make_finding('MODEL ERROR',ERROR_CLS,'self','self verdict','finite error input')] if case=='error' else []
        assembled = Assembled(outcome,{'self':view},conflicts,[],errors,{f.id for f in conflicts},1)
        self.line, self.exit = verdict(assembled,'check')
        self.check_case, self.finished = case, outcome.finished


def history_inputs():
    definition = history.definition_digest('need(at_main)\n')
    baseline = dict(receipt='finite-baseline-input',finished=True,loaded=True,complete=True,errors=0,
        scope=dict(model='self-contract',members=['self-contract'],bounds={'item':2},starts=['initial','saved'],
                   coverage={'actions':['repair'],'field:state':['broken','ready']}),
        obligations=[dict(id='repair_guard',kind='guard',sources=['R15'],definition=definition,
                          cases={'main':True,'branch':False})],replay='not_run')
    entry = dict(id='self-history-contract',kind='STUCK',model='self-contract',subject='state = broken',sources=['R15'])
    cases = {name:deepcopy(baseline) for name in ('complete','capped','smaller','reproduced','missing_obligation')}
    for name,value in cases.items(): value['receipt']='finite-'+name+'-input'
    cases['capped']['complete']=False
    cases['smaller']['scope']['bounds']['item']=1
    cases['reproduced']['replay']='reproduced'
    cases['missing_obligation']['obligations']=[]
    return dict(entry=entry,baseline=baseline,cases=cases)


class HistoryFlow:
    def __init__(self):
        source = Path('history-inputs.json')
        inputs = json.loads(source.read_text()) if source.exists() else history_inputs()
        self.inputs = inputs['cases']
        self.entry = history.bind(inputs['entry'],inputs['baseline'])
        self.original = deepcopy(self.entry['history']['baseline'])
        self.history_case, self.outcome, self.claim = 'unseen', 'open', 'model_only'
        self.baseline_kept = self.entry['history']['baseline']==self.original

    def compare(self, case):
        self.entry = history.compared(self.entry,self.inputs[case])
        self.history_case = case
        self.outcome = self.entry['history']['latest']['outcome']
        self.claim = self.entry['history']['latest']['claim']
        self.baseline_kept = self.entry['history']['baseline']==self.original

    def rediscover(self):
        self.entry = history.bind(self.entry,self.inputs['complete'],previous=self.entry)
        self.baseline_kept = self.entry['history']['baseline']==self.original


class OwnerWords:
    def __init__(self):
        self.words = _REQUEST.read_bytes()
        self.quote_case, self.quoted, self.subject, self.bytes_kept = 'unseen', False, False, True

    def inspect(self, case):
        text = self.words.decode('utf-8')
        quotes = {'verbatim':text,'elided':text[:2]+'...'+text[text.index('GitHub'):],
                  'forged':'Invented requirement for GitHub.','unrelated':text[:4]}
        quote = quotes[case]
        self.quoted = quote_matches(text,quote)
        self.subject,_ = literal_subject_match(quote,['GitHub'])
        self.bytes_kept = _REQUEST.read_bytes()==self.words
        self.quote_case = case
