"""Compute the legacy static recovery view; never explore or store a verdict."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess

from .common import advice, matches_any, read_source, render_advice
from .inventory import list_files
from .mapfile import ignore_patterns, load_map
from .plan import PLAN_RELPATH, function_identities, static_plan_rows
from .records import CHANGE_DIR, change_records, since_release
from .requests import other_worktrees, request_details
from .targetfile import build_target_view, load_target


def _age(moment):
    if not moment:
        return 'unknown'
    seconds = max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(moment)).total_seconds()))
    return f'{seconds // 86400} days' if seconds >= 86400 else f'{seconds // 60} min'


def _read_git(root, reader, *args):
    try:
        return reader(root, *args)
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_header(root, reader, peers):
    head = _read_git(root, reader, 'rev-parse', '--verify', 'HEAD')
    branch = _read_git(root, reader, 'symbolic-ref', '--short', '-q', 'HEAD')
    pending = _read_git(root, reader, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--', '.')
    prefix = _read_git(root, reader, 'rev-parse', '--show-prefix')
    prefix = prefix[0].rstrip('\r\n') if prefix else ''
    paths = []
    iterator = iter(pending or ())
    for row in iterator:
        paths.append(row[3:])
        if 'R' in row[:2] or 'C' in row[:2]:
            paths.append(next(iterator))
    worktrees = sorted([str(root), *(str(peer) for peer in peers)])
    paths = [path[len(prefix):] if path.startswith(prefix) else path for path in paths]
    return dict(head=head[0].strip() if head else None, branch=branch[0].strip() if branch else None,
                uncommitted_paths=sorted(set(paths)) if pending is not None else None,
                worktree=worktrees.index(str(root)) + 1, worktree_count=len(worktrees),
                known_from='Git, static, now' if pending is not None else 'no Git worktree')


def _edited_functions(root, base, data, reader):
    """Use target-start function identities; missing older facts stay unknown."""
    files = [path for path in list_files(root)
             if path.endswith('.py') and not matches_any(path, ignore_patterns(data))]
    git_base = base.get('git')
    if isinstance(git_base, str):
        changed = _read_git(root, reader, 'diff', '--relative', '--name-only', '-z', git_base, '--', '.')
        untracked = _read_git(root, reader, 'ls-files', '--others', '--exclude-standard', '-z')
        if changed is None or untracked is None:
            return [], 'unknown: target Git base is unavailable'
        files = sorted((set(changed) | set(untracked)) & set(files)
                       | {path for path in changed if path.endswith('.py') and not (root / path).exists()})
    elif isinstance(base.get('files'), dict):
        files = sorted(set(files) | {path for path in base['files'] if path.endswith('.py')})
    else:
        return [], 'unknown: target has no function baseline'
    edited, unknown = [], []
    for path in files:
        if path.startswith('.flowguard/'):
            continue
        try:
            current = function_identities(read_source(root / path)) if (root / path).exists() else {}
            if isinstance(git_base, str):
                old_source = _read_git(root, reader, 'show', f'{git_base}:./{path}')
                previous = function_identities('\0'.join(old_source)) if old_source is not None else {}
            else:
                entry = base['files'].get(path)
                previous = entry.get('functions') if entry is not None else {}
            if current is None or previous is None:
                unknown.append(path)
                continue
            for name in sorted(previous.keys() | current.keys()):
                if previous.get(name) is None and name in previous or current.get(name) is None and name in current:
                    unknown.append(path + ':' + name)
                elif previous.get(name) != current.get(name):
                    edited.append(path + ':' + name)
        except (OSError, UnicodeError, SyntaxError, ValueError):
            unknown.append(path)
    return edited, 'static, now; unknown function identities: ' + ', '.join(unknown) if unknown else 'target-start AST identities, static, now'


def collect_status(root, *, read_git_paths):
    """Read only; CLI supplies the existing disposable-index Git reader."""
    root = Path(root).resolve()
    data = load_map(root)
    target = load_target(root)
    peers = other_worktrees(root)
    git = _git_header(root, read_git_paths, peers)
    records = change_records(root)
    history = since_release(root, records, read_git_paths)
    requests = request_details(root, records=records, worktrees=peers)
    released = history.pop('released_requests')
    for item in requests:
        item.update({'age': _age(item.get('received')),
                     'since_release': None if released is None else item['id'] not in released,
                     'known_from': 'request sidecar and current target/worktree/record links, static, now'})
    # Completed requests from before a known release do not make the screen grow with history.
    requests = [item for item in requests if not item['state'].startswith('done ') or item['since_release'] is not False]
    change, plan = None, []
    if target is not None:
        base = json.loads((root / '.flowguard/target/base.json').read_bytes())
        edited, known = _edited_functions(root, base, data, read_git_paths)
        change = dict(goal=target.goal, requests=target.data.get('requests', []), base=base.get('git'),
                      started=base.get('started'), age=_age(base.get('started')), edited_functions=edited,
                      edited_known_from=known)
        plan = static_plan_rows(root, target, build_target_view(root, data, target))
    others = []
    for peer in peers:
        opened = load_target(peer)
        if opened is None:
            continue
        directory = peer / '.flowguard/target'
        edited = max(path.stat().st_mtime for path in directory.rglob('*') if path.is_file())
        peer_plan = directory / 'PLAN.txt'
        size = sum(bool(line.strip()) and not line.lstrip().startswith('#')
                   for line in peer_plan.read_text(encoding='utf-8-sig').splitlines()) if peer_plan.exists() else 0
        others.append(dict(root=str(peer), goal=opened.goal, requests=opened.data.get('requests', []),
                           last_edit=datetime.fromtimestamp(edited, timezone.utc).isoformat(), plan_size=size,
                           known_from='current target files and their mtimes, static, now'))
    command = shlex.join(['python', '-m', 'flowguard', 'target', 'check', '--root', str(root)])
    note = None
    if target is not None:
        next_step = advice('check', command)
    else:
        pending = set(git['uncommitted_paths'] or ())
        unpublished = [identifier for identifier, _ in records if (CHANGE_DIR / (identifier + '.json')).as_posix() in pending]
        if unpublished:
            message = root / CHANGE_DIR / (unpublished[-1] + '.msg')
            next_step = advice('commit', shlex.join(['git', '-C', str(root), 'commit', '-F', str(message)]))
            note = 'Stage the reviewed code, requests, change record and target deletions before committing.'
        else:
            next_step = advice('check', shlex.join(['python', '-m', 'flowguard', 'read', '--root', str(root)]))
    return dict(root=str(root), scope='legacy static status; no exploration or stored verdicts', git=git,
                change=change, plan=plan, verdicts=dict(stored=False, command=command), requests=requests,
                since_release=history, other_changes=others, jobs='none in the legacy runtime',
                next=next_step, next_note=note)


def render_status(result):
    git = result['git']
    pending = git['uncommitted_paths']
    lines = [f"FLOWGUARD STATUS {result['root']}  branch {git['branch'] or '(detached or no Git)'} "
             f"at {git['head'] or '(unborn or no Git)'}  (worktree {git['worktree']} of {git['worktree_count']})",
             f"  uncommitted: {', '.join(pending) if pending else 'none' if pending == [] else 'unknown (no Git)'} [{git['known_from']}]"]
    opened = result['change']
    if opened:
        links = ', '.join(link['id'] + (':part' if link['part'] else '') for link in opened['requests']) or 'none'
        lines.append(f"OPEN CHANGE {opened['goal']!r} for {links}; base {opened['base'] or '(file baseline)'}; "
                     f"started {opened['started'] or 'unknown'} ({opened['age']}) [target, static, now]")
        lines.append(f"  edited since base: {', '.join(opened['edited_functions']) or 'none known'} [{opened['edited_known_from']}]")
        if result['plan']:
            lines.append(f"PLAN {Path(result['root']) / PLAN_RELPATH}")
            for row in result['plan']:
                lines.append(f"  {row['number']} {row['line']} | {row['state']} | {row['known_from']}")
                lines.extend('    ' + problem for problem in row['problems'])
            lines.append('  added after code: unknown; static status stores no edit-order or completion verdict')
    else:
        lines.append('OPEN CHANGE none [current target directory, static, now]')
    lines.append('verdicts: none stored; ' + result['verdicts']['command'])
    for item in result['requests']:
        context = item.get('stored_during')
        suffix = f"; stored during {context.get('goal', '')!r} (started {context.get('started') or 'unknown'})" if context else ''
        marker = '; stored since release' if item['since_release'] else '; release boundary unknown' if item['since_release'] is None else ''
        lines.append(f"REQUEST {item['id']} {item['state']} ({item['age']}); {item.get('kind', 'unknown')}: "
                     f"{item['first_line']}{suffix}{marker} [sidecar/current links, static, now]")
    history = result['since_release']
    counts = (f"{len(history['changes'])} changes; {len(history['code_commits_without_record'])} code commits without a record"
              if history['changes'] is not None else 'change/commit counts unknown')
    lines.append(f"SINCE RELEASE {history['release'] or 'unknown'}: {counts} [{history['known_from']}]")
    if history['changes'] is not None:
        lines.append('  details: ' + shlex.join(['python', '-m', 'flowguard', 'status', '--json', '--root', result['root']]))
    for item in result['other_changes']:
        lines.append(f"OTHER OPEN CHANGE {item['goal']!r} in {item['root']}; last edit {item['last_edit']}; "
                     f"{item['plan_size']} plan lines [{item['known_from']}]")
    if result['next_note']:
        lines.append(result['next_note'])
    lines.append('NEXT ' + render_advice(result['next']))
    return '\n'.join(lines)
