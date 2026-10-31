"""Standalone bootstrap for the unreleased behavior pilot."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard.behave",
        description="Unreleased behavior pilot.",
    )
    verbs = parser.add_subparsers(dest="command")
    init = verbs.add_parser("init", help="derive a skeleton, construct its root and write source pins")
    init.add_argument("--root", default=".", help="project source directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if (sys.version_info < (3, 12) and arguments
            and arguments not in (["-h"], ["--help"])):
        parser.error("the FlowGuard pilot needs Python 3.12 or newer")
    options = parser.parse_args(arguments)
    if options.command is None:
        parser.print_help()
        return 0
    from .project import replay
    from .skeleton import derive, render, write_pins

    try:
        spec = derive(options.root)
        observed = replay(spec, [])
        spec["shipped"] = observed["defaults"]
        path = write_pins(options.root, spec)
    except (ValueError, OSError) as exc:
        print("ERROR " + str(exc), file=sys.stderr)
        return 1
    print(render(spec))
    print("pins: " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
