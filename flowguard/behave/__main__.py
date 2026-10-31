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
    audit = verbs.add_parser("audit", help="explore bounded real worlds and state which checks remain unimplemented")
    audit.add_argument("--root", default=".")
    audit.add_argument("--world", action="append", dest="worlds")
    audit.add_argument("--seeds", default="0,1")
    audit.add_argument("--steps", type=int, default=64)
    audit.add_argument("--node-cap", type=int, default=1000)
    audit.add_argument("--alphabet-cap", type=int, default=1000)
    audit.add_argument("--json", action="store_true")
    why = verbs.add_parser("why", help="reprove a stored witness against current code")
    why.add_argument("identifier")
    why.add_argument("--root", default=".")
    why.add_argument("--json", action="store_true")
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
    if options.command in {"audit", "why"}:
        try:
            if options.command == "audit":
                from .engine import audit
                from .report import render
                seeds = tuple(int(value) for value in options.seeds.split(","))
                if not seeds:
                    raise ValueError("at least one seed is required")
                result = audit(options.root, worlds=options.worlds, seeds=seeds, steps=options.steps,
                               node_cap=options.node_cap, alphabet_cap=options.alphabet_cap)
                print(render(result, as_json=options.json))
                return 0
            from .why import why
            import json
            result = why(options.root, options.identifier)
            payload = {key: value for key, value in result.items() if key not in {"proof", "identity"}}
            payload["verdict"] = "UNCHECKED"
            if options.json:
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            else:
                print("UNCHECKED witness " + result["state"] + ": " + options.identifier)
                if result.get("matched"):
                    print(json.dumps(result["semantic"], ensure_ascii=False, sort_keys=True))
                elif result.get("reason"):
                    print(result["reason"])
            return 1 if result["state"] in {"engine-defect", "unchecked"} else 0
        except (ValueError, OSError) as exc:
            print("UNCHECKED " + str(exc), file=sys.stderr)
            return 1
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
