"""Draft is static vocabulary and exclusive TODO creation, never an oracle."""
import ast
from pathlib import Path
import runpy

import pytest

from flowguard.flow.draft import DraftError, draft, write_once


SOURCE = '''from config import Settings
raise AssertionError("selected module must not execute")
class Refused(Exception): pass
class Worker:
    cache: dict
    def __init__(self, settings: Settings):
        self.ready=False
        self.status="INITIAL_EFFECT_NOT_A_MODEL_DOMAIN"
        self.settings=settings
    def finish(self, value, /, *extra, strict=expensive_default(), **options):
        if self.status in {"open","closed"} and self.ready:
            if production_guard(value): raise Refused("RAISE_MESSAGE_IS_NOT_AN_ORACLE")
        self.status="EFFECT_MUST_NOT_BE_COPIED"
        def nested(): raise InnerError("nested")
        return opaque_effect(value)
    @property
    def display(self): return self.status
    @staticmethod
    def compare(left, right): return left==right
    @classmethod
    def create(cls, value): return cls(value)
    async def wait(self): return None
'''


def test_vocabulary_reads_source_without_executing_or_copying_behavior(project):
    project.file('worker.py',SOURCE)
    project.file('config.py','raise AssertionError("settings must not import")\nclass Settings: pass\n')
    result=draft(project.root,'worker.py:Worker')
    vocabulary=result.vocabulary
    operations={row['name']:row for row in vocabulary['operations']}
    assert set(operations)=={'finish','compare','create','wait'}
    assert operations['finish']['raises']==['Refused']
    assert [p['kind'] for p in operations['finish']['parameters']]==[
        'positional_only','var_positional','keyword_only','var_keyword']
    assert operations['finish']['parameters'][2]['has_default'] is True
    assert operations['compare']['kind']=='static' and operations['create']['kind']=='class'
    assert operations['wait']['async'] is True and vocabulary['unknown']
    assert [row['name'] for row in vocabulary['queries']]==['display']
    fields={row['name']:row for row in vocabulary['fields']}
    assert fields['status']['literals']==['open','closed']
    assert not fields['status']['truth_tested'] and fields['ready']['truth_tested']
    assert 'cache' in fields
    assert vocabulary['settings'][0]=={'name':'Settings','source':'config:Settings','line':1,'kind':'import'}
    settings=next(row for row in vocabulary['settings'] if row['kind']=='parameter')
    assert settings['name']=='settings' and settings['source'] is None and settings['annotation']=='Settings'
    rendered=repr(result.to_dict())
    for forbidden in ['production_guard','opaque_effect','expensive_default','EFFECT_MUST_NOT_BE_COPIED',
                      'INITIAL_EFFECT_NOT_A_MODEL_DOMAIN','RAISE_MESSAGE_IS_NOT_AN_ORACLE']:
        assert forbidden not in rendered
    assert 'TODO' in result.model and 'TODO' in result.adapter
    assert not any(isinstance(node,(ast.If,ast.Compare)) for node in ast.walk(ast.parse(result.model)))


def test_draft_is_read_only_and_only_its_explicit_creation_writes(project):
    path=project.file('app.py','class App:\n    def work(self): pass\n')
    before={p.relative_to(project.root):p.read_bytes() for p in project.root.rglob('*') if p.is_file()}
    result=draft(project.root,'./app.py:App.work')
    assert {p.relative_to(project.root):p.read_bytes() for p in project.root.rglob('*') if p.is_file()}==before
    model,adapter=write_once(result,project.root/'.flowguard/flow/app.py',project.root/'app_adapter.py')
    assert path.read_bytes()==before[Path('app.py')]
    with pytest.raises(NotImplementedError,match='independent model'):
        runpy.run_path(str(model))
    adapter.write_text(adapter.read_text()+'\n# author completion must survive\n')
    preserved=(model.read_bytes(),adapter.read_bytes())
    with pytest.raises(FileExistsError):
        write_once(draft(project.root,'app.py:App'),model,adapter)
    assert (model.read_bytes(),adapter.read_bytes())==preserved


def test_existing_adapter_prevents_creation_of_either_output(project):
    project.file('app.py','def work(): pass\n')
    adapter=project.file('adapter.py','# author-owned\n')
    model=project.root/'new_model.py'
    with pytest.raises(FileExistsError):
        write_once(draft(project.root,'app.py'),model,adapter)
    assert not model.exists() and adapter.read_text()=='# author-owned\n'


def test_selected_method_does_not_become_all_class_operations(project):
    project.file('app.py','''class App:
    def first(self): raise FirstReason()
    def second(self): raise SecondReason()
''')
    vocabulary=draft(project.root,'app.py:App.first').vocabulary
    assert [(row['name'],row['raises']) for row in vocabulary['operations']]==[('first',['FirstReason'])]


@pytest.mark.parametrize('target', ['app.py:App', 'app.py:App.work'])
def test_new_adapter_declares_known_source_base_chain_without_widening_members(project, target):
    project.file('app.py', '''raise AssertionError("draft must not execute source")
class Root:
    def inherited(self): raise BaseOnly()
class Base(Root): pass
class App(Base):
    def work(self): pass
''')
    result = draft(project.root, target)
    namespace = {}
    exec(result.adapter, namespace)
    assert namespace['SPEC'] == {'system': 'app:App',
                                'classes': ['app:App', 'app:Base', 'app:Root'], 'refusal': []}
    assert [row['name'] for row in result.vocabulary['operations']] == ['work']
    assert not result.vocabulary['fields']
    assert result.vocabulary['unknown'] == ['inherited members need author review: App']


@pytest.mark.parametrize('source', [
    'from external import Base\nclass App(Base): pass\n',
    'class App(Base): pass\nclass Base: pass\n',
    'class Base: pass\nBase = foreign\nclass App(Base): pass\n',
    'class Base: pass\nfrom external import Base\nclass App(Base): pass\n',
    'class Base: pass\nclass Base: pass\nclass App(Base): pass\n',
    'class Base: pass\nif condition:\n    class Base: pass\nclass App(Base): pass\n',
    '@replace\nclass Base: pass\nclass App(Base): pass\n',
    'class Base: pass\nclass App(external.Base): pass\n',
])
def test_adapter_keeps_unresolved_or_rebound_bases_for_author_review(project, source):
    project.file('app.py', source)
    namespace = {}
    exec(draft(project.root, 'app.py:App').adapter, namespace)
    assert namespace['SPEC']['classes'] == ['app:App']


def test_new_base_scope_still_never_updates_author_owned_adapter(project):
    project.file('app.py', 'class Base: pass\nclass App(Base): pass\n')
    model, adapter = write_once(draft(project.root, 'app.py:App'),
                               project.root / 'model.py', project.root / 'adapter.py')
    adapter.write_text(adapter.read_text() + '\n# independent author completion\n')
    project.file('app.py', 'class Root: pass\nclass Base(Root): pass\nclass App(Base): pass\n')
    preserved = (model.read_bytes(), adapter.read_bytes())
    with pytest.raises(FileExistsError):
        write_once(draft(project.root, 'app.py:App'), model, adapter)
    assert (model.read_bytes(), adapter.read_bytes()) == preserved


@pytest.mark.parametrize('target',['app.py:Missing','app.py:App.missing','outside.txt'])
def test_invalid_target_is_an_error_not_empty_candidates(project,target):
    project.file('app.py','class App: pass\n')
    project.file('outside.txt','plain text')
    with pytest.raises(DraftError): draft(project.root,target)


def test_invalid_python_is_not_a_successful_draft(project):
    project.file('bad.py','def broken(:\n')
    with pytest.raises(DraftError,match='bad.py:1'):
        draft(project.root,'bad.py')


def test_settings_parameter_uses_static_annotation_and_marks_unresolved_sources(project):
    project.file('app.py','''from preferences import Preferences
class App:
    def __init__(self, options: Preferences, config): pass
''')
    settings=draft(project.root,'app.py:App').vocabulary['settings']
    assert settings==[
        {'name':'Preferences','source':'preferences:Preferences','line':1,'kind':'import'},
        {'name':'options','source':None,'line':3,'kind':'parameter','annotation':'Preferences'},
        {'name':'config','source':None,'line':3,'kind':'parameter','annotation':''},
    ]


def test_rebound_settings_source_does_not_choose_a_caller_claim(project):
    project.file('app.py','''from first import Settings
from second import Settings
class App:
    def __init__(self, settings: Settings): pass
''')
    settings=draft(project.root,'app.py:App').vocabulary['settings']
    parameter=next(row for row in settings if row['kind']=='parameter')
    assert parameter['source'] is None


def test_settings_sources_preserve_dotted_import_and_class_shadow_as_candidates(project):
    project.file('app.py','''import pkg.config
from first import Settings
class App:
    Settings=Other
    def __init__(self, settings: pkg.config.Settings, options: Settings): pass
''')
    settings=draft(project.root,'app.py:App').vocabulary['settings']
    assert any(row['source']=='pkg.config' and row['kind']=='import' for row in settings)
    assert any(row['source']=='app.py:App.Settings' for row in settings)
    assert all(row['source'] is None for row in settings if row['kind']=='parameter')
    assert all(row['source']!='pkg.config:config.Settings' for row in settings)
