"""`check` and `show`: arguments, the output contract (design 7.2), exit codes and
`.flowguard/conflicts.json` (3.8, 7.3).

The caller never runs model code: it plans parts, takes the finished ones from the cache
and waits for the plan's worker at most `--wait` seconds (jobs.py). stdout line 1 is the
verdict; then each new conflict in full, each open conflict on one line, each model
warning on one line, each model error with its location, one reach line per model.
`--json` prints exactly one line instead. Progress goes to stderr only.

Exit codes: 0 clean and complete; 1 a conflict (new or open); 2 a model error, a usage
error, not a project, or an internal error; 3 UNKNOWN with no conflict; 4 RUNNING.
A model error decides 2 even when there are conflicts too: part of the check is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import diagram, jobs
from .checks import CONFLICT, ERROR_CLS, WARNING, Finding
from .explore import Bounds
from .model import natural_key
from .parts import ENGINE_DIGEST
from .project import (FLOW_DIR, PROG, ProjectError, conflict_entry, find_root, model_files,
                      overlap_views, read_conflicts, request_lines, resolve_models, write_conflicts)

EXIT_CLEAN, EXIT_CONFLICT, EXIT_ERROR, EXIT_UNKNOWN, EXIT_RUNNING = 0, 1, 2, 3, 4
DEFAULT_WAIT = 90.0              # inside the AI's 120 s tool timeout
DEFAULT_KEEP = 300.0


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def _seconds(text):
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more seconds")
    return value


def _states(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def parser(prog: str = PROG) -> argparse.ArgumentParser:
    top = _Parser(prog=prog, description="Flow models: check them, draw them.")
    verbs = top.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    check = verbs.add_parser("check", help="explore the flow models and run the prepared checks")
    check.add_argument("models", nargs="*", metavar="MODEL", help="model ids or files in .flowguard/flow/")
    check.add_argument("--wait", type=_seconds, default=DEFAULT_WAIT,
                       help=f"return after at most this many seconds (default {DEFAULT_WAIT:g})")
    check.add_argument("--full", action="store_true",
                       help="also mutate the models and verify renaming without reduction")
    check.add_argument("--json", action="store_true", help="print one JSON line")
    check.add_argument("--max-states", type=_states, default=Bounds().max_states)
    check.add_argument("--keep", type=_seconds, default=DEFAULT_KEEP,
                       help="how long work left RUNNING waits for a resume (seconds)")
    check.add_argument("--root", help="the project (default: the nearest directory with .flowguard/)")
    show = verbs.add_parser("show", help="draw the flowchart of the current change or conflict")
    show.add_argument("what", nargs="?", metavar="WHAT", help="a model id, model:object or a conflict id")
    show.add_argument("--before", metavar="REV")
    show.add_argument("--fields", metavar="F,..")
    show.add_argument("--object", metavar="O")
    show.add_argument("--focus", type=int, metavar="K")
    show.add_argument("--story", action="store_true")
    show.add_argument("--group", metavar="FIELD")
    show.add_argument("--max-boxes", type=int, default=12)
    show.add_argument("--max-arrows", type=int, default=20)
    show.add_argument("--max-states", type=_states, default=Bounds().max_states)
    show.add_argument("--wait", type=_seconds, default=DEFAULT_WAIT)
    show.add_argument("--keep", type=_seconds, default=DEFAULT_KEEP)
    show.add_argument("--json", action="store_true")
    show.add_argument("--root")
    return top


def main(argv=None, *, prog: str = PROG, out=None, err=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        args = parser(prog).parse_args(argv)
    except UsageError as e:
        early = _show_early if argv[:1] == ["show"] else _early
        return early(out, f"usage error: {e} (see {prog} --help)", EXIT_ERROR, "--json" in argv)
    if args.verb == "show":
        return show(args, argv, prog=prog, out=out, err=err)
    return check(args, argv, prog=prog, out=out, err=err)


def _early(out, line: str, code: int, as_json: bool) -> int:
    """A verdict before any model was looked at (usage, project, empty flow directory)."""
    if as_json:
        out.write(json.dumps({"verdict": line, "exit": code, "complete": code == EXIT_CLEAN, "conflicts": [],
                              "warnings": [], "errors": [], "unknown": [], "models": {}, "parts": [],
                              "declared_routes": [], "closed": [], "resume": None, "running": None},
                             ensure_ascii=False, separators=(",", ":")) + "\n")
    else:
        out.write(line + "\n")
    out.flush()
    return code


def show(args, argv, *, prog: str = PROG, out=None, err=None) -> int:
    """`show` draws through the `picture` part (diagram.show_main) with the job runner, so
    it keeps the wait contract of `check`: the parts it needs that are not finished
    within --wait leave it RUNNING with the command that resumes."""
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        root = find_root(Path(args.root) if args.root else Path.cwd())
    except ProjectError as e:
        return _show_early(out, str(e), EXIT_ERROR, args.json)
    runner = jobs.Runner(root, wait=args.wait, keep=args.keep, progress=_Progress(err, "show"))
    try:
        code, text = diagram.show_main(root, args, runner)
    except jobs.Running as running:
        resume = f"{prog} {shlex.join(argv)}"
        return _show_early(out, running_line(running.outcome, resume), EXIT_RUNNING, args.json, resume=resume)
    except jobs.Failed as e:
        return _show_early(out, f"internal error: {e}", EXIT_ERROR, args.json)
    out.write(text)
    out.flush()
    return code


def _show_early(out, line: str, code: int, as_json: bool, resume: str | None = None) -> int:
    """A show that draws nothing: usage, project, RUNNING, internal error."""
    if as_json:
        out.write(json.dumps({"exit": code, "message": line, "pictures": [], "more": [], "resume": resume},
                             ensure_ascii=False, sort_keys=True) + "\n")
    else:
        out.write(line + "\n")
    out.flush()
    return code


# ---------------------------------------------------------------------- progress (stderr)
class _Progress:
    """At most one line every 5 s, and only after the first 2 s."""

    def __init__(self, stream, verb: str = "check"):
        self.stream = stream
        self.verb = verb
        self.next = time.monotonic() + 2.0

    def __call__(self, done: int, total: int, current: dict | None) -> None:
        now = time.monotonic()
        if now < self.next:
            return
        self.next = now + 5.0
        self.stream.write(f"{self.verb}: {done} of {total} parts done{_current_text(current, '; ')}\n")
        self.stream.flush()


def _current_text(current: dict | None, lead: str) -> str:
    if not current:
        return ""
    if current["kind"] == "core":
        states = current.get("states") or 0
        return f"{lead}exploring {current['model']}" + (f" ({states:,} states)" if states else "")
    return f"{lead}running {current['kind']} of {current['model']}"


# ---------------------------------------------------------------------- check
def check(args, argv, *, prog: str = PROG, out=None, err=None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        root = find_root(Path(args.root) if args.root else Path.cwd())
        paths = resolve_models(root, args.models) if args.models else model_files(root)
    except ProjectError as e:
        return _early(out, str(e), EXIT_ERROR, args.json)
    if not paths:
        return _early(out, f"no flow models in {FLOW_DIR.as_posix()}/", EXIT_CLEAN, args.json)
    previous = read_conflicts(root)
    planned = jobs.plan(root, paths, full=args.full, max_states=args.max_states, stored=previous)
    outcome = jobs.run(root, planned, wait=args.wait, keep=args.keep, progress=_Progress(err))
    resume = f"{prog} {shlex.join(argv)}"
    if outcome.failure is not None:
        return _early(out, f"internal error: {outcome.failure}", EXIT_ERROR, args.json)
    result = assemble(root, outcome, previous)
    if outcome.finished:
        write_conflicts(root, conflicts_data(root, result, previous))
    lines, data = render(root, result, resume)
    if args.json:
        out.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    else:
        out.write("\n".join(lines) + "\n")
    out.flush()
    return data["exit"]


# ---------------------------------------------------------------------- assembling
@dataclass
class ModelView:
    id: str
    parts: list = field(default_factory=list)      # (Planned, PartResult | None, cached, worker)

    @property
    def finished(self) -> bool:
        return all(r is not None for _, r, _, _ in self.parts)

    @property
    def complete(self) -> bool:
        return self.finished and all(r.complete for _, r, _, _ in self.parts)

    @property
    def explored(self) -> bool:
        """A complete exploration of the model as it is: the only run that closes a conflict
        it no longer finds (a capped run, or a model that does not load, closes none)."""
        core = self.result("core")
        return self.complete and core is not None and core.info["loaded"]

    def result(self, kind: str):
        for p, r, _, _ in self.parts:
            if p.spec.kind == kind:
                return r
        return None

    def writes(self) -> list[str]:
        return [w for _, r, _, _ in self.parts if r is not None for w in r.writes]


@dataclass
class Assembled:
    outcome: object
    models: dict                                  # id -> ModelView, in plan order
    conflicts: list
    warnings: list
    errors: list
    new: set
    max_states: int
    closed: list = field(default_factory=list)     # (entry, why): a stored path that no longer reproduces


def assemble(root, outcome, previous: dict | None) -> Assembled:
    models = {}
    for item, r, c, w in zip(outcome.planned, outcome.results, outcome.cached, outcome.workers):
        models.setdefault(item.spec.model, ModelView(item.spec.model)).parts.append((item, r, c, w))
    findings, seen = [], set()
    for view in models.values():
        for _, r, _, _ in view.parts:
            for d in (r.findings if r is not None else []):
                f = Finding.from_json(d)
                if f.id not in seen:
                    seen.add(f.id)
                    findings.append(f)
    views = []
    for view in models.values():
        core = view.result("core")
        if core is not None and core.info["loaded"] and core.info["covers"]:
            views.append((view.id, core.info["families"], core.info["covers"]))
    findings += [f for f in overlap_views(views) if f.id not in seen]
    before = {c["id"] for c in (previous or {}).get("conflicts", [])}
    conflicts = [f for f in findings if f.cls == CONFLICT]
    kept, closed = _kept(models, previous, {f.id for f in conflicts})
    conflicts += kept
    max_states = dict(outcome.planned[0].spec.options)["max_states"]
    return Assembled(outcome, models, conflicts, [f for f in findings if f.cls == WARNING],
                     [f for f in findings if f.cls == ERROR_CLS], {f.id for f in conflicts if f.id not in before},
                     max_states, closed)


def _kept(models: dict, previous: dict | None, found: set) -> tuple[list, list]:
    """The stored conflicts a check of their model did not find again, when that check
    cannot close them (design M6): it was capped, or the model did not load. Each stays
    open unless the replay of its stored shrunk path no longer reproduces it (closed)."""
    kept, closed = [], []
    for c in (previous or {}).get("conflicts", []):
        view = models.get(c["model"])
        if c["id"] in found or view is None or not view.finished or view.explored:
            continue
        replay = view.result("replay")
        outcome, why = (replay.info["replays"].get(c["id"]) if replay is not None else None) or (
            None, "no stored path to replay")
        if outcome == "gone":
            closed.append((c, why))
            continue
        core = view.result("core")
        scope = "this check is capped" if core is not None and core.info["loaded"] else "the model does not load"
        if outcome == "reproduces":
            reason = f"{why}; {scope}"
        elif why == scope:
            reason = f"proven by an earlier complete check; {scope}"
        else:
            reason = f"proven by an earlier complete check ({why}); {scope}"
        kept.append(Finding(c["kind"], CONFLICT, c["model"], c["subject"], c["text"], (), tuple(c["sources"]),
                            tuple(c.get("path", [])), "", {"kept": reason, "entry": c}, None, c["id"]))
    return kept, closed


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _undecided(result: Assembled, capped: list[str]) -> list[str]:
    """The checks a capped search could not decide: check kinds by name, rules counted."""
    words, rules = [], 0
    for mid in capped:
        for _, r, _, _ in result.models[mid].parts:
            for label in r.info.get("unknown", []):
                if "'" in label:
                    rules += 1
                elif label not in words:
                    words.append(label)
    return words + ([_plural(rules, "rule")] if rules else [])


def running_line(o, resume: str) -> str:
    """The first line of a call that returns before every part is done."""
    done = [p.label for p, r in zip(o.planned, o.results) if r is not None]
    line = f"RUNNING: {len(done)} of {len(o.planned)} parts done" + (f" ({', '.join(done)})" if done else "")
    return line + _current_text(o.current, "; still ") + f"; resume with: {resume}"


def verdict(result: Assembled, resume: str) -> tuple[str, int]:
    o = result.outcome
    if not o.finished:
        return running_line(o, resume), EXIT_RUNNING
    n_new = len([f for f in result.conflicts if f.id in result.new])
    n_open = len(result.conflicts) - n_new
    capped = [m for m, v in result.models.items() if not v.complete]
    head = []
    if n_new and n_open:
        head.append(f"{_plural(n_new, 'new conflict')}, {n_open} open")
    elif n_new:
        head.append(_plural(n_new, "new conflict"))
    elif n_open:
        head.append(_plural(n_open, "open conflict"))
    elif capped:
        head.append("no conflict found")
    if result.errors:
        head.append(_plural(len(result.errors), "model error"))
    if capped:
        tail = f"UNKNOWN: {', '.join(capped)} capped at {result.max_states:,} states"
        if not result.conflicts:
            tail += f" ({', '.join(_undecided(result, capped))} undecided)"
    elif not head:
        tail = "clean, complete" + (f"; {_plural(len(result.warnings), 'model warning')}" if result.warnings else "")
    else:
        tail = "complete"
    line = "; ".join(head + [tail])
    if result.errors:
        code = EXIT_ERROR
    elif result.conflicts:
        code = EXIT_CONFLICT
    elif capped:
        code = EXIT_UNKNOWN
    else:
        code = EXIT_CLEAN
    return line, code


# ---------------------------------------------------------------------- rendering
def _objects(result: Assembled, f: Finding) -> str:
    if not f.objects:
        return ""
    core = result.models[f.model].result("core") if f.model in result.models else None
    kinds = core.info.get("objects", {}) if core is not None and core.info["loaded"] else {}
    for kind, ids in kinds.items():
        if set(f.objects) <= set(ids):
            return f" ({kind}s {', '.join(f.objects)})"
    return f" ({', '.join(f.objects)})"


def _explanation(f: Finding) -> str:
    """The one-setting explanation of a NEVER REACHED item ("" when not explained)."""
    how = f.detail.get("explained")
    if f.kind != "NEVER REACHED" or how is None:
        return ""
    capped = f.detail.get("capped") or []
    text = f"reached only with {', '.join(how)}" if how else "no one-setting change reaches it"
    if capped:
        text += f"; UNKNOWN with {', '.join(capped)} (capped)"
    return text


def picture(result: Assembled, f: Finding) -> str | None:
    """The picture written for a conflict: `<model>-<fingerprint>.svg` among its parts'
    writes, or its Mermaid text `.mmd` when the picture file could not be written."""
    written = {Path(w).name: w for w in (result.models[f.model].writes() if f.model in result.models else [])}
    stem = f"{f.model}-{f.id[2:]}"
    return written.get(f"{stem}.svg") or written.get(f"{stem}.mmd")


def _steps(n: int) -> str:
    return _plural(n, "step")


def _source(source) -> str:
    return source or "the AI's own"


def _stuck_lines(detail: dict) -> list[str]:
    """Every call that would change the stuck object and refuses where it is stuck, the same
    later where a consequence sets in, then the step that entered it."""
    out = [f"  {r['call']} refused: {r['reason']!r} ({_source(r['source'])})" for r in detail.get("refused", [])]
    out += [f"  later, where {r['at']}: {r['call']} refused: {r['reason']!r} ({_source(r['source'])})"
            for r in detail.get("later", [])]
    entered = detail.get("entered")
    if entered is None:
        out.append("  stuck from the start")
    else:
        out.append(f"  entered by {entered['call']} ({', '.join(entered['sources']) or _source(None)})")
    return out


def _consequences(detail: dict) -> str | None:
    shown = detail.get("shown_consequences", detail.get("consequences") or [])
    folded = (detail.get("folded") or {}).get("count", 0)
    fields = ", ".join((detail.get("folded") or {}).get("fields", []))
    if not shown and not folded:
        return None
    if not shown:
        return f"  then also stuck: {_plural(folded, 'counter value')} ({fields}), folded"
    return "  then also stuck: " + "; ".join(shown) + (
        f" ({_plural(folded, 'counter value')} folded: {fields})" if folded else "")


def full_block(root, result: Assembled, f: Finding) -> list[str]:
    lines = [f"NEW {f.kind} {f.model}: {f.text}{_objects(result, f)}   [{f.id}]"]
    if f.kind == "STUCK":
        lines += _stuck_lines(f.detail)
    lines.append("  requests: " + " | ".join(f'{rid} "{words}"' if rid else words
                                             for rid, words in request_lines(root, f.sources)))
    if f.state:
        lines.append(f"  state: {f.state}")
    if f.path:
        lines.append(f"  path ({_steps(len(f.path))}): " + " ; ".join(f.path))
    if f.detail.get("example"):                       # a second route: one change both make
        lines.append(f"  for example: {f.detail['example']}")
    for r in f.detail.get("refusals") or []:          # a fallback: where each one is the route
        lines.append(f"  where {r['where']} does it, {r['refuses']} refuses: {r['reason']!r} "
                     f"({r['states']} of {r['of']} states)")
    consequences = _consequences(f.detail) if f.kind == "STUCK" else None
    if consequences:
        lines.append(consequences)
    explained = _explanation(f)
    if explained:
        lines.append(f"  {explained}")
    for e in f.detail.get("explanation_errors") or []:
        lines.append(f"  model error in a setting variant: {e}")
    for note in f.detail.get("notes") or []:
        lines.append(f"  note: {note}")
    pic = picture(result, f)
    if pic is not None:
        lines.append(f"  picture: {pic}" + (" (Mermaid text: the picture file was not written)"
                                            if pic.endswith(".mmd") else ""))
    lines += cause_lines(result, f)
    return lines


def cause_lines(result: Assembled, f: Finding) -> list[str]:
    """With --full: each requested guard (one with its own source=) whose drop or widening
    removes this conflict: what the conflict rests on, said as its cause (G5). Every change
    that removes it is in --json (the mutate part's causes)."""
    view = result.models.get(f.model)
    mutate = view.result("mutate") if view is not None else None
    causes = (mutate.info.get("causes", {}) if mutate is not None else {}).get(f.id, [])
    return [f"  cause (check --full): {c['cause']} this conflict does not occur" for c in causes if c["requested"]]


def _one_line(result: Assembled, f: Finding, lead: str) -> str:
    return f"{lead} {f.kind} {f.model}: {f.text}{_objects(result, f)}   [{f.id}]"


def _warning_line(result: Assembled, f: Finding) -> str:
    explained = _explanation(f)
    return f"model warning {f.model}: {f.text}{_objects(result, f)}" + (f" ({explained})" if explained else "")


def _error_lines(f: Finding) -> list[str]:
    lines = [f"MODEL ERROR {f.model}: {f.subject}"]
    if f.path:
        lines.append(f"  path ({_steps(len(f.path))}): " + " ; ".join(f.path))
    if f.state:
        lines.append(f"  state: {f.state}")
    return lines


def declared_lines(root, result: Assembled) -> list[str]:
    """One line per second route a model keeps with m.second_route (M15): the pair, its
    request with its first line, what it keeps, and why."""
    out = []
    for view in result.models.values():
        routes = view.result("routes")
        for d in (routes.info.get("declared_routes", []) if routes is not None else []):
            [(rid, words)] = request_lines(root, [d["source"]])
            keeps = f"keeps {', '.join(d['keeps'])}" if d["keeps"] else "keeps nothing now"
            out.append(f"declared second route {view.id}: {' / '.join(d['actions'])} ({rid} \"{words}\"; {keeps}): "
                       f"{d['why']}")
    return out


def reach(view: ModelView) -> str | None:
    """The model's reach line (3.9), with the unreduced verification under --full."""
    core = view.result("core")
    if core is None:
        return None
    if not core.info["loaded"]:
        return f"{view.id}: not explored (model error)"
    line = core.info["reach_line"]
    sym = core.info.get("symmetry")
    if sym is not None and core.info["reach"]["symmetry"]:
        line += f"; {sym['text']}"
    return line


def render(root, result: Assembled, resume: str) -> tuple[list[str], dict]:
    line, code = verdict(result, resume)
    new = [f for f in result.conflicts if f.id in result.new]
    open_ = [f for f in result.conflicts if f.id not in result.new]
    lines = [line]
    for f in new:
        lines += full_block(root, result, f)
    for f in open_:
        lines.append(_one_line(result, f, "OPEN") + (f" (kept: {f.detail['kept']})" if "kept" in f.detail else ""))
        lines += cause_lines(result, f)
    lines += [f"closed {c['id']} {c['kind']} {c['model']}: its stored path no longer reproduces it ({why})"
              for c, why in result.closed]
    lines += [_warning_line(result, f) for f in result.warnings]
    for f in result.errors:
        lines += _error_lines(f)
    lines += declared_lines(root, result)
    reaches = [reach(v) for v in result.models.values()]
    lines += [r for r in reaches if r is not None]
    o = result.outcome
    models = {}
    for mid, view in result.models.items():
        core = view.result("core")
        info = core.info if core is not None else {}
        models[mid] = {"finished": view.finished, "complete": view.complete if view.finished else None,
                       "states": info["reach"]["states"] if info.get("loaded") else None,
                       "reach": reach(view),
                       "undecided": _undecided(result, [mid]) if view.finished and not view.complete else [],
                       "symmetry": info.get("symmetry")}
    data = {
        "verdict": line, "exit": code, "complete": o.finished and all(v.complete for v in result.models.values()),
        "conflicts": [dict(f.to_json(), new=f.id in result.new, requests=request_lines(root, f.sources),
                           picture=picture(result, f)) for f in result.conflicts],
        "warnings": [f.to_json() for f in result.warnings],
        "errors": [f.to_json() for f in result.errors],
        "unknown": [m for m, v in result.models.items() if v.finished and not v.complete],
        "models": models,
        "parts": [{"kind": p.spec.kind, "model": p.spec.model, "digest": r.digest if r is not None else None,
                   "cached": c, "worker": w} for p, r, c, w in zip(o.planned, o.results, o.cached, o.workers)],
        "declared_routes": [d for v in result.models.values() for _, r, _, _ in v.parts if r is not None
                            for d in r.info.get("declared_routes", [])],
        "closed": [{"id": c["id"], "kind": c["kind"], "model": c["model"], "why": why} for c, why in result.closed],
        "resume": None if o.finished else resume,
        "running": None if o.finished else {"done": sum(r is not None for r in o.results), "total": len(o.planned),
                                            "current": o.current, "worker": o.worker, "job": o.job},
    }
    return lines, data


# ---------------------------------------------------------------------- conflicts.json
def conflicts_data(root, result: Assembled, previous: dict | None) -> dict:
    """This computation's models replace their entries; the other models that still have
    a file keep theirs, so checking one model does not drop the others' open conflicts."""
    existing = {p.stem for p in model_files(root)}
    previous = previous or {}
    kept = {m: v for m, v in previous.get("models", {}).items() if m in existing and m not in result.models}
    entries = [c for c in previous.get("conflicts", []) if c["model"] in kept]
    entries += [conflict_entry(f) for f in result.conflicts]
    models = dict(kept)
    for mid, view in result.models.items():
        models[mid] = {"complete": view.complete, "parts": sorted(r.digest for _, r, _, _ in view.parts),
                       "warnings": len([f for f in result.warnings if f.model == mid])}
    digests = sorted(d for v in models.values() for d in v["parts"])
    return {"engine": ENGINE_DIGEST,
            "tree": hashlib.sha256(json.dumps(digests).encode("utf-8")).hexdigest(),
            "complete": all(v["complete"] for v in models.values()),
            "conflicts": entries,
            "unknown": sorted((m for m, v in models.items() if not v["complete"]), key=natural_key),
            "warnings": sum(v["warnings"] for v in models.values()),
            "models": dict(sorted(models.items()))}


RELEASE_WAIT = 3600                # the release check may run long (design 7.6); the in-loop default never does


def release(root, *, out=None, err=None) -> bool:
    """The flow-model part of the legacy `release` (design 7.6, wired by the move-in): check
    every model with --full (the deliberate-breakage mutants and the unreduced symmetry
    check) and the release wait. True when the release may go on: a conflict or a model
    error stops it (UNKNOWN does not); work still RUNNING after the wait stops it too, since
    nothing was decided."""
    code = main(["check", "--full", "--wait", str(RELEASE_WAIT), "--root", str(root)], out=out, err=err)
    return code in (EXIT_CLEAN, EXIT_UNKNOWN)


def status_lines(root) -> list[str]:
    """For the legacy `status` (move-in, design 7.6): open conflicts of the flow models
    from the last final check, and what blocks a commit."""
    data = read_conflicts(root)
    if data is None:
        return ["flow models: no check recorded (run check)"]
    conflicts = data["conflicts"]
    unknown = data["unknown"]
    if conflicts:
        ids = ", ".join(c["id"] for c in conflicts)
        line = f"flow models: {_plural(len(conflicts), 'open conflict')} ({ids}); a commit is blocked until fixed"
    elif unknown:
        line = "flow models: no conflict found"
    else:
        line = "flow models: clean"
    if unknown:
        line += (f"; capped: {', '.join(unknown)} (what a capped search could not decide is UNKNOWN; "
                 f"that alone does not block)")
    return [line]
