"""Construct ordinary source/test fixtures, never a callable adapter or answer oracle."""
import ast
from pathlib import Path
import textwrap


def annotate(code, target, name, parameters, *, output='bool', calibrated_by=''):
    """Only add the source declaration/types; preserve the function's statements."""
    tree=ast.parse(textwrap.dedent(code))
    parts=target.split('.')
    body=tree.body
    for part in parts:
        node=next(n for n in body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==part)
        body=node.body
    for argument in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]:
        if argument.arg in parameters:
            argument.annotation=ast.parse(parameters[argument.arg],mode='eval').body
    node.returns=ast.parse(output,mode='eval').body
    # Change only the header and attach the observation comment. Keep every
    # original body statement and module initializer byte-for-byte.
    import io,tokenize
    code=textwrap.dedent(code)
    rows=code.splitlines(True);offsets=[0]
    for line in rows:offsets.append(offsets[-1]+len(line))
    signature=next(line.strip() for line in ast.unparse(node).splitlines()
                   if line.lstrip().startswith(('def ','async def ')))
    tokens=iter(tokenize.generate_tokens(io.StringIO(code).readline))
    for token in tokens:
        if token.start==(node.lineno,node.col_offset):break
    depth=0
    for token in tokens:
        if token.type==tokenize.OP:
            if token.string in ('(','[','{'):depth+=1
            elif token.string in (')',']','}'):depth-=1
            elif token.string==':'and depth==0:break
    start=offsets[node.lineno-1]+node.col_offset
    end=offsets[token.end[0]-1]+token.end[1]
    code=code[:start]+signature+code[end:]
    rendered=code.splitlines(True)
    line=min([node.lineno,*[d.lineno for d in node.decorator_list]])-1
    sensor='# flowguard: sensor '+name+'('+', '.join(p+': '+p for p in parameters)+') -> answer: '+output
    if calibrated_by:sensor+=' calibrated_by='+calibrated_by
    rendered.insert(line,' '*node.col_offset+sensor+'\n')
    return ''.join(rendered)


def native(root, module, target, name, parameters, *, call=None, body=None):
    """A genuine ordinary pytest test calls the production target using named inputs."""
    test='test_'+name.lower();file='tests/test_native_'+name.lower()+'.py'
    args=', '.join(p+': '+t for p,t in parameters.items())
    defaults={'int':'0','bool':'False','str':"''",'float':'0.0'}
    fixtures=''
    for p,t in parameters.items():
        fixtures+=f'@pytest.fixture\ndef {p}(): return {defaults[t]}\n'
    if call is None:call='app.'+target+'('+', '.join(parameters)+')'
    text=f'import pytest\nimport {module} as app\n'+fixtures+'# flowguard: event CASE_'+name+'('+args+')\n'+f'def {test}('+args+'):\n'
    if body is None:body='answer='+call+'\nassert type(answer) is bool'
    text+=textwrap.indent(textwrap.dedent(body).strip(),'    ')+'\n'
    (Path(root)/file).write_text(text)
    return file+'::'+test

# Direct Engine controls use the same scoped in-process backend as the pytest
# plugin, so Footprint and mutants observe the actual call rather than a child.
from contextlib import ExitStack
from contextvars import ContextVar
import sys
import pytest
_SCOPES=ContextVar('source_fixture_scopes')


def _containers(value):
    if isinstance(value,dict): return {key:_containers(item) for key,item in value.items()}
    if isinstance(value,list): return [_containers(item) for item in value]
    if isinstance(value,set): return set(value)
    return value


@pytest.fixture(autouse=True)
def source_sessions(request):
    import sys
    from flowguard.intent import config
    manager=request.config.pluginmanager
    fixture_manager=request.session._fixturemanager
    names=('_arg2fixturedefs','_arg2node2fixturedefs','_arg2nodeid2fixturedefs',
           '_node_autousenames','_nodeid_autousenames','_holderobjseen','_pending_conftests')
    fixture_state={name:_containers(getattr(fixture_manager,name)) for name in names if hasattr(fixture_manager,name)}
    conftests=set(manager._conftest_plugins)
    directories=dict(manager._dirpath2confmods)
    paths,owned=list(sys.path),set(config._INSERTED_PATHS)
    try:
        with ExitStack() as scopes:
            token=_SCOPES.set((scopes,request))
            try:yield
            finally:_SCOPES.reset(token)
    finally:
        for plugin in manager._conftest_plugins-conftests:
            manager.unregister(plugin)
        manager._conftest_plugins.intersection_update(conftests)
        manager._dirpath2confmods.clear();manager._dirpath2confmods.update(directories)
        for name,value in fixture_state.items():
            current=getattr(fixture_manager,name)
            current.clear();current.update(value)
        sys.path[:]=paths
        config._INSERTED_PATHS.clear();config._INSERTED_PATHS.update(owned)


def source_engine(model):
    """Native collection/import is verifier metadata, not ordinary coverage."""
    from flowguard.intent.runtime import _private_call
    return _private_call(_source_engine, model)


def _source_engine(model):
    from flowguard.intent.anchors import _execution_session
    from flowguard.intent.engine import Engine
    scopes,request=_SCOPES.get()
    from flowguard.intent import calibration
    from flowguard.intent.runtime import Runtime
    from flowguard.intent.config import setup_path
    from flowguard.intent.imports import prepare
    import inspect
    cfg=model.cfg
    setup_path(cfg);prepare(cfg.root)
    files=sorted({(home.testnode if hasattr(home,'scenario') else home.anchor.calibrated_by).partition('::')[0]
                  for rule in model.rules.values() for home in rule.homes
                  if hasattr(home,'scenario') or home.anchor and home.anchor.calibrated_by})
    items=[]
    manager=request.config.pluginmanager
    fixtures=request.session._fixturemanager
    for file in files:
        path=cfg.root/file
        manager._loadconftestmodules(path,importmode=request.config.getoption('importmode'),
            rootpath=request.config.rootpath,consider_namespace_packages=request.config.getini('consider_namespace_packages'))
        module=pytest.Module.from_parent(request.node,path=path,nodeid=path.as_posix())
        for conftest in manager._getconftestmodules(path):
            if 'holder' in inspect.signature(fixtures.parsefactories).parameters:
                fixtures.parsefactories(holder=conftest,node=module)
            else:
                from types import ModuleType
                holder=ModuleType(conftest.__name__+'_native_fixtures')
                vars(holder).update(vars(conftest))
                fixtures.parsefactories(holder,module.nodeid)
        # New FixtureDefs retain the real functions, scopes and parameters. A
        # child must not borrow its active outer test's single-slot cache.
        clones={}
        def descendants(nodes):
            for node in nodes:
                if isinstance(node,pytest.Item): yield node
                else: yield from descendants(node.collect())
        # This is a different source project's subtree. Its own parameter
        # marks stay intact; the outer harness's already collected control
        # parameters must not be generated again on this native function.
        marks=[(node.own_markers,list(node.own_markers)) for node in request.node.listchain()]
        try:
            for current,original in marks:
                current[:]=[mark for mark in original if mark.name!='parametrize']
            native=list(descendants(module.collect()))
        finally:
            for current,original in marks:current[:]=original
        for item in native:
            for name,definitions in list(item._fixtureinfo.name2fixturedefs.items()):
                rebound=[]
                for definition in definitions:
                    if definition.scope!='function':
                        rebound.append(definition);continue
                    if definition not in clones:
                        options=dict(name=name,func=definition.func,scope=definition.scope,
                                     params=definition.params,ids=definition.ids,autouse=False)
                        if 'node' in inspect.signature(fixtures._register_fixture).parameters:
                            options['node']=module
                        else:options['nodeid']=module.nodeid
                        fixtures._register_fixture(**options)
                        clones[definition]=fixtures.getfixturedefs(name,item)[-1]
                    rebound.append(clones[definition])
                item._fixtureinfo.name2fixturedefs[name]=tuple(rebound)
        items.extend(native)
    runtime=Runtime(cfg.root)
    # Run the actual conftest/session collection hooks once. Their errors and
    # deselection remain real; only FlowGuard's unrelated outer-model observer
    # recognizes its own private runtime context.
    from flowguard.intent.runtime import _PRIVATE
    if items:
        with calibration.session(runtime,items,nextitem=request.node):
            token=_PRIVATE.set(True)
            try:
                request.config.hook.pytest_collection_modifyitems(
                    session=request.session,config=request.config,items=items)
            finally:_PRIVATE.reset(token)
    events=[]
    scopes.enter_context(calibration.session(runtime,items,nextitem=request.node,events=events))
    scopes.enter_context(_execution_session(cfg.root))
    ordinary_run(model,runtime,items,events,request.node)
    from flowguard.intent.calibration import _prepare, _prepare_scenario
    for rule in model.rules.values():
        for binding in rule.homes:
            if hasattr(binding,'scenario'):
                _prepare_scenario(model.cfg.root,binding)
            elif binding.anchor and binding.anchor.calibrated_by:
                _prepare(model.cfg.root,binding.anchor)
    model.deep=True
    return Engine(model)


def ordinary_run(model,runtime,items,events,nextitem):
    """The native tests' one ordinary run, recorded as the pytest plugin records it: each calibrated anchor's
    real calls (`Runtime.hook`) and each test's anchor events (`Capture`). Calibration reads only these; no
    test runs again (design 4.5, 8). The outer FlowGuard session does not observe this private run."""
    from _pytest.runner import runtestprotocol
    from flowguard.intent import sites
    from flowguard.intent.flow import Capture
    from flowguard.intent.runtime import _PRIVATE
    calibrated={home.anchor.target:home.anchor for rule in model.rules.values() for home in rule.homes
                if not hasattr(home,'scenario') and home.anchor and home.anchor.calibrated_by}
    index=model.anchor_index
    if not items:
        return
    def loaded(target):
        """The loaded function of a target, or None when its module or member is not loaded."""
        module,_,qual=target.partition(':')
        value=sys.modules.get(module)
        for part in qual.split('.'):
            value=vars(value).get(part) if value is not None and hasattr(value,'__dict__') else None
        value=value.__func__ if isinstance(value,(staticmethod,classmethod)) else value
        return sites.unwrap(value) if callable(value) and hasattr(sites.unwrap(value),'__code__') else None
    codes=[(loaded(anchor.target).__code__,anchor.target) for anchor in index.entries
           if anchor.kind in ('sensor','event') and loaded(anchor.target) is not None]
    with ExitStack() as hooks:
        for anchor in calibrated.values():
            if loaded(anchor.target) is not None:
                hooks.enter_context(runtime.hook(loaded(anchor.target),name=anchor.name,private=True,
                                                 fields=anchor.fields,line=anchor.line))
        for item in items:
            runtime.test=item.nodeid
            function=sites.unwrap(item.obj)
            own=[(function.__code__,anchor.target) for anchor in index.entries if anchor.kind=='event'
                 and Path(function.__code__.co_filename).resolve()==(Path(model.cfg.root)/anchor.file).resolve()
                 and function.__qualname__==anchor.qual]
            capture=Capture(model.cfg.root,index,item.nodeid)
            class Outcomes:
                """What the pytest plugin records of each phase that did not pass, with its exception."""
                @pytest.hookimpl(hookwrapper=True)
                def pytest_runtest_makereport(self,item,call):
                    report=(yield).get_result()
                    if not report.passed:
                        runtime.outcome(item.nodeid,report.when,report.outcome,call.excinfo)
            recorder=Outcomes()
            item.config.pluginmanager.register(recorder)
            token=_PRIVATE.set(True)
            try:
                with runtime.record([*codes,*own],callback=capture.on_trace,private=True):
                    item.session._setupstate.teardown_exact(item)
                    runtestprotocol(item,log=False,nextitem=nextitem)
            finally:
                _PRIVATE.reset(token)
                item.config.pluginmanager.unregister(recorder)
                capture.close()
            events.extend(capture.events)
    runtime._test=''          # the ordinary run is over: later calls belong to no test


def scenario(root,module,code,intent,*,rule,target,parameters,source_parameters,
             body,read="Read('answer')",output='bool',defaults=None,imports=''):
    """Write an ordinary native test and the public Flow that reads its real call.

    The caller supplies the actual source parameters and logical input relation;
    no old Home declaration, expected answer or callable is accepted.
    """
    defaults=defaults or {}
    values={'int':'0','bool':'False','str':"''",'float':'0.0','tuple':'()'}
    file='tests/test_native_'+rule.lower()+'.py';test='test_'+rule.lower()
    text='import pytest\nimport '+module+' as app\n'+imports
    for name,kind in parameters.items():
        text+='@pytest.fixture\ndef '+name+'(): return '+defaults.get(name,values.get(kind,'None'))+'\n'
    signature=', '.join(name+': '+kind for name,kind in parameters.items())
    text+='# flowguard: event CASE_'+rule+'('+signature+')\n'
    text+='def '+test+'('+signature+'):\n'+textwrap.indent(textwrap.dedent(body).strip(),'    ')+'\n'
    (Path(root)/file).write_text(text)
    code=annotate(code,target,'ACTUAL_'+rule,source_parameters,output=output,calibrated_by=file+'::'+test)
    mapping='{'+', '.join(repr(name)+":Read('case','arg."+name+"')"for name in parameters)+'}'
    intent+='\nfrom flowguard.intent import flow,Node,Read,Relation\n'
    intent+="flow('OBSERVE_"+rule+"',source='assumed: actual native source observation',nodes=[Node('case','CASE_"+rule+"',start=True),Node('answer','ACTUAL_"+rule+"',phase='return',caller='case',end=True),Node('error','ACTUAL_"+rule+"',phase='raise',caller='case',end=True)],edges=[('case','answer'),('case','error')],relations=[Relation('"+rule+"',"+mapping+","+read+",on='answer'),Relation('"+rule+"',"+mapping+",Read('error','error'),on='error')])\n"
    return code,intent
