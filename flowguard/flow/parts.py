"""Parts: the unit of work the job system runs and caches. A part is (kind, model,
options); its digest covers the engine, the options and every file the model's load read."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .checks import ERROR_CLS, UNDECIDED, check_model, make_finding, reach_line, replay_conflict, verify_symmetry
from .explore import Bounds
from .model import ModelError, load_model
from .project import file_digest

_PKG = Path(__file__).resolve().parent


def _engine_digest() -> str:
    h = hashlib.sha256()
    for path in sorted(x for x in _PKG.rglob("*") if x.suffix in (".py", ".js")):   # .js: the picture renderer
        h.update(path.relative_to(_PKG).as_posix().encode() + b"\0")
        h.update(path.read_bytes() + b"\0")
    h.update(f"python {sys.version_info.major}.{sys.version_info.minor}".encode())
    return h.hexdigest()


ENGINE_DIGEST: str = _engine_digest()


@dataclass(frozen=True)
class PartSpec:
    kind: str
    model: str
    options: tuple = ()              # ((name, value), ...), e.g. (("max_states", 200000),)

    def option(self, name, default):
        return dict(self.options).get(name, default)


@dataclass
class PartResult:
    kind: str
    model: str
    digest: str
    complete: bool
    findings: list                   # Finding.to_json() dicts
    info: dict
    reads: list
    writes: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {"kind": self.kind, "model": self.model, "digest": self.digest, "complete": self.complete,
                "findings": self.findings, "info": self.info, "reads": self.reads, "writes": self.writes}

    @staticmethod
    def from_json(d: dict) -> "PartResult":
        return PartResult(d["kind"], d["model"], d["digest"], d["complete"], d["findings"], d["info"],
                          d["reads"], d["writes"])


@dataclass
class PartContext:
    root: Path
    spec: PartSpec
    path: Path                       # the model file
    cache: Path                      # .flowguard/cache/flow
    progress: Callable[[dict], None] = lambda info: None


_REGISTRY: dict[str, tuple[Callable[[PartContext], PartResult], str]] = {}
PART_MODULES = ("routes", "mutate", "diagram")   # register their part kinds when imported (after core)
_PLANNED, _FULL_ONLY, _ON_REQUEST = "check", "full", "request"


def register(kind: str, fn: Callable[[PartContext], PartResult], *, full_only: bool = False,
             on_request: bool = False) -> None:
    """A part kind: planned by every check, only by `check --full` (full_only), or never by a
    check, only when a command asks for it by name (on_request: `show`'s pictures)."""
    if kind in _REGISTRY:
        raise ValueError(f"part kind {kind!r} is registered twice")
    _REGISTRY[kind] = (fn, _ON_REQUEST if on_request else _FULL_ONLY if full_only else _PLANNED)


def _registry() -> dict:
    """Every part kind: the part modules import this one, so it imports them on first use."""
    for name in PART_MODULES:
        importlib.import_module(f"{__package__}.{name}")
    return _REGISTRY


def _rank(kind: str) -> int:
    """core first, then the part modules in PART_MODULES order (whatever imported first)."""
    module = _REGISTRY[kind][0].__module__.rpartition(".")[2]
    return PART_MODULES.index(module) + 1 if module in PART_MODULES else 0


def kinds(full: bool = False) -> list[str]:
    """The part kinds a check plans for each model (full_only kinds only with --full)."""
    allowed = (_PLANNED, _FULL_ONLY) if full else (_PLANNED,)
    return sorted((k for k, (_, when) in _registry().items() if when in allowed), key=_rank)


def run_part(ctx: PartContext) -> PartResult:
    """Run one part in this process (the worker and the tests call this)."""
    fn, _ = _registry()[ctx.spec.kind]
    return fn(ctx)


def part_digest(root: Path, spec: PartSpec, reads: list[str]) -> str:
    """sha256 of the engine, the part kind, its options and the content of every read file."""
    data = [ENGINE_DIGEST, spec.kind, spec.model, sorted([list(o) for o in spec.options], key=repr),
            [[rel, file_digest(root, rel)] for rel in sorted(set(reads))]]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=repr).encode("utf-8")).hexdigest()


def core_part(ctx: PartContext) -> PartResult:
    """Load, explore, run the prepared checks with their explanations. With the option
    verify_symmetry (check --full) the model is also explored without renaming and the
    fingerprints compared. The digest is taken right after the load, so it names the file
    contents the run used even if a file changes while it explores."""
    root, spec = Path(ctx.root), ctx.spec
    max_states = spec.option("max_states", Bounds().max_states)
    try:
        loaded = load_model(ctx.path, root)
    except ModelError as err:
        reads = list(err.reads)
        subject = f"{err.where()}: {err.text}" if err.where() else err.text
        finding = make_finding("MODEL ERROR", ERROR_CLS, spec.model, subject, err.text,
                               detail={"file": err.file}, line=err.line)
        return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), True, [finding.to_json()],
                          {"loaded": False}, sorted(reads), [])
    reads = list(loaded.reads)
    digest = part_digest(root, spec, reads)
    report = check_model(loaded, Bounds(max_states),
                         progress=lambda d: ctx.progress({"model": spec.model, "kind": spec.kind, **d}))
    model = loaded.model
    info = {"loaded": True, "reach": report.reach, "reach_line": reach_line(report.reach),
            "holds": [list(h) for h in report.holds], "unknown": list(report.unknown),
            "seconds": round(report.graph.seconds, 3), "covers": list(model.covers),
            "families": sorted({f.family for f in model.fields}),
            "objects": {kind: list(ids) for kind, ids in model.kinds.items()},
            "reached": list(report.reached)}
    findings = list(report.findings)
    if spec.option("verify_symmetry", False):
        sym = verify_symmetry(loaded, Bounds(max_states), report)
        info["symmetry"] = {"verified": sym["verified"], "text": sym["text"]}
        if sym["finding"] is not None:
            findings.append(sym["finding"])
    from .diagram import conflict_pictures              # diagram imports this module
    pictures = conflict_pictures(report, root)          # <model>-<fingerprint>.mmd/.svg/.png per conflict
    writes = sorted({w for _, _, files in pictures for w in files})
    return PartResult(spec.kind, spec.model, digest, report.graph.complete,
                      [f.to_json() for f in findings], info, reads, writes)


register("core", core_part)


def replay_part(ctx: PartContext) -> PartResult:
    """The conflicts conflicts.json keeps for this model, each replayed along its stored
    shrunk path on the model as it is now (option stored: the JSON of their entries). Only
    a capped check uses the outcome, to say why each kept conflict is still open; it closes
    none: only a complete check of the model that no longer finds a conflict closes it."""
    root, spec = Path(ctx.root), ctx.spec
    entries = json.loads(spec.option("stored", "[]"))
    bounds = Bounds(spec.option("max_states", Bounds().max_states))
    try:
        loaded = load_model(ctx.path, root)
    except ModelError as err:                   # nothing replays a model that does not load
        reads = sorted(err.reads)
        return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), True, [],
                          {"replays": {e["id"]: [UNDECIDED, "the model does not load"] for e in entries}}, reads, [])
    reads = list(loaded.reads)
    digest = part_digest(root, spec, reads)
    replays = {e["id"]: list(replay_conflict(loaded.model, e, bounds)) for e in entries}
    return PartResult(spec.kind, spec.model, digest, True, [], {"replays": replays}, reads, [])


register("replay", replay_part, on_request=True)
