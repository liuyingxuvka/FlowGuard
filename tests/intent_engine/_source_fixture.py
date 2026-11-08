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
import pytest
_SCOPES=ContextVar('source_fixture_scopes')


@pytest.fixture(autouse=True)
def source_sessions():
    with ExitStack() as scopes:
        token=_SCOPES.set(scopes)
        try:yield
        finally:_SCOPES.reset(token)


def source_engine(model):
    from flowguard.intent.anchors import _execution_session
    from flowguard.intent.engine import Engine
    _SCOPES.get().enter_context(_execution_session(model.cfg.root))
    from flowguard.intent.calibration import _prepare, _prepare_scenario
    for rule in model.rules.values():
        for binding in rule.homes:
            if hasattr(binding,'scenario'):
                _prepare_scenario(model.cfg.root,binding)
            elif binding.anchor and binding.anchor.calibrated_by:
                _prepare(model.cfg.root,binding.anchor)
    model.deep = True  # These Engine controls explicitly exercise decision probes and mutation survival.
    return Engine(model)


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
