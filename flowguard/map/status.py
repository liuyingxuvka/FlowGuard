"""Current Git, owner-word and executable-check facts, without a target/map lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .common import (CACHE_RELDIR, MapError, atomic_write_text, cache_dir, git_common_directory,
                     git_head, git_run, project_command, project_root)
from .records import protected_paths, since_release
from .requests import REQUEST_DIR, other_worktrees, owner_words, validate_request_links


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


def collect_status(root, *, read_git_paths, version):
    """Read current facts; the command's existing flow owner performs any refresh."""
    root = Path(root).resolve()
    git = _git_header(root, read_git_paths, other_worktrees(root))
    words = owner_words(root)
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
    # This is an immutable original-word boundary reader, not an old change gate.
    history = since_release(root, [], read_git_paths)
    retired = history['released_retired']
    words['retired_since_release'] = [row['id'] for row in words['rows']
                                     if row['retired'] and (retired is None or row['id'] not in retired)]
    from ..flow.cli import status_lines
    return dict(root=str(root), scope='current source facts and the last recorded executable checks',
                git=git, flow_models=status_lines(root), owner_words=words,
                skill_warnings=installed_skill_warnings(version))


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

    The public entry point calls this. The project is the one the
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
    lines.extend(result['flow_models'])
    refresh = result.get('flow_refresh') or {}
    if refresh.get('upgrade'):
        lines.insert(0, 'UPGRADE REQUIRED: ' + ', '.join(refresh['upgrade']) +
                     '; migrate their behavior to flow models and native tests, then remove these old artifacts')
    if refresh.get('running') is not None:
        lines.insert(0, 'RUNNING: changed model checks; resume with: ' + refresh['resume'])
    lines.extend(render_owner_words(result['owner_words']))
    lines.extend(result['skill_warnings'])
    return '\n'.join(lines)
