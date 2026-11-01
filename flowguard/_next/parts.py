"""Parts: the unit of work the job system runs and caches. A part is (kind, model,
options); its digest covers the engine, the options and every file the model's load read."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .checks import ERROR_CLS, check_model, make_finding, reach_line
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


_REGISTRY: dict[str, tuple[Callable[[PartContext], PartResult], bool]] = {}


def register(kind: str, fn: Callable[[PartContext], PartResult], *, full_only: bool = False) -> None:
    if kind in _REGISTRY:
        raise ValueError(f"part kind {kind!r} is registered twice")
    _REGISTRY[kind] = (fn, full_only)


def kinds(full: bool = False) -> list[str]:
    """The part kinds a plan runs for each model (full_only kinds only with --full)."""
    return [k for k, (_, only_full) in _REGISTRY.items() if full or not only_full]


def run_part(ctx: PartContext) -> PartResult:
    """Run one part in this process (the worker and the tests call this)."""
    fn, _ = _REGISTRY[ctx.spec.kind]
    return fn(ctx)


def part_digest(root: Path, spec: PartSpec, reads: list[str]) -> str:
    """sha256 of the engine, the part kind, its options and the content of every read file."""
    data = [ENGINE_DIGEST, spec.kind, spec.model, sorted([list(o) for o in spec.options], key=repr),
            [[rel, file_digest(root, rel)] for rel in sorted(set(reads))]]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=repr).encode("utf-8")).hexdigest()


def core_part(ctx: PartContext) -> PartResult:
    """Load, explore, run the prepared checks with their explanations."""
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
    report = check_model(loaded, Bounds(max_states),
                         progress=lambda d: ctx.progress({"model": spec.model, "kind": spec.kind, **d}))
    info = {"loaded": True, "reach": report.reach, "reach_line": reach_line(report.reach),
            "holds": [list(h) for h in report.holds], "unknown": list(report.unknown),
            "seconds": round(report.graph.seconds, 3)}
    reads = list(loaded.reads)
    return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.graph.complete,
                      [f.to_json() for f in report.findings], info, reads, [])


register("core", core_part)
