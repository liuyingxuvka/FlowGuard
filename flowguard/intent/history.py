"""Literal regression preservation and the same engine applied to an archived previous commit."""
from __future__ import annotations

import ast
import io
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from flowguard.map.common import MapError, content_digest, git_blob, git_run
from .cache import scan


def _revision(cfg, value=None):
    if value:
        git_run(cfg.root, 'rev-parse', '--verify', value + '^{commit}')
        return value
    if git_run(cfg.root, 'rev-parse', '--verify', 'HEAD', allowed=(0, 128)).returncode:
        return None
    upstream = git_run(cfg.root, 'rev-parse', '--verify', 'origin/main', allowed=(0, 128))
    if upstream.returncode == 0:
        base = git_run(cfg.root, 'merge-base', 'HEAD', 'origin/main').stdout.decode().strip()
        if base != git_run(cfg.root, 'rev-parse', 'HEAD').stdout.decode().strip():
            return base
    dirty = git_run(cfg.root, 'diff', '--quiet', 'HEAD', allowed=(0, 1)).returncode
    untracked = git_run(cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout.split(b'\0')
    if dirty or any(path.endswith(b'.py') for path in untracked):
        return 'HEAD'
    parent = git_run(cfg.root, 'rev-parse', '--verify', 'HEAD^', allowed=(0, 128))
    if parent.returncode == 0:
        return parent.stdout.decode().strip()
    shallow = git_run(cfg.root, 'rev-parse', '--is-shallow-repository').stdout.strip()
    return None if shallow == b'true' else 'HEAD'


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
    revision = _revision(cfg, base)
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
            from .calibration import _binding_data
            facts = _binding_data(binding)
            facts.pop('entries', None)  # Unrelated source anchors do not reinterpret this row.
            return facts
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
    """Keep valid old-code evidence in the existing result payload, never infer agreement from coverage.

    Observed-case confirmation is deliberately absent: this round removed boundary
    value recording. A marked or entered test is not proof that its answer agrees.
    """
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
                reason='a retained row failed in the previous real code and passes now' if proofs else '')


_PROBE = '''
import json,sys
from pathlib import Path
source, root, rid, line, targets = sys.argv[1:]
targets=json.loads(targets)
sys.path.insert(0,source)
from flowguard.intent.loader import load
from flowguard.intent.engine import Engine,WitnessUnavailable
from flowguard.intent import sites
from flowguard.intent.anchors import _execution_session
from flowguard.intent.calibration import _prepare,_prepare_scenario
from contextlib import ExitStack
scopes=ExitStack();scopes.enter_context(_execution_session(root))
model=load(root=root)
rule=model.rules.get(rid)
if model.errors or rule is None:
 print(json.dumps({'status':'unknown','reason':str(model.errors)})); raise SystemExit()
engine=Engine(model)
row=next((r for r in rule.live_rows if r.line==int(line)),None)
if row is None:
 print(json.dumps({'status':'unknown','reason':'new row could not be loaded'})); raise SystemExit()
answers=[]
from flowguard.intent.cells import same,Raised
from flowguard.intent.tracer import Footprint
from flowguard.intent.readings import project_module
if not rule.homes:
 print(json.dumps({'status':'unknown','reason':'no real homes bound'})); raise SystemExit()
for home in rule.homes:
 if home.anchor is None:
  # A missing historical observation comment is not evidence that the
  # production function did not exist. Inspect the existing Map, never call
  # an unbound old function through an anonymous fallback.
  from contextlib import closing
  from flowguard.structure import build
  candidates=targets.get(home.name,[])
  with closing(build(model.cfg.root,roots=model.cfg.roots)) as graph:
   present=any(graph.node(graph.canonical(target) or target) for target in candidates)
  answers.append({'status':'unknown' if present or not candidates else 'new code',
                  'home':home.name,'reason':'old source has no corresponding observation anchor' if present or not candidates else 'old production function is absent'})
  continue
 if hasattr(home,'scenario'):
  _prepare_scenario(model.cfg.root,home)
 elif home.anchor and home.anchor.calibrated_by:
  _prepare(model.cfg.root,home.anchor)
 fn,_,gone=engine.home_sites(home.target)
 if gone:
  module=home.target.partition(':')[0].replace('.', '/')
  exists=any((base/(module+'.py')).is_file() or (base/module/'__init__.py').is_file() for base in [model.cfg.root,*model.cfg.roots])
  failed_import=any(kind in gone for kind in ('ImportError','ModuleNotFoundError'))
  answers.append({'status':'unknown' if exists and failed_import else 'new code','home':home.target,'reason':gone}); continue
 with Footprint(engine.is_project) as footprint:
  got=engine.call(home,row.inputs,fn)
 if isinstance(got,Raised) and isinstance(got.error,WitnessUnavailable):
  answers.append({'status':'unknown','home':home.target,'reason':'source observation unavailable: '+str(got.error)}); continue
 code=getattr(sites.unwrap(fn),'__code__',None)
 if code is None or sites.code_key(code) not in footprint.keys():
  answers.append({'status':'unknown','reason':'binding never enters old home'}); continue
 if isinstance(got,Raised) and not same(row.expect,got):
  error=got.error
  if isinstance(error,ImportError) and not project_module(getattr(error,'name',''),model.cfg):
   answers.append({'status':'unknown','reason':repr(got)}); continue
  if isinstance(error,OSError) and (not getattr(error,'filename',None) or not Path(error.filename).resolve().is_relative_to(model.cfg.root)):
   answers.append({'status':'unknown','reason':repr(got)}); continue
 answers.append({'status':'regression' if same(row.expect,got) else 'proven','home':home.target,'actual':repr(got)})
print(json.dumps({'status':'unknown' if any(a['status']=='unknown' for a in answers) else 'proven' if any(a['status']=='proven' for a in answers) else 'new code' if all(a['status']=='new code' for a in answers) else 'regression','homes':answers}))
'''


def _probe(root, rule, row):
    result = subprocess.run([sys.executable, '-c', _PROBE, str(Path(__file__).resolve().parents[2]),
                             str(root), rule.id, str(row.line), json.dumps({name: [home.target for home in rule.homes if home.name == name and home.anchor is not None] for name in {home.name for home in rule.homes}})], cwd=root, capture_output=True, text=True)
    if result.returncode:
        return dict(status='unknown', reason=result.stderr.strip() or f'exit {result.returncode}')
    try:
        return json.loads(result.stdout.splitlines()[-1])
    except (ValueError, IndexError):
        return dict(status='unknown', reason='old-code probe did not produce a result')


def proven(cfg, rule, row, base='HEAD^'):
    """A new row tested against real old code, without inventing a second test executor."""
    try:
        revision = _revision(cfg, base)
    except MapError as error:
        return dict(status='unknown', reason=str(error))
    if revision is None:
        return dict(status='unknown', reason='no previous commit')
    current = _probe(cfg.root, rule, row)
    if current['status'] != 'regression':
        return dict(status='unknown', reason='current row does not pass at every home', current=current)
    archive = git_run(cfg.root, 'archive', revision).stdout
    with tempfile.TemporaryDirectory(prefix='flowguard-previous-') as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        # Only the new regression declaration is carried back. Old production
        # code and old test helpers stay old; incompatible helpers are unknown.
        path = Path(rule.file)
        target = root / path.relative_to(cfg.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        result = _probe(root, rule, row)
        result.update(base=git_run(cfg.root, 'rev-parse', revision + '^{commit}').stdout.decode().strip(),
                      signature=current_row_signature(rule, row))
        return result
