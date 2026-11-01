"""python -m flowguard --help: daily verbs on top of the FlowGuard map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .map.cli import main as map_main
from .map.proof import DEFAULT_JOBS
from .map.common import advice, print_verdict, quiet_broken_pipe, render_advice, safe_stdio, project_command





VERB_PURPOSE = {
    'read': 'Understand the components, models and their relationships.',
    'where': 'Locate source functions, calls, architecture and attributed original text without execution.',
    'status': 'Resume from static project and target facts and the newest owner words; never explore.',
    'change': 'Check an edit and run the affected tests and models.',
    'release': 'Run the release gate, optionally with whole-suite shards.',
    'template': 'Write starter model and test files.',
    'target': 'Legacy route, kept until v1.0.0: plan, check and promote a change of the legacy models.',
    'req': "Store the owner's words byte for byte, with immutable metadata; retire a stored text the owner did not write.",
    'map': 'Use every map and proof command.',
}


def _verb_parser(verb: str) -> argparse.ArgumentParser:
    if verb == "target":
        from .map.target import build_parser

        return build_parser()
    p = argparse.ArgumentParser(prog=f"python -m flowguard {verb}")
    if verb == "template":
        p.add_argument("name", nargs="?", help="template name (see --list)")
        p.add_argument("--list", action="store_true", help="list template names")
        p.add_argument(
            "--write", metavar="DIR", help="write the files under DIR instead of printing them"
        )
        p.add_argument("--force", action="store_true", help="overwrite existing files when writing")
        return p
    p.add_argument("--root", help="project root (default: the project holding the current directory)")
    if verb == "where":
        p.add_argument("name", nargs="?", metavar="NAME", help="source name or, with --text, FILE, source:<id>, group:<id> or text:<literal phrase>")
        views = p.add_mutually_exclusive_group()
        for view, purpose in (("flow", "static calls"), ("arch", "source architecture"),
                              ("text", "original text and source references"), ("keyflows", "shared state and stores")):
            views.add_argument("--" + view, dest="view", action="store_const", const=view, help="show " + purpose)
        p.set_defaults(view="tree")
        p.add_argument("--at", metavar="REF", help="read text and code from the same Git reference (requires --text)")
        p.add_argument("--all", action="store_true", help="print every row instead of the bounded most relevant part")
        p.add_argument("--json", action="store_true", help="print one structured static view")
        return p
    if verb == "status":
        p.add_argument('--json', action='store_true', help='print one structured static view')
        p.add_argument('--hook', action='store_true', help='silent outside a project; internal errors never fail the hook')
        p.add_argument('--wait', type=float, metavar='S', help='legacy static runtime has no jobs to wait for')
        return p
    if verb == "req":
        commands = p.add_subparsers(dest="request_command", required=True)
        add = commands.add_parser("add")
        add.add_argument("file", help="owner text file, or - for raw stdin bytes")
        add.add_argument("--id", dest="identifier")
        add.add_argument("--kind", choices=("request", "glossary", "adoption"), default="request")
        add.add_argument("--supersedes", action="append", default=[], metavar="ID",
                         help="an earlier stored request that these owner words replace (repeatable)")
        add.add_argument("--root", default=argparse.SUPPRESS)
        retire = commands.add_parser("retire", help="record once that a stored text is not the owner's words")
        retire.add_argument("identifier", metavar="ID")
        retire.add_argument("--not-owner", action="store_true", required=True,
                            help="the only reason to retire: the stored text was not written by the owner")
        retire.add_argument("--note", help="why, in your own words")
        retire.add_argument("--root", default=argparse.SUPPRESS)
        return p
    if verb == "read":
        group = p.add_mutually_exclusive_group()
        group.add_argument("--component", help="show one component in detail")
        group.add_argument(
            "--field", metavar="NAME", help="field writers, readers, rules and tests"
        )
        group.add_argument(
            "--find",
            nargs="+",
            metavar="WORD",
            help="words, a location path[:symbol], or a test path[::test]",
        )
        p.add_argument(
            "--mermaid",
            action="store_true",
            help="export the model tree (incompatible with --find)",
        )
        p.add_argument(
            "--target",
            action="store_true",
            help="show changes made by the target (incompatible with --find)",
        )
        p.add_argument(
            "--review",
            action="store_true",
            help="rank architecture strengths, defects and next steps (incompatible with the other views)",
        )
    elif verb == "change":
        p.add_argument(
            "--broad", action="store_true", help="include all ancestors and review models"
        )
        p.add_argument(
            "--verbose",
            action="store_true",
            help="print the exact selected test commands and nodes",
        )
        p.add_argument("--base", default="HEAD", help="git revision to diff against (default HEAD)")
        p.add_argument("files", nargs="*", help="changed files (default: from git)")
        p.add_argument(
            "--run",
            action="store_true",
            help="then run the selected tests and models, one RAN line each",
        )
    elif verb == "release":
        p.add_argument("--json", action="store_true")
        p.add_argument(
            "--jobs",
            type=int,
            choices=range(1, 33),
            default=DEFAULT_JOBS,
            metavar="N",
            help="run 1-32 model subprocesses concurrently (default: min(4, CPUs))",
        )
        p.add_argument(
            "--shards",
            type=int,
            choices=range(1, 33),
            metavar="N",
            help="after normal checks pass, run the whole suite in 1-32 parallel shards",
        )
    return p


def template_factories() -> dict[str, object]:
    """Template name -> factory, from every public ``*_template_files`` function."""

    from . import templates

    suffix = "_template_files"
    return {
        name[: -len(suffix)].replace("_", "-"): getattr(templates, name)
        for name in sorted(templates.__all__)
        if name.endswith(suffix) and not name.startswith("write_")
    }


def _template(ns: argparse.Namespace) -> int:
    factories = template_factories()
    if ns.list or not ns.name:
        for name in factories:
            print(name)
        return 0
    aliases = {
        "ui-flow": "ui-journey",
        "contract-exhaustion": "validator",
    }
    factory = factories.get(aliases.get(ns.name, ns.name))
    if factory is None:
        print(f"unknown template {ns.name!r}; run 'python -m flowguard template --list'", file=sys.stderr)
        return 2
    files = factory()
    if ns.write:
        from .map.mapfile import MapError
        from .map.targetfile import load_target
        from .templates import TemplateFile, write_template_files

        current_prefix = ".flowguard/models/"
        target_prefix = ".flowguard/target/models/"
        try:
            has_target = load_target(Path(ns.write)) is not None
            if has_target:
                files = tuple(TemplateFile(target_prefix + file.path[len(current_prefix):], file.content)
                              if file.path.startswith(current_prefix) else file for file in files)
            written = write_template_files(ns.write, files, overwrite=ns.force)
        except MapError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except FileExistsError as exc:
            print(f"{exc}; use --force to overwrite", file=sys.stderr)
            return 1
        for path in written:
            staged = ".flowguard/target/models" in path.as_posix()
            print(f"wrote {Path(path).relative_to(Path(ns.write)) if staged else path}" + (" (into the open target)" if staged else ""))
        if any(file.path == "CLAUDE.md" for file in files) and Path(ns.write) / "CLAUDE.md" not in written:
            print("kept CLAUDE.md (it exists): make sure it holds the line @AGENTS.md")
        if has_target:
            if any(file.path.startswith(target_prefix) for file in files):
                print(render_advice(advice('check', project_command(Path(ns.write), 'target', 'check'))))
        else:
            for file in files:
                if file.path.startswith(current_prefix) and file.path.count("/") == 2:
                    instruction = ("replace every REPLACE_ME anchor and the example with your own code"
                                   if "REPLACE_ME" in file.content else "replace the example with your own code and behaviour")
                    print(f"edit {file.path}: {instruction}; set COMPONENTS "
                          "(and PARENT if it refines another model)")
                    project = Path(ns.write).resolve()
                    has_map = (project / '.flowguard/map.json').is_file()
                    arguments = ('map', 'models', file.path.rsplit('/', 1)[-1][:-3]) if has_map else ('map', 'scan')
                    print(render_advice(advice('models' if has_map else 'describe', project_command(project, *arguments))))
        return 0
    for file in files:
        print(f"===== {file.path} =====")
        print(file.content)
    return 0


def _request(ns: argparse.Namespace) -> int:
    from .map.mapfile import MapError
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
    from .map.impact_history import read_git_paths

    try:
        root = Path(ns.root).resolve()
        if ns.hook and not (root / '.flowguard').is_dir():
            return 0
        result = status.collect_status(root, read_git_paths=read_git_paths, version=__version__)
        session = status.agent_session()
        result['session'] = session or None
        print(json.dumps(result, ensure_ascii=False) if ns.json else status.render_status(result))
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
    from .map.mapfile import MapError

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
            result["next_queries"] = [project_command(root, "where", selector, *options) for selector in dict.fromkeys(selectors)]
            renderer = textrules
        else:
            result = derived.where(root, ns.name, view=ns.view)
            if "unexpanded_functions" in result:
                modules = result.get("modules", [])
                options = ([modules[0]["path"]] + (["--flow"] if ns.view == "flow" else [])) if modules else ["--arch"]
                result["next"] = advice("where", project_command(root, "where", *options, *(["--json"] if ns.json else [])))
            result["next_queries"] = []
            renderer = derived
        shown = renderer.project(result, all_rows=ns.all)
        if shown.get("omitted"):
            shown["next_queries"] = [*shown["next_queries"], every]
        output = renderer.render(shown, as_json=ns.json, all_rows=ns.all)
        if not ns.json and shown["next_queries"]:
            output += "\n" + "\n".join(render_advice(advice("where", command)) for command in shown["next_queries"])
        print(output)
        return 0
    except (OSError, ValueError, RuntimeError, MapError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


@quiet_broken_pipe
def main(argv: list[str] | None = None) -> int:
    safe_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(__doc__.strip())
        for verb, purpose in VERB_PURPOSE.items():
            print()
            print(f"{verb:<10}{purpose}")
            if verb == "map":
                print(
                    "usage: python -m flowguard map <command> ... (python -m flowguard map --help)"
                )
            else:
                print(_verb_parser(verb).format_usage().strip())
        return 0
    if args[0] in {"--version", "version"}:
        print(__version__)
        return 0
    verb, rest = args[0], args[1:]
    if verb not in {"map", "read", "where", "change", "release", "template", "target", "req", "status"}:
        print(f"unknown command {verb!r}; run 'python -m flowguard --help'", file=sys.stderr)
        return 2
    if verb != "status":
        from .map.impact_history import read_git_paths
        from .map.status import show_status_first
        show_status_first(rest, __version__, read_git_paths=read_git_paths)
    if verb == "map":
        return map_main(rest)
    if verb == "target":
        from .map.target import main as target_main

        return target_main(rest)
    parser = _verb_parser(verb)
    ns = parser.parse_args(rest)
    if hasattr(ns, "root"):
        from .map.common import project_root
        ns.root = str(project_root(ns.root))
    if verb == "where":
        if ns.at is not None and ns.view != "text":
            parser.error("--at requires --text")
        return _where(ns)
    if verb == 'status':
        return _status(ns)
    if verb == "req":
        return _request(ns)
    if verb == "read" and ns.mermaid and ns.find:
        parser.error("--mermaid cannot be used with --find")
    if verb == "read" and ns.target and ns.find:
        parser.error("--target cannot be used with --find")
    if (
        verb == "read"
        and ns.review
        and (ns.component or ns.find or ns.field or ns.mermaid or ns.target)
    ):
        parser.error("--review cannot be used with --component, --find, --mermaid or --target")
    if verb == "read" and ns.field and (ns.mermaid or ns.target):
        parser.error("--field cannot be used with --mermaid or --target")
    if verb == "template":
        return _template(ns)
    root = ["--root", ns.root]
    if verb == "read":
        project = Path(ns.root)
        if ns.field:
            return map_main([*root, "show", "--field", ns.field])
        if ns.find:
            return map_main([*root, "find", *ns.find])
        return map_main(
            [
                *root,
                "show",
                *(["--component", ns.component] if ns.component else []),
                *(["--mermaid"] if ns.mermaid else []),
                *(["--target"] if ns.target else []),
                *(["--review"] if ns.review else []),
            ]
        )
    if verb == "change":
        from .map.cli import cmd_change
        from .map.mapfile import MapError

        try:
            return cmd_change(Path(ns.root).resolve(), ns)
        except (MapError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    from .map.cli import cmd_verify
    from .map.mapfile import MapError

    ns.limit = 80
    try:
        return cmd_verify(Path(ns.root).resolve(), ns)
    except (MapError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if getattr(ns, "json", False):
            print_verdict("release", 2, [dict(level="error", code="runtime_error", subject="map")])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
