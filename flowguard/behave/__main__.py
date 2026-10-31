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
    audit.add_argument("--base", help="compare against an existing source revision")
    audit.add_argument("--world", action="append", dest="worlds")
    audit.add_argument("--seeds", help="comma-separated fixed seeds; otherwise use the world correction or 0,1")
    audit.add_argument("--steps", type=int, help="successful-step budget; default 64 unless corrected")
    audit.add_argument("--node-cap", type=int, help="node budget; default 1000 unless corrected")
    audit.add_argument("--alphabet-cap", type=int, help="action-domain budget; default 1000 unless corrected")
    audit.add_argument("--json", action="store_true")
    why = verbs.add_parser("why", help="reprove a stored witness against current code")
    why.add_argument("identifier", nargs="?")
    views = why.add_mutually_exclusive_group()
    views.add_argument("--coverage", action="store_true", help="show matching recorded audit coverage without exploring")
    views.add_argument("--defects", action="store_true", help="show matching recorded proof failures")
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
    if options.command == "audit":
        try:
            seeds = tuple(int(value) for value in options.seeds.split(",")) if options.seeds is not None else None
        except ValueError:
            parser.error("--seeds needs comma-separated integers")
        for name in ("steps", "node_cap", "alphabet_cap"):
            value = getattr(options, name)
            if value is not None and value < 1:
                parser.error("--" + name.replace("_", "-") + " must be positive")
    if options.command == "why" and (bool(options.identifier) == bool(options.coverage or options.defects)):
        parser.error("give either a finding id, --coverage or --defects")
    if options.command in {"audit", "why"}:
        try:
            if options.command == "audit":
                from .engine import audit
                from .report import render
                result = audit(options.root, worlds=options.worlds, seeds=seeds, steps=options.steps,
                               node_cap=options.node_cap, alphabet_cap=options.alphabet_cap, base=options.base)
                print(render(result, as_json=options.json))
                return 0
            from .why import why
            import json
            result = why(options.root, options.identifier, coverage=options.coverage, defects=options.defects)
            payload = {key: value for key, value in result.items() if key not in {"proof", "identity"}}
            payload["verdict"] = "BLOCKED" if result.get("matched") else "UNCHECKED"
            payload["word"] = payload["verdict"]
            if options.json:
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            else:
                print(payload["word"] + " " + result["state"] + (": " + options.identifier if options.identifier else " audit facts"))
                if "coverage" in result:
                    for name, counts in result["coverage"].get("modules", {}).items():
                        print(name + ": " + str(counts[0]) + "/" + str(counts[1]) + " functions")
                    for path, line in result["coverage"].get("unhit_lines", []):
                        print("changed line not run: " + path + ":" + str(line))
                    for entry in result["coverage"].get("front_doors", []):
                        print("unrecognised: " + entry)
                if "engine_defects" in result:
                    print("engine defect: " + str(len(result["engine_defects"])) + " items did not replay")
                    for defect in result["engine_defects"]:
                        print(str(defect.get("id", "finding")) + ": " + str(defect.get("reason", defect.get("state"))))
                for index, row in enumerate(result.get("trace", []), 1):
                    call = row["call"]
                    text = str(index) + ". " + call.get("name", call.get("construct", "call")) + "(" + ", ".join(map(repr, call.get("args", []))) + ") -> " + row["outcome"]
                    if row.get("exception"):
                        text += " " + repr(row["exception"]["message"])
                    print(text)
                if result.get("matched"):
                    print(result["label"] + ": " + repr(result["semantic"]))
                    if result.get("origin"):
                        print("origin: " + result["origin"])
                    for name, value in result.get("details", {}).items():
                        print(name + ": " + repr(value))
                    print("replayed now: still fails at step " + str(len(result.get("trace", []))))
                elif result.get("state") == "no-longer-reproduces":
                    print("replayed now: does not reproduce on this tree")
                if result.get("reason"):
                    print(result["reason"])
            return 1 if result["state"] in {"engine-defect", "unchecked"} else 0
        except ValueError as exc:
            parser.error(str(exc))
        except OSError as exc:
            print("UNCHECKED " + str(exc), file=sys.stderr)
            return 1
    from .project import UnsupportedWorld, replay
    from .skeleton import NoSkeleton, derive, fallback_facts, render, render_fallback, write_pins

    try:
        spec = derive(options.root)
        observed = replay(spec, [])
        spec["shipped"] = observed["defaults"]
        path = write_pins(options.root, spec)
    except NoSkeleton as exc:
        print(render_fallback(exc.facts))
        return 0
    except UnsupportedWorld as exc:
        print(render_fallback(fallback_facts(options.root, str(exc))))
        return 0
    except (ValueError, OSError) as exc:
        print("ERROR " + str(exc), file=sys.stderr)
        return 1
    print(render(spec))
    print("pins: " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
