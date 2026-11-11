"""Preserve literal regressions and compare previous functions in verified current inputs."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from flowguard.map.common import MapError, content_digest, git_blob, git_run, normalize_newlines
from .cache import scan


def _texts(cfg, revision, folder):
    paths = git_run(cfg.root, 'ls-tree', '-r', '--name-only', '-z', revision, '--', folder).stdout.split(b'\0')
    return {path.decode(): git_run(cfg.root, 'show', revision + ':' + path.decode()).stdout.decode('utf-8-sig')
            for path in paths if path and path.endswith(b'.py')}


def _guards(texts):
    guards = {}
    for file, text in texts.items():
        tree = ast.parse(text, file)
        pytest_names = {alias.asname or alias.name for statement in tree.body if isinstance(statement, ast.Import)
                        for alias in statement.names if alias.name == 'pytest'}
        mark_names = {alias.asname or alias.name for statement in tree.body if isinstance(statement, ast.ImportFrom)
                      and statement.module == 'pytest' for alias in statement.names if alias.name == 'mark'}
        skip_names = {alias.asname or alias.name for statement in tree.body if isinstance(statement, ast.ImportFrom)
                      and statement.module == 'pytest' for alias in statement.names if alias.name == 'skip'}
        markers = {name + '.mark' for name in pytest_names} | mark_names
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            marked = []
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == 'rule' and ast.unparse(decorator.func.value) in markers and decorator.args):
                    marked.append(ast.dump(decorator.args[0], include_attributes=False))
            if marked:
                # Conditional calls and importorskip need their real pytest outcome.
                calls = [statement.value for statement in node.body if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)]
                skipped = any(isinstance(call.func, ast.Name) and call.func.id in skip_names
                              or isinstance(call.func, ast.Attribute) and call.func.attr == 'skip'
                              and ast.unparse(call.func.value) in pytest_names for call in calls)
                for decorator in node.decorator_list:
                    call = decorator if isinstance(decorator, ast.Call) else None
                    target = call.func if call else decorator
                    if not isinstance(target, ast.Attribute) or ast.unparse(target.value) not in markers:
                        continue
                    if target.attr == 'skip':
                        skipped = True
                    elif target.attr == 'skipif' and call:
                        condition = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == 'condition'), None)
                        if isinstance(condition, ast.Constant) and condition.value is True:
                            skipped = True
                guards[(file, node.name)] = (tuple(marked), skipped)
    return guards


def check(cfg, base=None):
    """Compare Git's baseline, never a cache that might already have forgotten a deleted rule."""
    from .owners import baseline
    revision = baseline(cfg, base)
    if base is not None:
        git_run(cfg.root, 'rev-parse', '--verify', base + '^{commit}')
    if revision is None:
        shallow = git_run(cfg.root, 'rev-parse', '--is-shallow-repository', allowed=(0, 128))
        return ['anchor gone (no history: use fetch-depth 0)'] if shallow.stdout.strip() == b'true' else []
    previous = scan(cfg, _texts(cfg, revision, cfg.rel(cfg.intent)))
    current = scan(cfg)
    red = []
    superseded = {old for rule in current['rules'].values() for old in rule.get('supersedes', [])}
    for rid, old in previous['rules'].items():
        new = current['rules'].get(rid)
        if new is None:
            if rid not in superseded:
                red.append(f'rule removed without supersedes= or retired=: {rid} ({old["file"]})')
            continue
        cases = [row['fields'] for row in new['row_records']]
        for row in old['row_records']:
            if row['retired'] or row['fields'] in cases:
                continue
            red.append(f'row removed or narrowed without retired=: {rid} {old["file"]}:{row["line"]} -> retain the case or retire it with a reason')
    before_guards = _guards(_texts(cfg, revision, 'tests'))
    after_guards = _guards({cfg.rel(p): p.read_text(encoding='utf-8-sig') for p in (cfg.root / 'tests').rglob('*.py')}) if (cfg.root / 'tests').is_dir() else {}
    for (file, name), marker in before_guards.items():
        if (file, name) not in after_guards or after_guards[(file, name)][1] or after_guards[(file, name)][0] != marker[0]:
            red.append(f'guard lost: {file}::{name} -> restore the real marked test without skipping it')
    return red


def self_confirmed(cfg, rule, engine):
    """Derive green* from the row's semantic introduction, without a second ledger.

    Uncommitted changes compare with HEAD; committed rows compare homes in their
    own introduction commit. Later edits cannot combine two different moments.
    The per-engine memo avoids repeating Git/AST work for rows in the same file.
    """
    head = git_run(cfg.root, 'rev-parse', '--verify', 'HEAD', allowed=(0, 128))
    if head.returncode:
        return dict(pending=bool(rule.live_rows and rule.homes), reason='new row/home pair has no previous commit',
                    changed_rows=[row.line for row in rule.live_rows], changed_homes=[home.target for home in rule.homes])
    memo = getattr(engine, '_history_facts', None)
    if memo is None:
        memo = engine._history_facts = {}
    current = scan(cfg)['rules'].get(rule.id, {})
    relative = current.get('file', cfg.rel(rule.file))
    def facts(revision):
        key = ('rows', revision, relative)
        if key not in memo:
            raw = git_blob(cfg.root, revision, relative)
            memo[key] = scan(cfg, {relative: raw.decode('utf-8-sig')})['rules'] if raw is not None else {}
        return memo[key].get(rule.id, {}).get('row_records', [])
    if ('commits', relative) not in memo:
        memo[('commits', relative)] = git_run(cfg.root, 'log', '--format=%H', '--', relative).stdout.decode().splitlines()
    def identity(row):
        return (tuple(sorted(row['fields'].items())), row.get('expect'))
    def origin(row):
        introduced = 'WORKTREE'
        for revision in memo[('commits', relative)]:
            if identity(row) not in {identity(old) for old in facts(revision) if not old['retired']}:
                break
            introduced = revision
        return introduced
    from flowguard.structure.extract import extract
    from .sites import unwrap
    def home_fp(revision, relative, qual, module):
        key = ('home', revision, relative, qual)
        if key not in memo:
            raw = (cfg.root / relative).read_bytes() if revision == 'WORKTREE' else git_blob(cfg.root, revision, relative)
            memo[key] = next((node['fp'] for node in extract(cfg.root, relative, raw, module, False)['nodes'] if node['qual'] == qual), None) if raw is not None else None
        return memo[key]
    changed_rows, changed_homes = [], set()
    for row in current.get('row_records', []):
        if row['retired']:
            continue
        revision = origin(row)
        before = 'HEAD' if revision == 'WORKTREE' else revision + '^'
        parent = git_run(cfg.root, 'rev-parse', '--verify', before, allowed=(0, 128))
        for home in rule.homes:
            fn = engine.home_sites(home.target)[0]
            code = getattr(unwrap(fn), '__code__', None) if fn is not None else None
            if code is None or not Path(code.co_filename).resolve().is_relative_to(cfg.root):
                continue
            source, qual = cfg.rel(code.co_filename), code.co_qualname.replace('.<locals>.', '.')
            old = home_fp(before, source, qual, home.target.partition(':')[0]) if parent.returncode == 0 else None
            if home_fp(revision, source, qual, home.target.partition(':')[0]) != old:
                changed_rows.append(row['line'])
                changed_homes.add(home.target)
    pending = bool(changed_rows and changed_homes)
    return dict(pending=pending, reason='rows and homes changed together' if pending else '',
                changed_rows=sorted(set(changed_rows)), changed_homes=sorted(changed_homes))


def current_row_signature(rule, row):
    """Identify a literal case and its present interpretation, without line-number churn."""
    def function_body(function):
        import textwrap
        from flowguard.structure.extract import fingerprint
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        definition = tree.body[0]
        definition.decorator_list = []
        return fingerprint(definition, definition.name)
    def binding_facts(binding):
        from dataclasses import asdict
        if hasattr(binding, 'scenario'):
            from dataclasses import fields, is_dataclass
            from .flow import _UNSET
            def semantic(value):
                if value is _UNSET:return {'unset':True}
                if is_dataclass(value):return {field.name:semantic(getattr(value,field.name)) for field in fields(value)}
                if hasattr(value,'id'):return {'id':value.id}
                if isinstance(value,dict):return {key:semantic(item) for key,item in value.items()}
                if isinstance(value,(list,tuple)):return [semantic(item) for item in value]
                return repr(value)
            return dict(flow=semantic(binding.flow),scenario=asdict(binding.scenario),anchor=asdict(binding.anchor),
                        field_map=binding.field_map,testnode=binding.testnode,actual_targets=binding.actual_targets,targets=binding.targets,
                        relation_indices=binding.relation_indices,argument_plan=semantic(binding.argument_plan))
        return dict(target=binding.target, name=binding.name,
                    anchor=asdict(binding.anchor) if binding.anchor else None,
                    equivalent=binding.equivalent)
    facts = dict(rule=rule.id, decides=rule.decides, source=rule.source,
                 quote=getattr(rule, 'quote', None), fields={name: repr(kind) for name, kind in rule.fields.items()},
                 inputs={name: (type(value).__module__, type(value).__qualname__, repr(value)) for name, value in row.inputs.items()},
                 expect=repr(row.expect), predicate=function_body(rule.pred),
                 homes=[binding_facts(home) for home in rule.homes])
    return content_digest(Path('row-proof'), data=json.dumps(facts, sort_keys=True).encode())


def confirmation(cfg, rule, engine=None):
    """Reuse bound previous-function evidence; merely entering a test never clears pending."""
    from .cache import read
    memo = getattr(engine, '_proven_results', None) if engine is not None else None
    if memo is None:
        memo = read(cfg)['results']
        if engine is not None:
            engine._proven_results = memo
    retained = [proof for result in memo.get(rule.id, {}).get('items', {}).values()
                for proof in result.get('proven_rows', []) if proof.get('status') == 'proven']
    if not retained:
        return dict(cleared=False, proven_rows=[], reason='')
    signatures = {current_row_signature(rule, row) for row in rule.live_rows}
    proofs = {}
    for proof in retained:
        if proof.get('signature') in signatures:
            proofs[proof['signature']] = proof
    return dict(cleared=bool(proofs), proven_rows=list(proofs.values()),
                reason='a retained row failed in previous functions/constants with the same verified inputs and passes now' if proofs else '')


def _historical_home(runtime, home, values):
    """An absent function is new code; an absent comment or environment is not."""
    from . import anchors, sites
    from .runtime import _functions
    anchor=home.anchor
    source=runtime._source(anchor.file)
    if source is None:return dict(status='unknown',reason='old module location cannot be restored')
    tree=ast.parse(source)
    definition=dict(_functions(tree)).get(anchor.qual)
    if definition is None:
        constants=runtime._constants(tree,anchor.module)
        inert=all(isinstance(node,(ast.Assign,ast.AnnAssign)) and all(isinstance(t,ast.Name) and t.id in constants for t in (node.targets if isinstance(node,ast.Assign) else [node.target])) for node in tree.body)
        return dict(status='new code' if inert else 'unknown',reason='old production function is absent' if inert else 'old dynamic function binding cannot be restored')
    facts=anchors.source_facts(tree,source,anchor.module,anchor.file)
    previous=next((old for old in facts.get('anchors',()) if old['name']==anchor.name and old['qual']==anchor.qual),None)
    if previous is None:return dict(status='unknown',reason='old source has no corresponding observation anchor')
    previous=anchors._anchor(previous)
    if previous.parameters!=anchor.parameters or any(getattr(previous,name)!=getattr(anchor,name) for name in
            ('kind','output','output_type','projection','fields','values','calibrated_by')):
        return dict(status='unknown',reason='old observation meaning cannot be restored')
    function=sites.unwrap(sites.resolve_loaded(anchor.target))
    if runtime.register(function) is None:return dict(status='unknown',reason=runtime.unavailable.get(function,'old function unavailable'))
    # Qualification and later evaluation both use the historical source in fresh sealed globals.
    # Live module bindings are deliberately irrelevant; no old code is installed into them.
    signature = inspect.signature(function, follow_wrapped=False)
    supplied = {parameter.source: values[parameter.name] for parameter in anchor.parameters if parameter.name in values}
    positional = [supplied[parameter.name] for parameter in signature.parameters.values()
                  if parameter.kind is inspect.Parameter.POSITIONAL_ONLY and parameter.name in supplied]
    keywords = {name: value for name, value in supplied.items()
                if name in signature.parameters and signature.parameters[name].kind is not inspect.Parameter.POSITIONAL_ONLY}
    arguments = signature.bind(*positional, **keywords)
    arguments.apply_defaults()
    problem = runtime.safety(function, arguments.arguments, historical=True)
    if problem:
        return dict(status='unknown', reason=problem)
    if hasattr(home,'scenario'):
        from .calibration import _context
        _,item=_context(runtime.root,home.testnode)
        files={home.testnode.partition('::')[0]}|{Path(definition.func.__code__.co_filename).resolve().relative_to(runtime.root).as_posix() for definitions in item._fixtureinfo.name2fixturedefs.values() for definition in definitions if hasattr(definition.func,'__code__') and Path(definition.func.__code__.co_filename).resolve().is_relative_to(runtime.root)}
        if any(normalize_newlines((runtime._source(file) or '').encode())!=normalize_newlines((runtime.root/file).read_text(encoding='utf-8-sig').encode()) for file in files):
            return dict(status='unknown',reason='old test context cannot be restored')
        return dict(status='unknown',reason='not compared: old scenario event/path replay is unavailable; a leaf does not establish the previous path')
    return None


def _probe(root, rule, row, *, runtime=None):
    from .loader import load
    from .engine import Engine,WitnessUnavailable
    from .calibration import _prepare,_prepare_scenario
    from .cells import same,Raised
    from contextlib import nullcontext
    model=load(root=root)
    if model.errors or rule.id not in model.rules:return dict(status='unknown',reason=str(model.errors))
    engine=Engine(model)
    current=model.rules[rule.id]
    literal=next((item for item in current.live_rows if item.line==row.line),None)
    if literal is None or current_row_signature(current,literal)!=current_row_signature(rule,row):
        return dict(status='unknown',reason='row is not the current literal regression')
    if not current.homes:return dict(status='unknown',reason='no real homes bound')
    answers=[]
    for home in current.homes:
        answer=dict(home=home.target)
        if home.anchor is None:
            answer.update(status='unknown',reason='source observation unavailable: no real anchor')
        else:
            if hasattr(home,'scenario'):_prepare_scenario(model.cfg.root,home)
            elif home.anchor.calibrated_by:_prepare(model.cfg.root,home.anchor)
            try:
                boundary=_historical_home(runtime,home,row.inputs) if runtime is not None else None
                if boundary:answer.update(boundary)
                else:
                    with runtime.old_code() if runtime is not None else nullcontext():
                        got=engine.call(home,row.inputs,None)
                    if isinstance(got,Raised) and (isinstance(got.error,WitnessUnavailable) or not same(row.expect,got) and isinstance(got.error,(ImportError,OSError))):
                        answer.update(status='unknown',reason='source observation unavailable: '+str(got.error))
                    else:answer.update(status='regression' if same(row.expect,got) else 'proven',actual=repr(got))
            except Exception as error:answer.update(status='unknown',reason=type(error).__name__+': '+str(error))
        answers.append(answer)
    statuses={answer['status'] for answer in answers}
    return dict(status='unknown' if 'unknown' in statuses else 'proven' if 'proven' in statuses
                else 'new code' if statuses=={'new code'} else 'regression',homes=answers)


def proven(cfg, rule, row, base=None):
    """Compare old functions/constants in the same verified inputs, not an old project run."""
    from .runtime import Runtime
    from .owners import baseline
    try:
        revision = baseline(cfg, base)
        if base is not None:
            git_run(cfg.root, 'rev-parse', '--verify', base + '^{commit}')
    except MapError as error:return dict(status='unknown',reason=str(error))
    if revision is None:return dict(status='unknown',reason='no previous commit')
    current=_probe(cfg.root,rule,row)
    if current['status']!='regression':
        return dict(status='unknown',reason='current row does not pass at every home',current=current)
    result=_probe(cfg.root,rule,row,runtime=Runtime(cfg.root,revision))
    result.update(base=git_run(cfg.root,'rev-parse',revision+'^{commit}').stdout.decode().strip(),
                  signature=current_row_signature(rule,row),
                  scope='previous functions and constants in the same verified inputs/test context; not the whole previous project')
    return result
