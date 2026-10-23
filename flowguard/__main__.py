"""python -m flowguard: daily verbs on top of the FlowGuard map.

  read      [--root R] [--component ID | --find WORDS...]   understand the software (business data read-only; disposable caches may update)
  change    [--root R] [--base REF] [FILES...]               after editing: check the map, list what to run
  release   [--root R]                                       release gate: strict check + lint errors + all models
  map       <command> ...                                    every map/proof command (python -m flowguard map --help)
  template  [--list | NAME [--write DIR] [--force]]          starter model files for one capability
  target    start "<goal>" | add <id> | check | promote | drop   plan a change as a target model, check the code against it, promote it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .map.cli import main as map_main
from .map.common import quiet_broken_pipe, safe_stdio


def _verb_parser(verb: str) -> argparse.ArgumentParser:
    if verb == "target":
        from .map.target import build_parser
        return build_parser()
    p = argparse.ArgumentParser(prog=f"python -m flowguard {verb}")
    if verb == "template":
        p.add_argument("name", nargs="?", help="template name (see --list)")
        p.add_argument("--list", action="store_true", help="list template names")
        p.add_argument("--write", metavar="DIR", help="write the files under DIR instead of printing them")
        p.add_argument("--force", action="store_true", help="overwrite existing files when writing")
        return p
    p.add_argument("--root", default=".")
    if verb == "read":
        group = p.add_mutually_exclusive_group()
        group.add_argument("--component", help="show one component in detail")
        group.add_argument("--find", nargs="+", metavar="WORD", help="which component owns this responsibility")
        p.add_argument("--mermaid", action="store_true", help="export the model tree (incompatible with --find)")
        p.add_argument("--target", action="store_true", help="show changes made by the target (incompatible with --find)")
    elif verb == "change":
        p.add_argument("--base", default="HEAD", help="git revision to diff against (default HEAD)")
        p.add_argument("files", nargs="*", help="changed files (default: from git)")
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
        "model-test": "model-test-alignment",
        "ui-flow": "ui-journey",
        "contract-exhaustion": "validator",
    }
    factory = factories.get(aliases.get(ns.name, ns.name))
    if factory is None:
        print(f"unknown template {ns.name!r}; run 'python -m flowguard template --list'", file=sys.stderr)
        return 2
    files = factory()
    if ns.write:
        from .templates import write_template_files

        try:
            written = write_template_files(ns.write, files, overwrite=ns.force)
        except FileExistsError as exc:
            print(f"{exc}; use --force to overwrite", file=sys.stderr)
            return 1
        for path in written:
            print(f"wrote {path}")
        for file in files:
            if file.path.startswith(".flowguard/models/") and file.path.count("/") == 2:
                print(f"next: replace every REPLACE_ME anchor and the example with your own code; set COMPONENTS "
                      f"(and PARENT if it refines another model) in {file.path}; then run: "
                      f"python -m flowguard map models {file.path.rsplit('/', 1)[-1][:-3]}")
        return 0
    for file in files:
        print(f"===== {file.path} =====")
        print(file.content)
    return 0


@quiet_broken_pipe
def main(argv: list[str] | None = None) -> int:
    safe_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(__doc__.strip())
        return 0
    if args[0] in {"--version", "version"}:
        print(__version__)
        return 0
    verb, rest = args[0], args[1:]
    if verb == "map":
        return map_main(rest)
    if verb == "target":
        from .map.target import main as target_main
        return target_main(rest)
    if verb not in {"read", "change", "release", "template", "target"}:
        print(f"unknown command {verb!r}; run 'python -m flowguard --help'", file=sys.stderr)
        return 2
    if any(flag in rest for flag in ("--request", "--contract", "--owner-current")):
        print("This 0.69 workflow interface retired in 0.70.0; see references/upgrade.md", file=sys.stderr)
        return 2
    parser = _verb_parser(verb)
    ns = parser.parse_args(rest)
    if verb == "read" and ns.mermaid and ns.find:
        parser.error("--mermaid cannot be used with --find")
    if verb == "read" and ns.target and ns.find:
        parser.error("--target cannot be used with --find")
    if verb == "template":
        return _template(ns)
    root = ["--root", ns.root]
    if verb == "read":
        project = Path(ns.root)
        legacy = (project / ".flowguard/project.toml").is_file() and not (project / ".flowguard/map.json").is_file()
        if legacy:
            print("FlowGuard 0.69 project detected; upgrade instructions: references/upgrade.md", file=sys.stderr)
            return 2
        if ns.find:
            return map_main([*root, "find", *ns.find])
        return map_main([*root, "show", *(["--component", ns.component] if ns.component else []),
                         *(["--mermaid"] if ns.mermaid else []), *(["--target"] if ns.target else [])])
    if verb == "change":
        from .map.cli import cmd_change
        from .map.mapfile import MapError
        try:
            return cmd_change(Path(ns.root).resolve(), ns)
        except (MapError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    return map_main([*root, "verify"])


if __name__ == "__main__":
    raise SystemExit(main())
