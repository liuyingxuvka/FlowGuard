"""`check` and `show`: arguments, the output contract (design 7.2), exit codes and
`.flowguard/conflicts.json` (3.8, 7.3).

The caller never runs model code: it plans parts, takes the finished ones from the cache
and waits for the plan's worker at most `--wait` seconds (jobs.py). stdout line 1 is the
verdict; then each new conflict in full, each open conflict on one line, each model
warning on one line, each model error with its location, one reach line per model.
`--json` prints exactly one line instead. Progress goes to stderr only.

Exit codes: 0 clean and complete; 1 a conflict (new or open); 2 a model error, a usage
error, not a project, an unreadable conflicts.json, or an internal error (each one line, never
a traceback); 3 UNKNOWN with no conflict; 4 RUNNING.
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
from .checks import CONFLICT, ERROR_CLS, GONE, REPLAYED, WARNING, Finding, explanation_text
from .explore import Bounds
from .model import natural_key
from .parts import ENGINE_DIGEST
from .project import (FLOW_DIR, PROG, ProjectError, conflict_entry, find_root, model_files,
                      overlap_views, read_conflicts, request_lines, resolve_models, unstored_sources,
                      write_conflicts)

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


VERBS = {"check": "explore the flow models and run the prepared checks",
         "show": "draw the flowchart of the current change or conflict"}


def _check_arguments(check: argparse.ArgumentParser) -> None:
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


def _show_arguments(show: argparse.ArgumentParser) -> None:
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


_ARGUMENTS = {"check": _check_arguments, "show": _show_arguments}


def parser(prog: str = PROG) -> argparse.ArgumentParser:
    top = _Parser(prog=prog, description="Flow models: check them, draw them.")
    verbs = top.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    for verb, purpose in VERBS.items():
        _ARGUMENTS[verb](verbs.add_parser(verb, help=purpose))
    return top


def verb_parser(verb: str, prog: str = PROG) -> argparse.ArgumentParser:
    """One verb's parser on its own, for the usage lines of `python -m flowguard --help`."""
    one = _Parser(prog=f"{prog} {verb}", description=VERBS[verb])
    _ARGUMENTS[verb](one)
    return one


class InternalError(Exception):
    """The engine itself failed (a worker that failed, a bug): exit 2, never 1."""


def internal_text(e: BaseException) -> str:
    """`internal error: <type>: <message> (<file>:<line>)`: one line with the place where it
    was raised (relative to the directory holding `flowguard/` when it is inside it)."""
    if isinstance(e, InternalError):
        return f"internal error: {e}"
    tb = e.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    where = ""
    if tb is not None:
        path = Path(tb.tb_frame.f_code.co_filename)
        try:
            path = path.resolve().relative_to(Path(__file__).resolve().parents[2])
        except ValueError:
            path = Path(path.name)
        where = f" ({path.as_posix()}:{tb.tb_lineno})"
    return f"internal error: {type(e).__name__}: {e}{where}"


def main(argv=None, *, prog: str = PROG, out=None, err=None) -> int:
    """Exit 2 for a project problem (not a project, an unreadable conflicts.json) and for any
    internal error, each as one line: exit 1 means a conflict and nothing else."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    err = err or sys.stderr
    early = _show_early if argv[:1] == ["show"] else _early
    try:
        args = parser(prog).parse_args(argv)
    except UsageError as e:
        return early(out, f"usage error: {e} (see {prog} --help)", EXIT_ERROR, "--json" in argv)
    try:
        if args.verb == "show":
            return show(args, argv, prog=prog, out=out, err=err)
        return check(args, argv, prog=prog, out=out, err=err)
    except ProjectError as e:
        return early(out, str(e), EXIT_ERROR, args.json)
    except BrokenPipeError:
        raise                                    # a closed stdout ends the command quietly (quiet_broken_pipe)
    except Exception as e:                       # noqa: BLE001 - one line and exit 2, never a traceback and 1
        return early(out, internal_text(e), EXIT_ERROR, args.json)


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
    root = find_root(Path(args.root) if args.root else Path.cwd())     # ProjectError: main says it
    read_conflicts(root)                         # an unreadable record stops show before any work
    runner = jobs.Runner(root, wait=args.wait, keep=args.keep, progress=_Progress(err, "show"))
    try:
        code, text = diagram.show_main(root, args, runner)
    except jobs.Running as running:
        resume = f"{prog} {shlex.join(argv)}"
        return _show_early(out, running_line(running.outcome, resume), EXIT_RUNNING, args.json, resume=resume)
    except jobs.Failed as e:
        raise InternalError(str(e)) from e
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
    """What the worker is on: the search with its states, then the phase of the work after it
    (finding what gets stuck, explaining with one-setting changes, verifying the renaming,
    drawing), so a line that repeats the same states still says it moves on."""
    if not current:
        return ""
    states = current.get("states") or 0
    phase = current.get("phase")
    if current["kind"] == "core":
        if phase:
            return f"{lead}{phase} in {current['model']}" + (f" ({states:,} states explored)" if states else "")
        return f"{lead}exploring {current['model']}" + (f" ({states:,} states)" if states else "")
    text = f"{lead}running {current['kind']} of {current['model']}"
    if current.get("mutant"):
        total = current.get("mutants")
        text += f" (deliberate breakage {current['mutant']}" + (f" of {total}" if total else "") + ")"
    return text + (f": {phase}" if phase else "")


# ---------------------------------------------------------------------- check
def check(args, argv, *, prog: str = PROG, out=None, err=None) -> int:
    """A project problem raises ProjectError and an engine failure InternalError (main turns
    either into one line and exit 2; release stops on them)."""
    out = out or sys.stdout
    err = err or sys.stderr
    root = find_root(Path(args.root) if args.root else Path.cwd())
    paths = resolve_models(root, args.models) if args.models else model_files(root)
    previous = read_conflicts(root)
    if not paths and not (previous or {}).get("conflicts"):     # a deleted model's conflicts stay (below)
        return _early(out, f"no flow models in {FLOW_DIR.as_posix()}/", EXIT_CLEAN, args.json)
    planned = jobs.plan(root, paths, full=args.full, max_states=args.max_states, stored=previous)
    outcome = jobs.run(root, planned, wait=args.wait, keep=args.keep, progress=_Progress(err))
    resume = f"{prog} {shlex.join(argv)}"
    if outcome.failure is not None:
        raise InternalError(str(outcome.failure))
    result = assemble(root, outcome, previous, max_states=args.max_states)
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
    def loaded(self) -> bool:
        core = self.result("core")
        return core is not None and core.info["loaded"]

    @property
    def complete(self) -> bool:
        """Every part finished on a complete search of a model that loaded (a model that does
        not load was not explored, and a search a model error cut short is not the model's:
        nothing about either is complete)."""
        return self.finished and self.loaded and all(r.complete for _, r, _, _ in self.parts)

    @property
    def cut(self) -> int:
        """The model errors that cut the model's search short (0: none, or it did not load)."""
        core = self.result("core")
        return core.info["reach"].get("cut", 0) if core is not None and core.info["loaded"] else 0

    @property
    def errors(self) -> int:
        """The model errors any part of the model reported."""
        return sum(1 for _, r, _, _ in self.parts if r is not None for d in r.findings if d["cls"] == ERROR_CLS)

    @property
    def explored(self) -> bool:
        """A complete exploration of the model as it is, every check of it run without a
        model error: the only run that closes a conflict it no longer finds (a capped run, a
        model that does not load and a check a model error broke off close none)."""
        return self.complete and not self.errors

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
    closed: list = field(default_factory=list)     # (entry, why): a complete check no longer finds it


def assemble(root, outcome, previous: dict | None, *, max_states: int | None = None) -> Assembled:
    """The findings of every part, plus the stored conflicts this check keeps open (also
    those of the models it left out or whose file is gone). max_states: the check's bound
    (default: the plan's)."""
    if max_states is None:
        max_states = dict(outcome.planned[0].spec.options)["max_states"] if outcome.planned else Bounds().max_states
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
    views, named = [], []
    for view in models.values():
        core = view.result("core")
        if core is not None and core.info["loaded"] and core.info["covers"]:
            views.append((view.id, core.info["families"], core.info["covers"]))
        if core is not None and core.info["loaded"]:
            named.append((view.id, core.info["sources"]))
    findings += [f for f in overlap_views(views) + unstored_sources(root, named) if f.id not in seen]
    before = {c["id"] for c in (previous or {}).get("conflicts", [])}
    conflicts = [f for f in findings if f.cls == CONFLICT]
    kept, closed = _kept(root, models, previous, {f.id for f in conflicts})
    conflicts += kept
    return Assembled(outcome, models, conflicts, [f for f in findings if f.cls == WARNING],
                     [f for f in findings if f.cls == ERROR_CLS], {f.id for f in conflicts if f.id not in before},
                     max_states, closed)


def _kept_finding(c: dict, reason: str) -> Finding:
    return Finding(c["kind"], CONFLICT, c["model"], c["subject"], c["text"], (), tuple(c["sources"]),
                   tuple(c.get("path", [])), "", {"kept": reason, "entry": c}, None, c["id"])


def _kept(root, models: dict, previous: dict | None, found: set) -> tuple[list, list]:
    """The stored conflicts a check of their model did not find again: (kept, closed).
    Only a complete exploration of the model as it is (ModelView.explored) closes one
    (design M6 as the coordinator decided). Every other check keeps it open and blocking:
    a capped one (also when the replay of its stored shrunk path fails, say after a
    setting changed, or when it reaches a NEVER REACHED item), one a model error cut
    short, a model that does not load, a model file that is gone, and a check that left
    the model out (`check lamp` keeps the other models' conflicts open, and they count
    for its exit code as they do for the release the status names). The reason says what
    this check saw and that a complete check will settle it."""
    kept, closed = [], []
    existing = {p.stem for p in model_files(root)}
    for c in (previous or {}).get("conflicts", []):
        if c["id"] in found:
            continue
        view = models.get(c["model"])
        if view is None:
            if c["model"] not in existing:
                kept.append(_kept_finding(c, f"its model file {FLOW_DIR.as_posix()}/{c['model']}.py is gone; it "
                                             f"closes only when a complete check of {c['model']} no longer finds it"))
            else:
                kept.append(_kept_finding(c, f"this check left {c['model']} out; a complete check of {c['model']} "
                                             f"will settle it"))
            continue
        if not view.finished:
            continue
        if view.explored:
            closed.append((c, f"a complete check of {c['model']} no longer finds it"))
            continue
        core = view.result("core")
        scope = ("the model does not load" if core is None or not core.info["loaded"]
                 else "a model error cut this check short" if view.errors else "this check is capped")
        replay = view.result("replay")
        outcome, why = (replay.info["replays"].get(c["id"]) if replay is not None else None) or (
            None, "no stored path to replay")
        if c["kind"] == "NEVER REACHED" and core is not None and core.info.get("loaded") \
                and c["subject"] in core.info.get("reached", []):
            reason = f"this check reaches it now; {scope}; a complete check will settle it"
        elif outcome == GONE:
            reason = f"its stored path no longer replays ({why}); {scope}; a complete check will settle it"
        elif outcome == REPLAYED:
            reason = f"{why}; {scope}"
        elif why == scope:
            reason = f"proven by an earlier complete check; {scope}"
        else:
            reason = f"proven by an earlier complete check ({why}); {scope}"
        kept.append(_kept_finding(c, reason))
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
    """The first line of a call that returns before every part is done: still running, or
    not finished because the model files changed under the run."""
    if o.changed is not None:
        return f"RUNNING: not finished: {o.changed}; resume with: {resume}"
    done = [p.label for p, r in zip(o.planned, o.results) if r is not None]
    line = f"RUNNING: {len(done)} of {len(o.planned)} parts done" + (f" ({', '.join(done)})" if done else "")
    return line + _current_text(o.current, "; still ") + f"; resume with: {resume}"


def _survivors_said(result: Assembled) -> str:
    """check --full: the deliberate breakages no check caught, said on the first line (never a
    bare "clean" over them); their warnings follow below."""
    n = len([f for f in result.warnings if f.kind == "MUTANT SURVIVES"])
    return f"; {_plural(n, 'deliberate breakage')} not caught \u2014 see below" if n else ""


def _warnings_said(result: Assembled) -> str:
    survived = _survivors_said(result)
    others = len([f for f in result.warnings if f.kind != "MUTANT SURVIVES"])
    if not others:
        return survived
    return survived + f"; {_plural(others, 'other model warning' if survived else 'model warning')}"


def verdict(result: Assembled, resume: str) -> tuple[str, int]:
    o = result.outcome
    if not o.finished:
        return running_line(o, resume), EXIT_RUNNING
    n_new = len([f for f in result.conflicts if f.id in result.new])
    n_open = len(result.conflicts) - n_new
    cut = [m for m, v in result.models.items() if v.loaded and v.cut]
    capped = [m for m, v in result.models.items() if v.loaded and not v.complete and not v.cut]
    unexplored = [m for m, v in result.models.items() if not v.loaded]
    head = []
    if n_new and n_open:
        head.append(f"{_plural(n_new, 'new conflict')}, {n_open} open")
    elif n_new:
        head.append(_plural(n_new, "new conflict"))
    elif n_open:
        head.append(_plural(n_open, "open conflict"))
    elif capped or cut:
        head.append("no conflict found")
    if result.errors:
        head.append(_plural(len(result.errors), "model error"))
    if capped or cut or unexplored:
        why = []
        if capped:
            why.append(f"{', '.join(capped)} capped at {result.max_states:,} states")
            if not result.conflicts:
                why[-1] += f" ({', '.join(_undecided(result, capped))} undecided)"
        if cut:
            why.append(f"{', '.join(cut)} cut short by a model error")
            if not result.conflicts:
                why[-1] += f" ({', '.join(_undecided(result, cut))} undecided)"
        if unexplored:
            why.append(f"{', '.join(unexplored)} not explored (model error)")
        tail = "UNKNOWN: " + "; ".join(why)
    elif not head:
        tail = "clean, complete" + _warnings_said(result)
    else:
        tail = "complete" + _survivors_said(result)
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
    if f.kind != "NEVER REACHED":
        return ""
    return explanation_text(f.detail) or ""


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


def causes_of(result: Assembled, f: Finding) -> list[dict]:
    """With --full: every change of the model whose mutant no longer has this conflict (the
    mutate part's causes: guards dropped or widened, transitions removed, ends cut off)."""
    view = result.models.get(f.model)
    mutate = view.result("mutate") if view is not None else None
    return list((mutate.info.get("causes", {}) if mutate is not None else {}).get(f.id, []))


def cause_lines(result: Assembled, f: Finding) -> list[str]:
    """With --full: each guard whose drop or widening removes this conflict, said as its cause
    (G5: what the conflict rests on, never a survivor inviting to delete the guard): the
    requested guards (their own source=) first, then the guards that carry their action's
    source. Every change that removes it, guards and others, is in --json ("causes")."""
    every = causes_of(result, f)
    guards = [c for c in every if c["op"] in ("drop guard", "widen guard")]
    guards.sort(key=lambda c: (not c["requested"], c["line"] or 0))
    out = [f"  cause (check --full): {c['cause']} this conflict does not occur" for c in guards]
    others = len(every) - len(guards)
    if others:
        out.append(f"  {_plural(others, 'other change')} of the model remove{'s' if others == 1 else ''} it too "
                   f"(check --full --json: \"causes\")")
    return out


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
    lines += [f"closed {c['id']} {c['kind']} {c['model']}: {why}" for c, why in result.closed]
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
                           picture=picture(result, f), causes=causes_of(result, f)) for f in result.conflicts],
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
    a file keep theirs, so checking one model does not drop the others' open conflicts. The
    conflicts of a model whose file is gone stay too: no check explored it (design M6)."""
    existing = {p.stem for p in model_files(root)}
    previous = previous or {}
    kept = {m: v for m, v in previous.get("models", {}).items() if m in existing and m not in result.models}
    entries = {c["id"]: c for c in previous.get("conflicts", []) if c["model"] not in result.models}
    entries.update((f.id, conflict_entry(f)) for f in result.conflicts)
    entries = list(entries.values())
    models = dict(kept)
    for mid, view in result.models.items():
        models[mid] = {"complete": view.complete, "loaded": view.loaded, "cut": view.cut,
                       "errors": len([f for f in result.errors if f.model == mid]),
                       "parts": sorted(r.digest for _, r, _, _ in view.parts),
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
    """The flow-model part of `python -m flowguard release` (design 7.6): check
    every model with --full (the deliberate-breakage mutants and the unreduced symmetry
    check) and the release wait. True when the release may go on: a conflict or a model
    error stops it (UNKNOWN does not); work still RUNNING after the wait stops it too, since
    nothing was decided. An unreadable conflicts.json raises ProjectError and an engine failure
    an exception (InternalError or another): the release stops on either with exit 2, never
    as a failed gate."""
    argv = ["check", "--full", "--wait", str(RELEASE_WAIT), "--root", str(root)]
    code = check(parser().parse_args(argv), argv, out=out, err=err)
    return code in (EXIT_CLEAN, EXIT_UNKNOWN)


FAILS = "release and CI fail until fixed; without a hook a commit is not blocked"


def status_lines(root) -> list[str]:
    """For `python -m flowguard status`: open conflicts of the flow models from the last
    final check (.flowguard/conflicts.json, the only source), and what they stop: release
    (and so CI, which runs it) fails on an open conflict, a model error or a model that does
    not load; nothing stops a commit unless the project installs a hook that runs it. A
    project with no flow model and no recorded check gets no line."""
    try:
        data = read_conflicts(root)
    except ProjectError as e:                    # the same line check, show and release stop with
        return [f"flow models: {e}"]
    if data is None:
        return [f"flow models: no check recorded (run {PROG} check)"] if model_files(Path(root)) else []
    conflicts = data["conflicts"]
    unknown = data["unknown"]
    models = data.get("models", {})
    unexplored = [m for m in unknown if not models.get(m, {}).get("loaded", True)]
    erring = {m: v["errors"] for m, v in models.items() if v.get("errors") and m not in unexplored}
    capped = [m for m in unknown if m not in unexplored and not models.get(m, {}).get("cut")]
    if conflicts:
        ids = ", ".join(c["id"] for c in conflicts)
        line = f"flow models: {_plural(len(conflicts), 'open conflict')} ({ids}); {FAILS}"
    elif unknown or erring:
        line = "flow models: no conflict found"
    else:
        line = "flow models: clean"
    held = {c["model"] for c in conflicts}                 # a capped check never closes a proven conflict
    if [m for m in capped if m not in held]:
        line += (f"; capped: {', '.join(m for m in capped if m not in held)} (what a capped search could not "
                 f"decide is UNKNOWN; that alone fails no release)")
    if [m for m in capped if m in held]:
        line += (f"; capped with open conflicts: {', '.join(m for m in capped if m in held)} (they stay open "
                 f"until a complete check settles them)")
    if erring:
        shown = [f"{m} ({_plural(n, 'model error')}" + ("; its search was cut short" if models[m].get("cut") else "")
                 + ")" for m, n in sorted(erring.items(), key=lambda x: natural_key(x[0]))]
        line += f"; model errors: {', '.join(shown)}"
    if unexplored:
        line += f"; not explored: {', '.join(unexplored)} (the model does not load)"
    if (erring or unexplored) and not conflicts:
        line += f"; {FAILS}"
    return [line]
