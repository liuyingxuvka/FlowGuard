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

from . import diagram, jobs, history
from .checks import CONFLICT, ERROR_CLS, GONE, REPLAYED, WARNING, Finding, explanation_text, make_finding
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
         "show": "draw the flowchart of the current change or conflict",
         "decide": "record stored owner words or a narrowly eligible temporary decision"}


def _check_arguments(check: argparse.ArgumentParser) -> None:
    check.add_argument("models", nargs="*", metavar="MODEL", help="model ids or files in .flowguard/flow/")
    check.add_argument("--wait", type=_seconds, default=DEFAULT_WAIT,
                       help=f"return after at most this many seconds (default {DEFAULT_WAIT:g})")
    check.add_argument("--commit-ready", action="store_true", help="read existing results for actual staged bytes; never start work")
    check.add_argument("--tests", nargs='+', metavar='NODEID',
                       help='record these explicit pytest cases and audit their routes; otherwise ordinary whole-project checks select statically related tests')
    check.add_argument("--full", action="store_true",
                       help="also mutate the models and verify renaming without reduction")
    check.add_argument('--walk-steps', type=int, default=64, metavar='N',
                       help='ordinary affected-module native walk budget in steps (default 64)')
    check.add_argument('--seed', type=int, default=0, help='native walk seed (default 0)')
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


def _decide_arguments(command):
    command.add_argument('conflict', metavar='ID')
    modes = command.add_mutually_exclusive_group(required=True)
    modes.add_argument('--owner', metavar='QUOTE')
    modes.add_argument('--provisional', metavar='REASON')
    command.add_argument('--request', metavar='ID')
    command.add_argument('--existing-routes', action='store_true',
                         help='BOTH only: owner words authorize both already implemented and witnessed routes')
    command.add_argument('--root')
    command.add_argument('--json', action='store_true')


_ARGUMENTS = {"check": _check_arguments, "show": _show_arguments, "decide": _decide_arguments}


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
    tb = e.__traceback__
    package = Path(__file__).resolve().parents[1]
    owned = None
    while tb is not None:
        if Path(tb.tb_frame.f_code.co_filename).resolve().is_relative_to(package):
            owned = tb
        tb = tb.tb_next
    # A traceback-less external error has no engine location: say so explicitly
    # instead of silently presenting a standard-library filename as our code.
    where = " (FlowGuard location unavailable)"
    if owned is not None:
        path = Path(owned.tb_frame.f_code.co_filename).resolve().relative_to(package.parent)
        where = f" ({path.as_posix()}:{owned.tb_lineno})"
    message = " ".join(str(e).splitlines())
    label = message if isinstance(e, InternalError) else f"{type(e).__name__}: {message}"
    return f"internal error: {label}{where}"


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
        if args.verb == 'decide':
            return decide(args, out=out)
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
                              "warnings": [], "surviving_breakages": 0, "setting_proposals": [],
                              "errors": [], "unknown": [], "models": {}, "parts": [],
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
    from .project import require_current_format
    require_current_format(root)
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
    return text + (f": {phase}" if phase else "") + (f" ({states:,} states explored)" if states else "")


# ---------------------------------------------------------------------- check
def check(args, argv, *, prog: str = PROG, out=None, err=None, on_result=None) -> int:
    """A project problem raises ProjectError and an engine failure InternalError (main turns
    either into one line and exit 2; release stops on them)."""
    out = out or sys.stdout
    err = err or sys.stderr
    root = find_root(Path(args.root) if args.root else Path.cwd())
    from .project import require_current_format
    require_current_format(root)
    paths = resolve_models(root, args.models) if args.models else model_files(root)
    previous = read_conflicts(root)
    from .codeaudit import reopen_declared, apply_declared
    previous = apply_declared(root, reopen_declared(root, previous))
    if getattr(args, 'commit_ready', False):
        return commit_ready_command(root, args, out)
    tests = getattr(args, 'tests', None)
    if getattr(args, 'walk_steps', 64) < 0:
        raise ProjectError('--walk-steps must be nonnegative')
    if tests is None and not args.full and not args.models:
        from .affected import selected_tests
        tests = selected_tests(root)
        # The dirty Git diff can be identical to the source already checked by
        # an explicit failing case. Keep that actual failure; do not expand its
        # scope and execute it again until its real inputs change.
        audit = (previous or {}).get('code_audit')
        if tests and audit and audit.get('test_failures'):
            from .codeaudit import saved_result
            if saved_result(root, audit) is not None:
                tests = []
    if not paths and not (previous or {}).get("conflicts") and not (previous or {}).get('code_audit') and not tests:
        return _early(out, f"no flow models in {FLOW_DIR.as_posix()}/", EXIT_CLEAN, args.json)
    planned = jobs.plan(root, paths, full=args.full, max_states=args.max_states, stored=previous, tests=tests,
                        incremental=not args.full, walk_steps=getattr(args, 'walk_steps', 64),
                        walk_seed=getattr(args, 'seed', 0))
    outcome = jobs.run(root, planned, wait=args.wait, keep=args.keep, progress=_Progress(err))
    resume = f"{prog} {shlex.join(argv)}"
    if outcome.failure is not None:
        raise InternalError(str(outcome.failure))
    result = assemble(root, outcome, previous, max_states=args.max_states)
    if outcome.finished:
        from .codeaudit import apply_declared
        final_record = apply_declared(root, conflicts_data(root, result, previous))
        write_conflicts(root, final_record)
    lines, data = render(root, result, resume)
    if on_result is not None:
        on_result(data)
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
    def native_unknown(self):
        core = self.result('core')
        if core is None or not core.info.get('loaded'):
            return False
        native = core.info.get('native', {})
        return native.get('status') == 'unknown'

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
    code: list = field(default_factory=list)       # project-level native part; never a ModelView
    code_record: dict | None = None
    declarations: list = field(default_factory=list)
    previous: dict | None = None


def assemble(root, outcome, previous: dict | None, *, max_states: int | None = None) -> Assembled:
    """The findings of every part, plus the stored conflicts this check keeps open (also
    those of the models it left out or whose file is gone). max_states: the check's bound
    (default: the plan's)."""
    if max_states is None:
        max_states = dict(outcome.planned[0].spec.options)["max_states"] if outcome.planned else Bounds().max_states
    models, code_parts = {}, []
    for item, r, c, w in zip(outcome.planned, outcome.results, outcome.cached, outcome.workers):
        if item.spec.kind == 'code-audit':
            code_parts.append((item, r, c, w))
        else:
            models.setdefault(item.spec.model, ModelView(item.spec.model)).parts.append((item, r, c, w))
    # A current cached recipe can carry the original retained history even when
    # the published ledger was removed. Use it before comparison and persistence,
    # so both owners see the same baseline and validated decision references.
    recovered = []
    recorded = (previous or {}).get('models', {})
    known = {entry['model'] for entry in (previous or {}).get('conflicts', [])}
    for view in models.values():
        if view.id in recorded or view.id in known:
            continue
        for item, part, _, _ in view.parts:
            if item.spec.kind == 'core' and part is not None:
                entries = jobs.retained_entries(root, item, part.digest)
                if entries:
                    recovered.extend(entries)
    if recovered:
        previous = {**(previous or {}), 'conflicts':[*((previous or {}).get('conflicts', [])), *recovered]}
    findings, seen = [], set()
    for view in models.values():
        for _, r, _, _ in view.parts:
            for d in (r.findings if r is not None else []):
                f = Finding.from_json(d)
                if f.id not in seen:
                    seen.add(f.id)
                    findings.append(f)
    for _, result, _, _ in code_parts:
        for raw in result.findings if result is not None else []:
            finding = Finding.from_json(raw)
            if finding.id not in seen:
                seen.add(finding.id)
                findings.append(finding)
    views, named = [], []
    for view in models.values():
        core = view.result("core")
        if core is not None and core.info["loaded"] and core.info["covers"]:
            views.append((view.id, core.info["families"], core.info["covers"]))
        if core is not None and core.info["loaded"]:
            named.append((view.id, core.info["sources"]))
    findings += [f for f in overlap_views(views) + unstored_sources(root, named) if f.id not in seen]
    from .native_finding import native_drift
    for view in models.values():
        core = view.result('core')
        drift = native_drift(view.id, core)
        if drift is not None:
            findings.append(drift[0])
    before = {c["id"] for c in (previous or {}).get("conflicts", [])}
    from .codeaudit import declared_entries
    declarations = declared_entries(previous)
    permitted = {entry['id'] for entry in declarations}
    conflicts = [f for f in findings if f.cls == CONFLICT and f.id not in permitted]
    kept, closed = _kept(root, models, previous, {f.id for f in conflicts}, code_parts=code_parts)
    conflicts += kept
    assembled = Assembled(outcome, models, conflicts, [f for f in findings if f.cls == WARNING],
                     [f for f in findings if f.cls == ERROR_CLS], {f.id for f in conflicts if f.id not in before},
                     max_states, closed, code_parts, previous=previous)
    from .codeaudit import record
    assembled.code_record = record(root, assembled, previous)
    from .codeaudit import test_failure
    for nodeid in (assembled.code_record or {}).get('test_failures', []):
        failure = test_failure(nodeid)
        if failure.id not in {finding.id for finding in assembled.errors}:
            assembled.errors.append(failure)
    assembled.declarations = declarations
    return assembled


def model_observation(view):
    core = view.result('core')
    descriptor = core.info.get('descriptor', {}) if core is not None else {}
    receipt = core.digest if core is not None else 'unfinished:' + view.id
    observed = core
    routes = view.result('routes')
    route_descriptor = routes.info.get('descriptor') if routes is not None else None
    if (route_descriptor and 'finite comparison not evaluated for clean declaration' in descriptor.get('comparison_limits', [])
            and route_descriptor.get('receipt') == routes.digest
            and route_descriptor.get('scope') == descriptor.get('scope')
            and route_descriptor.get('inputs')
            and all(path in descriptor.get('inputs', {}) and descriptor['inputs'][path] == data
                    for path, data in route_descriptor['inputs'].items())):
        # A new route-only conflict owns these actual full relations. Never
        # attribute them to the clean core, or mix differently loaded inputs.
        descriptor, receipt, observed = route_descriptor, routes.digest, routes
    return dict(receipt=receipt, finished=view.finished, loaded=view.loaded,
                complete=view.explored, errors=view.errors, scope=descriptor.get('scope'),
                obligations=descriptor.get('obligations'), replay='not_run',
                conflicts=[{key:f[key] for key in ('id','kind','subject')} for f in (observed.findings if observed else []) if f['cls'] == CONFLICT])


def closure_proof(root, entry, view):
    """Consume real worker receipts; no caller flag or bare reference closes."""
    from ..map.common import content_digest
    core = view.result('core')
    if core is None or not view.explored:
        return None
    native = core.info.get('native', {})
    proof = native.get('closures', {}).get(entry['id'])
    if proof is not None:
        if native.get('schema') != 'flowguard.native-evidence.v1' or native.get('bound') is not True or native.get('status') != 'conformant':
            return None
        keys = proof.get('checks', [])
        checks = native.get('checks', {})
        if not keys or not native.get('footprints') or any(key not in checks or checks[key].get('status') != 'conformant' for key in keys):
            return None
        from ..native.inputs import footprint_evidence
        if any(footprint_evidence(footprint).status != 'current' for footprint in native['footprints']):
            return None
    else:
        proof = core.info.get('model_closures', {}).get(entry['id'])
        if proof is None or proof.get('boundary') != 'model-only' or entry.get('native_confirmation') or native.get('bound'):
            return None
        old = entry.get('history', {}).get('baseline', {}).get('scope') or {}
        anchors = old.get('coverage', {}).get('anchors', [])
        current = core.info.get('descriptor', {}).get('scope') or {}
        from ..map.inventory import coverage_kind
        correction = proof.get('model_correction', {})
        derived = (correction.get('kind') == 'model_corrected' and correction.get('closed_rules') and
                   correction.get('original_receipt') == entry.get('history', {}).get('baseline', {}).get('receipt'))
        if not anchors or not derived and any(coverage_kind(root, values) not in {'model-only', 'data-only'}
                                             for values in (anchors, current.get('coverage', {}).get('anchors', []))):
            return None
        if proof.get('model_receipt') != core.digest or proof.get('kind') not in {'model_corrected', 'requirement_changed'}:
            return None
    if proof.get('kind') == 'requirement_changed':
        compared = history.assess(entry, model_observation(view), root=root)
        if compared.get('resolution') != proof.get('resolution') or compared['outcome'] != 'requirement_changed':
            return None
    regression = proof.get('regression')
    if proof.get('complete_scope') is not True or proof.get('original_condition_gone') is not True or not isinstance(regression, dict):
        return None
    path = Path(regression.get('path', ''))
    if path.is_absolute() or '..' in path.parts or not path.parts or not (Path(root) / path).is_file() or (Path(root) / path).is_symlink():
        return None
    if regression.get('passed') is not True or content_digest(Path(root) / path) != regression.get('digest'):
        return None
    return proof


def _kept_finding(c: dict, reason: str) -> Finding:
    return Finding(c["kind"], CONFLICT, c["model"], c["subject"], c["text"], (), tuple(c["sources"]),
                   tuple(c.get("path", [])), "", {"kept": reason, "entry": c}, None, c["id"])


def _kept(root, models: dict, previous: dict | None, found: set, *, code_parts=()) -> tuple[list, list]:
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
        from . import codeaudit
        if codeaudit.is_entry(c):
            result = next((r for _, r, _, _ in code_parts if r is not None), None)
            proof = codeaudit.closure(root, c, result)
            if proof is not None:
                closed.append((dict(c, closure=proof), 'code_fixed: original recorded scope and executed unchanged regression'))
            else:
                kept.append(codeaudit.kept(root, c, result))
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
            kept.append(_kept_finding(c, 'changed work is RUNNING; its prior conflict stays open'))
            continue
        compared = history.compared(c, model_observation(view), root=root)
        comparison = compared['history']['latest']
        if view.explored:
            core = view.result('core')
            recorded = (core.info.get('native', {}).get('closures', {}) if c['kind'] == 'MODEL DRIFT' else
                        core.info.get('model_closures', {})) if core is not None else {}
            correction = recorded.get(c['id'], {}).get('model_correction', {})
            proof = closure_proof(root, c, view) if (comparison['outcome'] in {'model_absent', 'requirement_changed'} or
                    correction.get('kind') == 'model_corrected' and correction.get('original_receipt') ==
                    c.get('history', {}).get('baseline', {}).get('receipt')) else None
            if proof is not None:
                scope = 'implemented replacement requirement' if proof['kind'] == 'requirement_changed' else 'complete retained scope'
                closed.append((dict(compared, closure=proof), proof['kind'] + ': ' + scope + ' and executed regression'))
                continue
            reasons = ', '.join(row['code'] + (': ' + row['subject'] if row['subject'] else '')
                                for row in comparison['reasons'])
            reason = ('replacement requirement is sourced; current behavior evidence and executable regression are still required'
                      if comparison['outcome'] == 'requirement_changed' else
                      'complete retained model scope is clear; native original-condition evidence and executable regression are still required'
                      if comparison['outcome'] == 'model_absent' else 'retained: ' + reasons)
            kept.append(_kept_finding(compared, reason))
            continue
        c = compared
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
    return f"; {_plural(n, 'deliberate breakage')} not caught - see below" if n else ""


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
    native_unknown = [m for m, v in result.models.items() if v.native_unknown]
    from .codeaudit import scope_unknown
    code_unknown = scope_unknown(result.code_record)
    unexplored = [m for m, v in result.models.items() if not v.loaded]
    head = []
    if n_new and n_open:
        head.append(f"{_plural(n_new, 'new conflict')}, {n_open} open")
    elif n_new:
        head.append(_plural(n_new, "new conflict"))
    elif n_open:
        head.append(_plural(n_open, "open conflict"))
    elif capped or cut or native_unknown or code_unknown:
        head.append("no conflict found")
    if result.errors:
        native_errors = [finding for finding in result.errors if finding.model == '@recorded-code']
        model_errors = len(result.errors) - len(native_errors)
        if model_errors:
            head.append(_plural(model_errors, 'model error'))
        if native_errors:
            head.append(_plural(len(native_errors), 'selected native test failure'))
    if capped or cut or unexplored or native_unknown or code_unknown:
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
        if native_unknown:
            why.append('native conformance unavailable: ' + ', '.join(native_unknown))
        if code_unknown:
            why.append('recorded code input freshness or observation scope UNKNOWN; explicit --tests retest required')
        tail = "UNKNOWN: " + "; ".join(why)
    elif not head:
        tail = "clean, complete" + _warnings_said(result)
    else:
        tail = "complete" + _survivors_said(result)
    if result.code_record is not None and not result.models and not code_unknown:
        tail = 'complete recorded tests/invocations' if head else 'no code conflict found; complete recorded tests/invocations'
    line = "; ".join(head + [tail])
    if result.errors:
        code = EXIT_ERROR
    elif result.conflicts:
        code = EXIT_CONFLICT
    elif capped or native_unknown or code_unknown:
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
    if f.detail.get('code_audit'):
        from .codeaudit import fact_lines, question
        if f.detail.get('route'):
            lines += fact_lines(f.detail['route'])
        lines.append('  ' + question({'kind': f.kind}))
    if f.kind == "STUCK":
        lines += _stuck_lines(f.detail)
    lines.append('  requests:')
    lines.extend(f'    {rid} "{words}"' if rid else '    ' + words for rid, words in request_lines(root, f.sources))
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
    from .proposals import proposal_text
    proposals = [dict(p, model=mid) for mid, view in result.models.items()
                 if (core := view.result("core")) is not None
                 for p in core.info.get("setting_proposals", [])]
    lines = [line, *(proposal_text(p) for p in proposals)]
    for f in new:
        lines += full_block(root, result, f)
    for f in open_:
        lines.append(_one_line(result, f, "OPEN") + (f" (kept: {f.detail['kept']})" if "kept" in f.detail else ""))
        lines += cause_lines(result, f)
    lines += [f"closed {c['id']} {c['kind']} {c['model']}: {why}" for c, why in result.closed]
    lines += requirement_lines(root,[entry for entry,_ in result.closed])
    lines += [_warning_line(result, f) for f in result.warnings]
    for f in result.errors:
        lines += _error_lines(f)
    lines += declared_lines(root, result)
    reaches = [reach(v) for v in result.models.values()]
    lines += [r for r in reaches if r is not None]
    from .codeaudit import summary, scope_unknown
    lines += summary(root, result.code_record)
    from .codeaudit import declared_lines as code_declared_lines
    lines += code_declared_lines({'closed': result.declarations})
    o = result.outcome
    models = {}
    from .samples import coverage_summary
    for mid, view in result.models.items():
        core = view.result("core")
        info = core.info if core is not None else {}
        models[mid] = {"finished": view.finished, "complete": view.complete if view.finished else None,
                       "states": info["reach"]["states"] if info.get("loaded") else None,
                       "reach": reach(view),
                       "undecided": _undecided(result, [mid]) if view.finished and not view.complete else [],
                       "symmetry": info.get("symmetry"),
                       "native_operations": info.get('native', {}).get('operation_coverage', {}).get('selected_operations'),
                       "walk": {key:info['native']['walk'][key] for key in ('seed', 'step_budget', 'status')}
                               if 'walk' in info.get('native', {}) else None,
                       "composition": info.get('composition'), 'foreign': info.get('foreign', []),
                       'saved_samples':coverage_summary(info['saved_samples']) if 'saved_samples' in info else None}
    sampled=[model['saved_samples'] for model in models.values() if model['saved_samples'] is not None]
    if sampled:
        files=sum(item['files'] for item in sampled);starts=sum(item['starts'] for item in sampled)
        if not files and all(item['status']=='unchecked' for item in sampled):
            lines.append('old saves not checked: no saved-sample files supplied')
        else:
            status='UNKNOWN' if any(item['status']=='unknown' for item in sampled) else 'finite supplied scope'
            lines.append(f'saved inputs: {files} file entries; {starts} abstract starts; {status}')
            if any(item['status']=='unchecked' for item in sampled):
                lines.append('old saves not checked for other models')
    data = {
        "verdict": line, "exit": code, "complete": o.finished and not scope_unknown(result.code_record) and all(v.complete and not v.native_unknown for v in result.models.values()),
        "conflicts": [dict(public_finding(f), new=f.id in result.new, requests=request_lines(root, f.sources),
                           picture=picture(result, f), causes=causes_of(result, f)) for f in result.conflicts],
        "warnings": [f.to_json() for f in result.warnings],
        "surviving_breakages": sum(f.kind == "MUTANT SURVIVES" for f in result.warnings),
        "setting_proposals": proposals,
        "errors": [f.to_json() for f in result.errors],
        "unknown": [m for m, v in result.models.items() if v.finished and (not v.complete or v.native_unknown)],
        "models": models,
        "parts": [{"kind": p.spec.kind, "model": p.spec.model, "digest": r.digest if r is not None else None,
                   "cached": c, "worker": w} for p, r, c, w in zip(o.planned, o.results, o.cached, o.workers)],
        "declared_routes": [d for v in result.models.values() for _, r, _, _ in v.parts if r is not None
                            for d in r.info.get("declared_routes", [])],
        "closed": [{"id": c["id"], "kind": c["kind"], "model": c["model"], "why": why,
                    **({'requirement_change':requirement_summary(root,c)} if c.get('closure',{}).get('kind')=='requirement_changed' else {})}
                   for c, why in result.closed],
        "resume": None if o.finished else resume,
        "running": None if o.finished else {"done": sum(r is not None for r in o.results), "total": len(o.planned),
                                            "current": o.current, "worker": o.worker, "job": o.job},
    }
    if result.code_record is not None:
        data['code_audit'] = result.code_record
    return lines, data


# ---------------------------------------------------------------------- conflicts.json
def conflicts_data(root, result: Assembled, previous: dict | None) -> dict:
    """This computation's models replace their entries; the other models that still have
    a file keep theirs, so checking one model does not drop the others' open conflicts. The
    conflicts of a model whose file is gone stay too: no check explored it (design M6)."""
    from . import codeaudit
    existing = {p.stem for p in model_files(root)}
    previous = result.previous if result.previous is not None else previous
    previous = previous or {}
    kept = {m: v for m, v in previous.get("models", {}).items() if m in existing and m not in result.models}
    entries = {c["id"]: c for c in previous.get("conflicts", []) if c["model"] not in result.models}
    for closed, _ in result.closed:
        entries.pop(closed['id'], None)
    before = {entry['id']:entry for entry in previous.get('conflicts', [])}
    entries.update((f.id, conflict_entry(f, observation=model_observation(result.models[f.model])
                   if f.model in result.models else None, previous=None if 'entry' in f.detail else before.get(f.id))) for f in result.conflicts)
    for identifier, entry in entries.items():
        from . import codeaudit
        finding = next((f for f in result.conflicts if f.id == identifier and f.detail.get('route')), None)
        code_result = codeaudit.result_of(result)
        if finding is not None and code_result is not None:
            entry['code_evidence'] = before.get(identifier, {}).get('code_evidence') or codeaudit.evidence(root, finding, code_result)
            entry['subject_terms'] = [finding.detail['route']['site']['function'].split('.')[-1]]
        view = result.models.get(entry['model'])
        core = view.result('core') if view is not None else None
        confirmed = core.info.get('native', {}).get('confirmed', {}).get(identifier) if core is not None else None
        if entry.get('native_confirmation') is None and confirmed is not None:
            entry['native_confirmation'] = confirmed
    entries = list(entries.values())
    models = dict(kept)
    for mid, view in result.models.items():
        core = view.result('core')
        descriptor = core.info.get('descriptor', {}) if core is not None else {}
        models[mid] = {"complete": view.complete, "loaded": view.loaded, "cut": view.cut,
                       "finished": view.finished and view.loaded and not view.errors,
                       "unknown": not view.explored or view.native_unknown, "native_unknown": view.native_unknown, "inputs": descriptor.get('inputs', {}),
                       "observation": model_observation(view),
                       "core": {'digest':core.digest, 'planned':next(p.to_json() for p, r, _, _ in view.parts if r is core)} if core is not None else None,
                       "errors": len([f for f in result.errors if f.model == mid]),
                       # Full-only checks are diagnostics, not changes to this model's
                       # persistent check identity. Their real conflicts/errors remain above.
                       "parts": sorted(r.digest for p, r, _, _ in view.parts if p.spec.kind != "mutate"
                                       and p.spec.kind != "core"),
                       "warnings": len([f for f in result.warnings if f.model == mid
                                        and f.kind != "MUTANT SURVIVES"]),
                       "setting_proposals": (view.result("core").info.get("setting_proposals", [])
                                             if view.result("core") is not None else [])}
        core = view.result("core")
        if core is not None:
            # Execution and diagnostic options name actual cache recipes, not
            # the source/scope identity of the checked model. Keep planned below
            # actual, including a newly requested ordinary walk recipe.
            from .parts import PartSpec, part_digest
            spec = next(p.spec for p, r, _, _ in view.parts if r is core)
            canonical = PartSpec(spec.kind, spec.model, tuple(
                (k, v) for k, v in spec.options if k not in
                {"verify_symmetry", "incremental", "native_baseline", "known_never", "walk_steps", "walk_seed"}))
            models[mid]["parts"].append(part_digest(root, canonical, core.reads))
            models[mid]["parts"].sort()
            # Preserve an actual still-current receipt when full-only diagnostics
            # leave the checked source, scope and observation unchanged.
            before = previous.get('models', {}).get(mid, {})
            old_observation = before.get('observation') or {}
            current_observation = models[mid]['observation']
            same_observation = ({k:v for k,v in old_observation.items() if k != 'receipt'} ==
                                {k:v for k,v in current_observation.items() if k != 'receipt'})
            saved = before.get('core')
            same_recipe = saved and saved['planned'] == next(p.to_json() for p, r, _, _ in view.parts if r is core)
            if (saved and same_observation and before.get('parts') == models[mid]['parts']
                    and before.get('native_unknown', False) == models[mid]['native_unknown']
                    and (spec.option('verify_symmetry', False) or same_recipe)):
                planned = jobs.Planned.from_json(saved['planned'])
                if jobs.lookup(root, planned, recorded_digest=saved['digest']) is not None:
                    models[mid]['core'] = saved
                    models[mid]['observation'] = old_observation
    digests = sorted(d for v in models.values() for d in v["parts"])
    data = {"engine": ENGINE_DIGEST,
            "tree": hashlib.sha256(json.dumps(digests).encode("utf-8")).hexdigest(),
            "complete": all(v["complete"] and not v.get('native_unknown') for v in models.values()),
            "conflicts": entries,
            "unknown": sorted((m for m, v in models.items() if not v["complete"] or v.get('native_unknown')), key=natural_key),
            "warnings": sum(v["warnings"] for v in models.values()),
            "models": dict(sorted(models.items())),
            "closed": list(previous.get('closed', [])) + [dict(entry, closure={**entry.get('closure', {}), 'why':why}) for entry, why in result.closed]}
    if result.code_record is not None:
        data['code_audit'] = result.code_record
        data['complete'] &= not codeaudit.scope_unknown(result.code_record)
    return data


RELEASE_WAIT = 3600                # the release check may run long (design 7.6); the in-loop default never does


def release(root, *, out=None, err=None, on_result=None) -> bool:
    """The flow-model part of `python -m flowguard release` (design 7.6): check
    every model with --full (the deliberate-breakage mutants and the unreduced symmetry
    check) and the release wait. True when the release may go on: a conflict or a model
    error stops it (UNKNOWN does not); work still RUNNING after the wait stops it too, since
    nothing was decided. An unreadable conflicts.json raises ProjectError and an engine failure
    an exception (InternalError or another): the release stops on either with exit 2, never
    as a failed gate."""
    argv = ["check", "--full", "--wait", str(RELEASE_WAIT), "--root", str(root)]
    results = []
    def completed(data):
        results.append(data)
        if on_result is not None:
            on_result(data)
    code = check(parser().parse_args(argv), argv, out=out, err=err, on_result=completed)
    proposals = [p for data in results for p in data["setting_proposals"]]
    if proposals:
        print("release blocked: proposed settings differ from the covered code", file=out or sys.stdout)
    return code in (EXIT_CLEAN, EXIT_UNKNOWN) and not proposals


FAILS = "release fails until fixed; CI fails only when it runs release; without a hook a commit is not blocked"


def status_lines(root) -> list[str]:
    """For `python -m flowguard status`: open conflicts of the flow models from the last
    final check (.flowguard/conflicts.json, the only source), and what they stop: release
    (and CI only when it runs release) fails on an open conflict, a model error or a model that does
    not load; nothing stops a commit unless the project installs a hook that runs it. A
    project with no flow model and no recorded check gets no line."""
    platform = [problem] if model_files(Path(root)) and (problem := jobs.platform_problem()) else []
    try:
        data = read_conflicts(root)
    except ProjectError as e:                    # the same line check, show and release stop with
        return [f"flow models: {e}", *platform]
    if data is None:
        return [f"flow models: no check recorded (run {PROG} check)", *platform] if model_files(Path(root)) else []
    from .codeaudit import reopen_declared
    data = reopen_declared(root, data)
    conflicts = data["conflicts"]
    unknown = data["unknown"]
    models = data.get("models", {})
    unrecorded = sorted((path.stem for path in model_files(Path(root)) if path.stem not in models), key=natural_key)
    unexplored = [m for m in unknown if not models.get(m, {}).get("loaded", True)]
    erring = {m: v["errors"] for m, v in models.items() if v.get("errors") and m not in unexplored}
    capped = [m for m in unknown if m not in unexplored and not models.get(m, {}).get("cut") and not models.get(m, {}).get('complete')]
    native_unknown = [m for m in unknown if models.get(m, {}).get('native_unknown')]
    if conflicts:
        ids = ", ".join(c["id"] for c in conflicts)
        line = f"flow models: {_plural(len(conflicts), 'open conflict')} ({ids}); {FAILS}"
    elif unknown or erring:
        line = "flow models: no conflict found"
    else:
        line = "flow models: clean"
    if not models and data.get('code_audit'):
        line = (f"recorded code: {_plural(len(conflicts), 'open conflict')}; {FAILS}" if conflicts
                else 'recorded code: no witnessed conflict')
    if unrecorded:
        missing = f"no check recorded for {', '.join(unrecorded)} (run {PROG} check)"
        line = f"flow models: {missing}" if line == "flow models: clean" else f"{line}; {missing}"
    if (data.get('code_audit') or {}).get('test_failures'):
        line += '; selected native tests failed; ' + FAILS
    held = {c["model"] for c in conflicts}                 # a capped check never closes a proven conflict
    if [m for m in capped if m not in held]:
        line += (f"; capped: {', '.join(m for m in capped if m not in held)} (what a capped search could not "
                 f"decide is UNKNOWN; that alone fails no release)")
    if [m for m in capped if m in held]:
        line += (f"; capped with open conflicts: {', '.join(m for m in capped if m in held)} (they stay open "
                 f"until a complete check settles them)")
    if native_unknown:
        line += '; native conformance UNKNOWN: ' + ', '.join(native_unknown)
    if erring:
        shown = [f"{m} ({_plural(n, 'model error')}" + ("; its search was cut short" if models[m].get("cut") else "")
                 + ")" for m, n in sorted(erring.items(), key=lambda x: natural_key(x[0]))]
        line += f"; model errors: {', '.join(shown)}"
    if unexplored:
        line += f"; not explored: {', '.join(unexplored)} (the model does not load)"
    if (erring or unexplored) and not conflicts:
        line += f"; {FAILS}"
    from .proposals import proposal_text
    proposals = [proposal_text(dict(p, model=mid)) for mid, record in models.items()
                 for p in record.get("setting_proposals", [])]
    details = []
    for entry in conflicts:
        details.append(f"OPEN {entry['kind']} {entry['model']}: {entry['text']} [{entry['id']}]")
        if 'code_evidence' in entry:
            from .codeaudit import fact_lines
            details += fact_lines(entry['code_evidence']['route'])
        details += [f'  {rid}: {text}' if rid else '  ' + text for rid, text in request_lines(root, entry.get('sources', []))]
        for state in decision_results(root, entry):
            details.append('  ' + state.get('label', state.get('why', state['outcome'])))
        details.append('  ' + conflict_question(root, entry))
    from .codeaudit import summary
    from .codeaudit import declared_lines
    return [line, *details, *requirement_lines(root,data.get('closed',[])), *declared_lines(data), *summary(root, data.get('code_audit')), *proposals, *platform]


def requirement_summary(root, entry):
    resolution=entry['closure']['resolution']
    changes=resolution['changes']
    old=sorted({source for change in changes for source in change['old']['sources']})
    new={change['authority']['id']:change['authority']['quote'] for change in changes}
    return dict(old=request_lines(root,old),new=sorted(new.items()),code_fixed=False,
                scope_changed=resolution['scope']['before']!=resolution['scope']['after'],
                scope_changes=[row for row in resolution['scope']['changes'] if row['code']=='coverage_removed'])


def requirement_lines(root, entries):
    """Small public projection; finite proof matrices stay in their stored receipt."""
    lines,seen=[],set()
    for entry in entries:
        if entry.get('closure',{}).get('kind')!='requirement_changed':
            continue
        summary=requirement_summary(root,entry)
        key=(entry['model'],repr(summary))
        if key in seen:
            continue
        seen.add(key)
        scope='scope changed' if summary['scope_changed'] else 'scope retained'
        lines.append(f"REQUIREMENT CHANGED {entry['model']}: {scope}; no code-fix claim")
        lines += [f'  old {rid}: {words}' for rid,words in summary['old']]
        lines += [f'  new {rid}: {words}' for rid,words in summary['new']]
    return lines


def decision_results(root, entry):
    """Immutable event references remain evidence in the one conflict record."""
    from .decisions import evaluate_decision
    from ..map.common import MapError
    out = []
    for identifier in entry.get('history', {}).get('decision_refs', []):
        try:
            out.append(evaluate_decision(root, entry, identifier))
        except MapError as error:
            out.append(dict(id=identifier, outcome='invalid', open=True, commit_allowed=False, why=str(error)))
    return out


def conflict_question(root, entry):
    words = request_lines(root, entry.get('sources', []))
    cited = ' | '.join(f'{rid} "{text}"' if rid else text for rid, text in words)
    from .codeaudit import is_entry, question
    if is_entry(entry):
        return entry['id'] + ': ' + question(entry)
    latest=entry.get('history',{}).get('latest') or {}
    if latest.get('outcome')=='requirement_changed':
        choices={change['authority']['id']:change['authority']['quote'] for change in latest['resolution']['changes']}
        replacement=' | '.join(f'{rid} "{quote}"' for rid,quote in sorted(choices.items()))
        return (f"{entry['id']} {entry['subject']}: implement and verify the replacement requirement {replacement}; "
                f"current behavior and executed regression remain required; run {PROG} check {entry['model']}")
    if entry['kind'] in {'STUCK', 'NEVER REACHED'}:
        if (entry.get('native_confirmation') or {}).get('status') == 'confirmed':
            action = ('repair the dead end in code' if entry['kind'] == 'STUCK' else 'make the promised behavior reachable in code')
        else:
            action = 'model-only: check the owner words and actual code; repair the model or code as warranted'
        return f"{entry['id']} {entry['subject']}: {action}; preserve {cited}; then run {PROG} check {entry['model']}"
    if 'DRIFT' in entry['kind'].upper() or entry.get('code_status') == 'drift':
        return f"{entry['id']} {entry['subject']}: reconcile the model and real code; decide cannot settle drift"
    from ..map.requests import owner_quote
    from ..map.common import MapError
    for rid, text in words:
        if not rid:
            continue
        try:
            owner_quote(root, text, entry.get('subject_terms', []), request=rid)
        except MapError:
            continue
        command = shlex.join(['python', '-m', 'flowguard', 'decide', entry['id'], '--owner', text, '--request', rid])
        return f"{entry['id']} {entry['subject']}: which requirement applies? {cited}; record the choice: {command}"
    return (f"{entry['id']} {entry['subject']}: which requirement applies? {cited}; quote stored words naming "
            f"{', '.join(entry.get('subject_terms', [])) or 'this subject'} with {PROG} decide {entry['id']} --owner QUOTE --request ID")


def decide(args, *, out):
    from .decisions import record_decision, current_core
    from ..map.common import MapError
    root = find_root(Path(args.root) if args.root else Path.cwd())
    from .project import require_current_format
    require_current_format(root)
    data = read_conflicts(root)
    entry = next((c for c in (data or {}).get('conflicts', []) if c['id'] == args.conflict), None)
    if entry is None:
        return _early(out, f'no open conflict {args.conflict}; run {PROG} status', EXIT_ERROR, args.json)
    evidence = None
    if args.provisional is not None:
        if entry['kind'] not in {'RULE CONTRADICTION', 'CONTRADICTION'}:
            return _early(out, 'provisional_not_allowed: repair this conflict; only a computed incompatible requested-rule pair qualifies', EXIT_ERROR, args.json)
        try:
            evidence = current_core(root, entry)
        except MapError as error:
            return _early(out, str(error), EXIT_ERROR, args.json)
    try:
        event = record_decision(root, entry, owner=args.owner, request=args.request,
                                provisional=args.provisional, evidence=evidence,
                                purpose='existing_routes' if args.existing_routes else None)
    except MapError as error:
        return _early(out, str(error), EXIT_ERROR, args.json)
    entry.setdefault('history', history.bind(entry, previous=entry)['history'])
    entry['history']['decision_refs'] = sorted(set(entry['history']['decision_refs']) | {event['id']})
    states = decision_results(root, entry)
    result = next((state for state in states if state['id'] == event['id']), {})
    from .codeaudit import apply_declared
    write_conflicts(root, apply_declared(root, data))
    message = f"{event['id']}: {result.get('label', event['mode'])}; conflict remains visible"
    if args.json:
        out.write(json.dumps(dict(exit=0, decision=event, result=result, question=conflict_question(root, entry)), ensure_ascii=False) + '\n')
    else:
        out.write(message + '\n' + conflict_question(root, entry) + '\n')
    return EXIT_CLEAN


def commit_ready_command(root, args, out):
    from .commit_ready import commit_ready
    from .project import staged_models, running_models
    data = read_conflicts(root)
    from .codeaudit import reopen_declared, declared_entries
    data = reopen_declared(root, data)
    affected = staged_models(root, data)
    entries = [*(data or {}).get('conflicts', []), *declared_entries(data)]
    decisions = {c['id']:c.get('history', {}).get('decision_refs', []) for c in entries}
    policy = commit_ready(root, affected, data, entries,
                          running=running_models(root), decisions=decisions, closed=(data or {}).get('closed', []))
    policy['affected'] = affected
    policy['exit'] = EXIT_CLEAN if policy['ready'] else EXIT_CONFLICT
    if args.json:
        out.write(json.dumps(policy, ensure_ascii=False, sort_keys=True) + '\n')
    else:
        out.write('commit ready\n' if policy['ready'] else 'commit not ready\n')
        for reason in policy['reasons']:
            out.write('  ' + reason['code'] + ': ' + reason.get('model', '') +
                      (' ' + reason.get('conflict', '') if reason.get('conflict') else '') +
                      (' ' + ', '.join(reason['paths']) if reason.get('paths') else '') + '\n')
        if policy['unknown']:
            out.write('  finished UNKNOWN: ' + ', '.join(policy['unknown']) + '\n')
    return policy['exit']


def refresh_status(root, *, wait=DEFAULT_WAIT, err=None):
    """Use the existing cache/plan/wait route for changed or never-checked models."""
    import io
    problem = jobs.platform_problem()
    if problem is not None:
        return dict(refreshed=[], exit=EXIT_ERROR, unsupported=problem)
    from .project import legacy_artifacts
    legacy = legacy_artifacts(root)
    if legacy:
        return dict(refreshed=[], exit=EXIT_UNKNOWN, upgrade=[path.relative_to(root).as_posix() for path in legacy])
    previous = read_conflicts(root)
    from .codeaudit import reopen_declared
    reopened = reopen_declared(root, previous)
    if reopened != previous:
        write_conflicts(root, reopened)
        previous = reopened
    paths = []
    for path in model_files(root):
        saved = jobs.saved_core(root, path.stem, previous)
        bound = (jobs.Planned.from_json(saved['planned']).spec.option('max_states', Bounds().max_states)
                 if saved is not None else Bounds().max_states)
        planned = jobs.plan(root, [path], stored=previous, max_states=bound)
        if any(jobs.lookup(root, item) is None for item in planned):
            paths.append(path)
    if not paths:
        return dict(refreshed=[], exit=EXIT_CLEAN)
    argv = ['check', *(p.stem for p in paths), '--root', str(root), '--wait', str(wait), '--json']
    output = io.StringIO()
    code = check(parser().parse_args(argv), argv, out=output, err=err)
    result = json.loads(output.getvalue())
    return dict(refreshed=[p.stem for p in paths], exit=code, running=result.get('running'), resume=result.get('resume'))


def public_finding(finding):
    data = finding.to_json()
    data['detail'].pop('entry', None)
    return data
