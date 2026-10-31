"""Standalone bootstrap for the unreleased behavior pilot."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m flowguard.behave",
        description="Unreleased behavior pilot. No behavior commands are available yet.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if (sys.version_info < (3, 12) and arguments
            and arguments not in (["-h"], ["--help"])):
        parser.error("the FlowGuard pilot needs Python 3.12 or newer")
    parser.parse_args(arguments)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
