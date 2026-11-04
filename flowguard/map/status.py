"""Compute the legacy static recovery view; never explore or store a verdict."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex

from .common import (CACHE_RELDIR, advice, atomic_write_text, cache_dir, git_common_directory, git_head,
                     git_run, matches_any, project_command, project_root, read_source, render_advice)
from .inventory import list_files
from .mapfile import MapError, ignore_patterns, load_map
from .plan import PLAN_RELPATH, function_identities, static_plan_rows
from .records import CHANGE_DIR, change_records, commit_advice, protected_paths, since_release
from .requests import REQUEST_DIR, other_worktrees, owner_words, validate_request_links
from .targetfile import build_target_view, load_target, target_base


def _age(moment):
    if not moment:
        return 'unknown'
    seconds = max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(moment)).total_seconds()))
    return f'{seconds // 86400} days' if seconds >= 86400 else f'{seconds // 60} min'


def _git_header(root, reader, peers):
    worktrees = sorted([str(root), *(str(peer) for peer in peers)])
    place = dict(worktree=worktrees.index(str(root)) + 1, worktree_count=len(worktrees))
    if git_common_directory(root) is None:
        return dict(head=None, branch=None, uncommitted_paths=None, **place, known_from='no Git worktree')
    head = git_head(root)
    branch = git_run(root, 'symbolic-ref', '--short', '-q', 'HEAD', allowed=(0, 1)).stdout  # exit 1: detached HEAD
    pending = reader(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--', '.')
    prefix = reader(root, 'rev-parse', '--show-prefix')
    prefix = prefix[0].rstrip('\r\n') if prefix else ''
    paths = []
    iterator = iter(pending)
    for row in iterator:
        paths.append(row[3:])
        if 'R' in row[:2] or 'C' in row[:2]:
            paths.append(next(iterator))
    paths = [path[len(prefix):] if path.startswith(prefix) else path for path in paths]
    return dict(head=head, branch=os.fsdecode(branch).strip() or None, uncommitted_paths=sorted(set(paths)),
                **place, known_from='Git, static, now')


def _edited_functions(root, base, data, reader):
    """Use target-start function identities; missing older facts stay unknown."""
    files = [path for path in list_files(root)
             if path.endswith('.py') and not matches_any(path, ignore_patterns(data))]
    git_base = base.get('git')
    if isinstance(git_base, str):
        if (git_common_directory(root) is None
                or git_run(root, 'rev-parse', '-q', '--verify', git_base + '^{commit}', allowed=(0, 1)).returncode):
            return [], 'unknown: target Git base commit is not in this clone'
        changed = reader(root, 'diff', '--relative', '--name-only', '-z', git_base, '--', '.')
        untracked = reader(root, 'ls-files', '--others', '--exclude-standard', '-z')
        at_base = set(reader(root, 'ls-tree', '-r', '--name-only', '-z', git_base, '--', '.'))
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
                previous = (function_identities('\0'.join(reader(root, 'show', f'{git_base}:./{path}')))
                            if path in at_base else {})
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


def collect_status(root, *, read_git_paths, version):
    """Read only; CLI supplies the existing disposable-index Git reader."""
    root = Path(root).resolve()
    target = load_target(root)
    peers = other_worktrees(root)
    git = _git_header(root, read_git_paths, peers)
    unreadable = []
    records = change_records(root, unreadable=unreadable)
    history = since_release(root, records, read_git_paths)
    words = owner_words(root, records=records)
    protected = None
    for row in words['rows']:
        meta = REQUEST_DIR / (row['id'] + '.json')
        if row['invalid'] and not (root / meta).is_file():
            if protected is None:
                protected = protected_paths(root, REQUEST_DIR)
            if meta.as_posix() not in protected:
                try:
                    validate_request_links(root, [dict(id=row['id'], part=False)])
                except MapError as error:
                    row.update(not_stored=str(error), invalid=None, edited=None)
    released = history.pop('released_retired')
    words['retired_since_release'] = [row['id'] for row in words['rows']
                                      if row['retired'] and (released is None or row['id'] not in released)]
    change, plan = None, []
    if target is not None:
        data = load_map(root)
        base = target_base(root)  # a damaged base.json is named, never read as no base
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
    # NEXT names a pending step only: an open target, or a promoted change still to commit.
    next_step, note = None, None
    if target is not None:
        next_step = advice('check', shlex.join(['python', '-m', 'flowguard', 'target', 'check', '--root', str(root)]))
    else:
        pending = set(git['uncommitted_paths'] or ())
        unpublished = [(identifier, record) for identifier, record in records
                       if (CHANGE_DIR / (identifier + '.json')).as_posix() in pending]
        if unpublished and isinstance(unpublished[-1][1].get('stage'), list):
            next_step = commit_advice(root, unpublished[-1][1])
        elif unpublished:
            note = (f'change {unpublished[-1][0]} records no file list (promoted before FlowGuard 0.72.0 or outside Git): '
                    'stage its files, then commit them with your own message.')
    from ..flow.cli import status_lines  # the flow models' open conflicts: .flowguard/conflicts.json only
    return dict(root=str(root), scope='static status, no exploration; flow-model conflicts as the last final check '
                'recorded them', git=git,
                change=change, plan=plan, verdicts=dict(stored=False), flow_models=status_lines(root), owner_words=words,
                since_release=history, unreadable_records=[dict(id=identifier, error=error) for identifier, error in unreadable],
                other_changes=others, jobs='none in the legacy runtime',
                skill_warnings=installed_skill_warnings(version), next=next_step, next_note=note)


def agent_session():
    """The agent session this process runs in; only Claude Code's own session id is a verified key."""
    if os.environ.get("CLAUDECODE") != "1":
        return None
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or ""


def mark_status_shown(root, session):
    atomic_write_text(cache_dir(root) / "status-shown.json",
                      json.dumps({"session": session, "shown": datetime.now(timezone.utc).isoformat()}) + "\n")


def show_status_first(arguments, version, *, read_git_paths):
    """Show status once per agent session, before the session's first other FlowGuard command.

    Every entry point calls this (python -m flowguard and python -m flowguard.map). The project is the one the
    command works on (common.project_root); outside a project nothing is shown."""
    import argparse
    import sys
    session = agent_session()
    if session is None or {"-h", "--help"} & set(arguments):
        return
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root")
    root = project_root(parser.parse_known_args(arguments)[0].root)
    if not (root / ".flowguard").is_dir():
        return
    command = project_command(root, "status")
    if not session:
        print(f"flowguard: CLAUDECODE=1 but CLAUDE_CODE_SESSION_ID is unset; status is not shown automatically: {command}",
              file=sys.stderr)
        return
    try:
        marker = root / CACHE_RELDIR / "status-shown.json"
        if marker.is_file() and json.loads(marker.read_text(encoding="utf-8")).get("session") == session:
            return
        screen = render_status(collect_status(root, read_git_paths=read_git_paths, version=version))
    except Exception as error:  # the requested command still runs; the failure is named, never hidden
        print(f"flowguard: status could not be shown first ({type(error).__name__}: {error}); run {command}", file=sys.stderr)
        return
    print(screen, file=sys.stderr)
    mark_status_shown(root, session)


def installed_skill_warnings(version):
    """Compare the documented skill install targets with the running package version; absent copies say nothing."""
    current = tuple(int(part) for part in version.split('.')[:3])
    codex = Path(os.environ['CODEX_HOME']) if os.environ.get('CODEX_HOME') else Path.home() / '.codex'
    warnings = []
    for path in (Path.home() / '.claude/skills/flowguard/SKILL.md', codex / 'skills/flowguard/SKILL.md'):
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError as error:
            warnings.append(f'WARNING cannot read installed skill text {path}: {error}')
            continue
        match = re.search(r'FlowGuard\.git@v(\d+)\.(\d+)\.(\d+)', text)
        installed = tuple(int(part) for part in match.groups()) if match else None
        if installed == current:
            continue
        if installed is not None and installed > current:
            warnings.append(f"WARNING installed skill text {path} is for v{'.'.join(map(str, installed))} but FlowGuard "
                            f"here is {version}: ask the owner to install FlowGuard v{'.'.join(map(str, installed))}")
            continue
        named = f"is for v{'.'.join(map(str, installed))}" if installed else 'names no version'
        warnings.append(f'WARNING installed skill text {path} {named}; FlowGuard here is {version}: trust AGENTS.md '
                        f'and this tool\'s output; ask the owner to reinstall it (python scripts/install_skill.py '
                        f'--target {path.parent.parent}, from a v{version} clone)')
    return warnings


SHOWN_OWNER_WORDS = 3


def _damage(row):
    """How a stored request's own files changed, with the restore step; None when they hold."""
    if row.get('not_stored'):
        return f"not a stored request: {row['not_stored']}"
    if row['invalid']:
        return f"unreadable ({row['invalid']})"
    if row['edited']:
        hidden = '' if row['retired'] else ", so its text is not shown as the owner's words"
        return f"edited after it was stored{hidden}: {row['edited']}"
    return None


def render_owner_words(words):
    """The newest owner words in full first lines; retired planner text never appears as owner words.

    A request whose files changed is named with its restore step: in its row when the row is shown in full,
    in one WARNING line when it is retired or older than the rows shown."""
    rows = [row for row in words['rows'] if not row['retired']]
    lines = []
    if not rows:
        lines.append('OWNER WORDS none stored')
    else:
        lines.append('OWNER WORDS newest first (full text: .flowguard/requests/<id>.md)'
                     + ('' if words['commit_links_known'] else '; commit links unknown (no Git history)'))
        for row in rows[:SHOWN_OWNER_WORDS]:
            when = row['received'][:16].replace('T', ' ') + ' UTC' if row['received'] else 'unknown time'
            kind = '' if row['kind'] in (None, 'request') else f" [{row['kind']}]"
            text = _damage(row)
            if text is None and row['superseded_by']:
                text = 'superseded by ' + ', '.join(row['superseded_by'])
            elif text is None:
                more = row['extra_lines']
                text = row['first_line'] + (f" (+{more} line{'s' if more > 1 else ''})" if more else '')
            cited = ''
            if row['cited_by']:
                more = len(row['cited_by']) - 2
                cited = ('  cited by: ' + ', '.join(row['cited_by'][:2])
                         + (f" and {more} more (python -m flowguard where {row['id']})" if more > 0 else ''))
            lines.append(f"  {row['id']}{kind} {when}: {text}{cited}")
        older = rows[SHOWN_OWNER_WORDS:]
        if older:
            names = ', '.join(row['id'] + (f" (superseded by {', '.join(row['superseded_by'])})" if row['superseded_by'] else '')
                              for row in older)
            lines.append(f"  older: {names} (python -m flowguard where {older[0]['id']})")
    if words['retired_since_release']:
        lines.append("RETIRED (not the owner's words): " + ', '.join(words['retired_since_release']))
    shown = {row['id'] for row in rows[:SHOWN_OWNER_WORDS]}
    for row in words['rows']:
        if row['id'] not in shown and _damage(row):
            lines.append(f"WARNING {'retired request' if row['retired'] else 'request'} {row['id']} {_damage(row)}")
    problems = words.get('retire_problems', {})
    unchecked = [identifier for identifier, problem in problems.items() if problem.startswith('cannot be checked here')]
    if unchecked:
        lines.append(f"WARNING retire record{'s' if len(unchecked) > 1 else ''} {', '.join(unchecked)} "
                     f"{problems[unchecked[0]]}; {'they still hide those texts' if len(unchecked) > 1 else 'it still hides that text'} "
                     "from OWNER WORDS")
    for identifier, problem in problems.items():
        if identifier not in unchecked:
            lines.append(f"WARNING retire record {identifier} {problem}; it still hides {identifier} from OWNER WORDS")
    return lines


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
    lines.extend(result['flow_models'])
    lines.extend(render_owner_words(result['owner_words']))
    lines.extend(f"WARNING change record {item['id']} unreadable: {item['error']}"
                 for item in result['unreadable_records'])
    lines.extend(result['skill_warnings'])
    history = result['since_release']
    counts = f"{len(history['changes'])} changes" if history['changes'] is not None else 'change count unknown'
    lines.append(f"SINCE RELEASE {history['release'] or 'unknown'}: {counts} [{history['known_from']}]")
    if history['changes'] is not None:
        lines.append('  details: ' + shlex.join(['python', '-m', 'flowguard', 'status', '--json', '--root', result['root']]))
    for item in result['other_changes']:
        lines.append(f"OTHER OPEN CHANGE {item['goal']!r} in {item['root']}; last edit {item['last_edit']}; "
                     f"{item['plan_size']} plan lines [{item['known_from']}]")
    if result['next_note']:
        lines.append(result['next_note'])
    if result['next']:
        lines.append(render_advice(result['next'], prefix='NEXT '))
    return '\n'.join(lines)
