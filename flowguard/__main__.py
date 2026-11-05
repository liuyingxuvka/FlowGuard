"""python -m flowguard --help: source queries, owner words and executable flow checks."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .map.common import advice, print_verdict, quiet_broken_pipe, render_advice, safe_stdio, project_command

VERB_PURPOSE = {
    'where': 'Locate source functions, calls, architecture and original text without execution.',
    'status': 'Refresh changed models and show open conflicts, owner words and current source facts.',
    'check': 'Check executable flow models and report sourced conflicts.',
    'show': 'Draw a flow model, change or conflict.',
    'decide': 'Record sourced owner choices for a genuine requirement conflict.',
    'req': "Store the owner's words once, byte for byte.",
    'template': 'Write project adoption instructions.',
    'release': 'Check all flow models and, with --shards, the whole test suite.',
}
FLOW_VERBS = ('check', 'show', 'decide')


def _verb_parser(verb):
    if verb in FLOW_VERBS:
        from .flow.cli import verb_parser
        return verb_parser(verb)
    parser = argparse.ArgumentParser(prog=f'python -m flowguard {verb}')
    if verb == 'template':
        parser.add_argument('name', nargs='?')
        parser.add_argument('--list', action='store_true')
        parser.add_argument('--write', metavar='DIR')
        parser.add_argument('--force', action='store_true', help='overwrite generated files; existing owner instruction files stay intact')
        return parser
    parser.add_argument('--root', help='project root (default: the project holding the current directory)')
    if verb == 'where':
        parser.add_argument('name', nargs='?', metavar='NAME')
        views = parser.add_mutually_exclusive_group()
        for view, purpose in (('flow', 'static calls'), ('arch', 'source architecture'),
                              ('text', 'original text and source references'), ('keyflows', 'shared state and stores')):
            views.add_argument('--' + view, dest='view', action='store_const', const=view, help='show ' + purpose)
        parser.set_defaults(view='tree')
        parser.add_argument('--at', metavar='REF', help='read text and source from this Git reference (requires --text)')
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--json', action='store_true')
    elif verb == 'status':
        parser.add_argument('--json', action='store_true')
        parser.add_argument('--hook', action='store_true', help='silent outside a project; diagnostic failures do not stop the caller')
        parser.add_argument('--wait', type=float, default=90.0, metavar='S')
    elif verb == 'req':
        commands = parser.add_subparsers(dest='request_command', required=True)
        add = commands.add_parser('add')
        add.add_argument('file', help='owner text file, or - for raw stdin bytes')
        add.add_argument('--id', dest='identifier')
        add.add_argument('--kind', choices=('request', 'glossary', 'adoption'), default='request')
        add.add_argument('--supersedes', action='append', default=[], metavar='ID')
        add.add_argument('--root', default=argparse.SUPPRESS)
        retire = commands.add_parser('retire', help="record that stored text was not the owner's words")
        retire.add_argument('identifier', metavar='ID')
        retire.add_argument('--not-owner', action='store_true', required=True)
        retire.add_argument('--note')
        retire.add_argument('--root', default=argparse.SUPPRESS)
    elif verb == 'release':
        parser.add_argument('--json', action='store_true')
        parser.add_argument('--shards', type=int, choices=range(1, 33), metavar='N',
                            help='after flow checks pass, run the whole pytest suite in 1-32 shards')
    return parser


def template_factories():
    from .templates import adoption_template_files
    return {'adoption': adoption_template_files}


def _template(ns):
    if ns.list or not ns.name:
        print('adoption')
        return 0
    factory = template_factories().get(ns.name)
    if factory is None:
        print(f"unknown template {ns.name!r}; run 'python -m flowguard template --list'", file=sys.stderr)
        return 2
    files = factory()
    if ns.write:
        from .templates import EARLIER_RULES_MARKERS, OWNER_FILES, AdoptionRulesFound, adoption_rules_in, write_template_files
        try:
            written = write_template_files(ns.write, files, overwrite=ns.force)
        except FileExistsError as error:
            print(f'{error}; use --force to overwrite', file=sys.stderr)
            return 1
        except OSError as error:
            print(f'error: {error}', file=sys.stderr)
            return 2
        for path in written:
            print(f'wrote {path}')
        for file in files:
            path = Path(ns.write) / file.path
            if file.path not in OWNER_FILES or path in written:
                continue
            if file.path == "AGENTS.md" and path.is_file():
                try:
                    found = adoption_rules_in(path.read_text(encoding="utf-8-sig", errors="replace"))
                except OSError as error:
                    found = AdoptionRulesFound(False, (), ())
                    print(f"cannot read {path.absolute()}: {error}")
                begin, end = EARLIER_RULES_MARKERS
                named = sorted([(first, f"  lines {first}-{last}: the earlier FlowGuard block, from {begin} to {end}, "
                                        "markers included") for first, last in found.blocks]
                               + ([] if found.held else [(number, f"  line {number}: "
                                                                  + (line if len(line) <= 100 else line[:97] + "..."))
                                                         for number, line in found.lines]))
                if found.held and not named:
                    print(f"kept AGENTS.md: {path.absolute()} already holds the current FlowGuard rules; nothing to add")
                    continue
                if found.held:  # an earlier block is left beside the current rules: remove it, add nothing
                    print("kept AGENTS.md (it exists): FlowGuard does not edit it; it holds the current FlowGuard rules,"
                          " and these lines of it hold "
                          + ("an earlier FlowGuard block:" if len(named) == 1 else "earlier FlowGuard blocks:"))
                    print(*(entry for _, entry in named), sep="\n")
                    print(f"remove those lines from {path.absolute()}; keep the current rules there")
                    continue
                print("kept AGENTS.md (it exists): FlowGuard does not edit it"
                      + ("; these lines of it look like earlier FlowGuard rules:" if named else ""))
                for _, entry in named:
                    print(entry)
                print(f"put these lines in {path.absolute()} in place of the lines named above:" if named else
                      f"add these lines to {path.absolute()}, replacing any earlier FlowGuard rules there:")
                print(file.content, end="")
            elif file.path == "AGENTS.md":
                print(f"{path.absolute()} is not a file: replace it with a file that holds these lines:")
                print(file.content, end="")
            elif path.exists() or path.is_symlink():
                print("kept CLAUDE.md (it exists): make sure it holds the line @AGENTS.md")
            else:
                print(f"did not write CLAUDE.md: {path.parent.absolute() / 'AGENTS.md'} is not a file, so its line @AGENTS.md "
                      "would include nothing")
        return 0
    for file in files:
        print(f'===== {file.path} =====')
        print(file.content)
    return 0


def _request(ns: argparse.Namespace) -> int:
    from .map.common import MapError
    from .map.requests import store_request

    from .map.requests import RETIRED_DIR, retire_request

    root = Path(ns.root).resolve()
    if ns.request_command == "retire":
        try:
            retire_request(root, ns.identifier, note=ns.note)
        except (OSError, MapError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(f"retired {ns.identifier}: not the owner's words ({(RETIRED_DIR / (ns.identifier + '.json')).as_posix()})")
        return 0
    try:
        raw = sys.stdin.buffer.read() if ns.file == "-" else Path(ns.file).read_bytes()
        item = store_request(root, raw, identifier=ns.identifier, kind=ns.kind, supersedes=ns.supersedes)
    except (OSError, MapError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    replaces = f"; supersedes {', '.join(item['supersedes'])}" if item.get('supersedes') else ''
    print(f"stored {item['id']} ({item['kind']}, sha {item['sha256'][:12]}, {item['bytes']} bytes{replaces})")
    print(render_advice(advice("status", project_command(root, "status"))))
    return 0


def _status(ns):
    import json
    from .map import status
    from .map.common import read_git_paths

    try:
        root = Path(ns.root).resolve()
        if ns.hook and not (root / '.flowguard').is_dir():
            return 0
        from .flow.cli import refresh_status
        refreshed = refresh_status(root, wait=ns.wait) if not ns.hook else dict(refreshed=[], exit=0)
        result = status.collect_status(root, read_git_paths=read_git_paths, version=__version__)
        result['flow_refresh'] = refreshed
        result['scope'] = 'current static facts after refreshing changed flow models through existing check jobs'
        session = status.agent_session()
        result['session'] = session or None
        if ns.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            flow = result['flow_models']
            has_conflicts = any(line.startswith('OPEN ') for line in flow)
            if has_conflicts:
                print('\n'.join(flow))
            print(status.render_status(dict(result, flow_models=[])) if has_conflicts else status.render_status(result))
        if session:
            status.mark_status_shown(root, session)
        return 0
    except Exception as error:
        if ns.hook:
            print(f'flowguard status failed ({type(error).__name__}); run python -m flowguard status for details')
            return 0
        print(f'error: {error}', file=sys.stderr)
        return 2


def _where(ns):
    from .map import derived, textrules
    from .map.common import MapError

    root = Path(ns.root).resolve()
    every = project_command(root, "where", *([ns.name] if ns.name else []), *(["--" + ns.view] if ns.view != "tree" else []),
                            *(["--at", ns.at] if ns.at else []), "--all", *(["--json"] if ns.json else []))
    try:
        if ns.view == "text":
            facts = textrules.report(root, at=ns.at)
            result = textrules.select(facts, ns.name, origins=ns.all) if ns.name else textrules._compact(facts)
            groups = result.get("related_groups", result["literal_groups"] + result["workflow_groups"])[:3]
            selectors = ["group:" + row["id"] for row in groups]
            texts = result.get("texts", facts["texts"])
            if texts and ns.name != texts[0]["path"]:
                selectors.append(texts[0]["path"])
            if texts:
                literal = 'text:' + texts[0]['text'].splitlines()[0][:160]
                if literal != ns.name:
                    selectors.append(literal)
            options = ["--text", *(["--at", ns.at] if ns.at else []), *(["--json"] if ns.json else [])]
            result["selectors"] = ["FILE", "source:<id>", "group:<id>", "text:<literal phrase>"]
            result["next"] = [advice("where", project_command(root, "where", selector, *options))
                              for selector in dict.fromkeys(selectors)]
            renderer = textrules
        else:
            result = derived.where(root, ns.name, view=ns.view)
            if "unexpanded_functions" in result:
                modules = result.get("modules", [])
                options = ([modules[0]["path"]] + (["--flow"] if ns.view == "flow" else [])) if modules else ["--arch"]
                result["next"] = [advice("where", project_command(root, "where", *options, *(["--json"] if ns.json else [])))]
            else:
                result["next"] = []
            renderer = derived
        # One route for next steps in every view and in --json: {id, command} objects in "next".
        shown = renderer.project(result, all_rows=ns.all)
        if shown.get("omitted"):
            shown["next"] = [*shown["next"], advice("where", every)]
        output = renderer.render(shown, as_json=ns.json, all_rows=ns.all)
        if not ns.json and shown["next"]:
            output += "\n" + "\n".join(render_advice(item) for item in shown["next"])
        print(output)
        return 0
    except (OSError, ValueError, RuntimeError, MapError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


@quiet_broken_pipe
def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(args)
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        return 2
    except Exception as error:
        from .flow.cli import _early, internal_text
        text = internal_text(error)
        if args[:1] == ['release'] and '--json' in args:
            print(text, file=sys.stderr)
            print_verdict('release', 2, [dict(level='error', code='runtime_error', subject='flow')])
            return 2
        if args and args[0] in FLOW_VERBS:
            return _early(sys.stdout, text, 2, '--json' in args)
        print(text, file=sys.stderr)
        return 2


def _dispatch(args):
    safe_stdio()
    if not args or args[0] in {'-h', '--help', 'help'}:
        print(__doc__.strip())
        for verb, purpose in VERB_PURPOSE.items():
            print(f'\n{verb:<10}{purpose}')
            print(_verb_parser(verb).format_usage().strip())
        return 0
    if args[0] in {'--version', 'version'}:
        print(__version__)
        return 0
    verb, rest = args[0], args[1:]
    if verb not in VERB_PURPOSE:
        print(f"unknown command {verb!r}; run 'python -m flowguard --help'", file=sys.stderr)
        return 2
    if verb != 'status':
        from .map.common import read_git_paths
        from .map.status import show_status_first
        show_status_first(rest, __version__, read_git_paths=read_git_paths)
    if verb in FLOW_VERBS:
        from .flow.cli import main as flow_main
        return flow_main([verb, *rest])
    parser = _verb_parser(verb)
    ns = parser.parse_args(rest)
    if hasattr(ns, 'root'):
        from .map.common import project_root
        ns.root = str(project_root(ns.root))
    if verb == 'where':
        if ns.at is not None and ns.view != 'text':
            parser.error('--at requires --text')
        return _where(ns)
    if verb == 'status':
        return _status(ns)
    if verb == 'req':
        return _request(ns)
    if verb == 'template':
        return _template(ns)
    from .flow.release import run
    return run(ns.root, shards=ns.shards, as_json=ns.json)


if __name__ == '__main__':
    raise SystemExit(main())
