"""A bounded field view joins model declarations, literal code sites and bound tests statically."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
import sys
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _relation_fixture import field_fixture
MODEL_ID='read_field'
PARENT = 'read_command'
IMPLEMENTED_BY={'Field':'flowguard/map/views.py:render_field'}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
    'Main': 'flowguard/__main__.py:main',
}
TESTED_BY = {'field_lists_writers_readers_rules': ['tests/test_read_field.py:test_read_field_status_names_writers_and_model', 'tests/test_read_field.py:test_json_key_written_and_read_across_components'], 'field_view_imports_no_model': ['tests/test_read_field.py:test_field_view_imports_no_model'], 'field_view_uncut': ['tests/test_read_field.py:test_field_view_is_complete']}
@dataclass(frozen=True)
class State:
    case:str=''
    field:str='unknown'
    correct:bool=True
    imported:bool=False
    complete: bool = True
class Show:
    name='Field'
    writes=('case','field','correct','imported','complete')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        value=State(event,'unknown' if event=='unknown' else 'listed',not(self.defect=='lists_subscript_store_as_read' and event=='json'),self.defect=='field_view_imports_a_model',False if self.defect=='field_view_cuts_lines' else True)
        return (FunctionResult(value.field,value),)
RULES=(
 Invariant('field_lists_writers_readers_rules','field code and model writers/readers/rules are listed',lambda s,t:s.case not in ('json','state') or s.correct),
 Invariant('field_view_imports_no_model','the field view imports no project model',lambda s,t:not s.imported),
 Invariant('field_view_uncut','each field view prints every section and line whole',lambda s,t:s.complete),
)
def make(defect=''):return Explorer(Workflow((Show(defect),)),(State(),State(field="listed")),('json','state','unknown'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('lists_subscript_store_as_read','field_view_imports_a_model','field_view_cuts_lines')}
def conformance():
    from flowguard.__main__ import main
    facts=[]
    with TemporaryDirectory(prefix='fg-field-') as directory:
        root=Path(directory);field_fixture(root)
        for case,name in (('json','record_code'),('state','status'),('unknown','missing_field')):
            output=StringIO();errors=StringIO()
            with redirect_stdout(output),redirect_stderr(errors):
                try:status=main(['read','--root',str(root),'--field',name])
                except SystemExit as exc:status=exc.code
            text=output.getvalue()+errors.getvalue()
            correct=(status==0 and 'code writes:' in text and 'writer.py:write' in text and 'reader.py:read' in text if case=='json' else
                     status==0 and 'status_model State.status' in text and 'status_visible' in text if case=='state' else
                     status==1 and text.startswith('field missing_field: no model, rule or code site'))
            imported=(root/'model_imported.marker').exists() or any(getattr(module,'__file__',None) and Path(module.__file__).resolve().is_relative_to(root) for module in tuple(sys.modules.values()))
            facts.append(Fact(case,correct and not imported,text))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'field': ('listed', 'unknown')}

from _read_fixture import complete_view_facts
_previous_conformance = conformance
def conformance():
    previous = _previous_conformance()
    return CodeFactsReport(tuple(previous.facts) + complete_view_facts('field'))
