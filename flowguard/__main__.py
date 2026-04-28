"""Thin command wrappers for public flowguard utilities."""

from __future__ import annotations

import argparse
from typing import Callable

from .schema import SCHEMA_VERSION


def _run_schema_version() -> int:
    print(SCHEMA_VERSION)
    return 0


def _run_adoption_template() -> int:
    from .templates import ADOPTION_LOG_TEMPLATE

    print(ADOPTION_LOG_TEMPLATE)
    return 0


COMMANDS: dict[str, Callable[[], int]] = {
    "adoption-template": _run_adoption_template,
    "schema-version": _run_schema_version,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flowguard",
        description="Run public flowguard utility commands.",
    )
    parser.add_argument("command", choices=tuple(COMMANDS))
    args = parser.parse_args(argv)
    return COMMANDS[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
