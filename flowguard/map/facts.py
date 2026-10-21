"""Code binding: the real code a model names, and whether the model consulted it.

Every model names the code it is about in ``IMPLEMENTED_BY`` (``"path:Symbol"``).
Two cheap facts bind the model to that code:

* each anchor resolves (``flowguard.map.check.anchor_problems``: a file and
  symbol lookup, nothing is executed);
* while the model runs, each anchor is consulted: its Python symbol is called
  (replay) or its file is read (code facts).  ``AnchorWatch`` sees both through
  ``sys.settrace`` call events and the interpreter's ``open`` audit events.
  Opening a file in order to import it is not a read.

``CodeFacts`` is the small static reader a model's ``conformance()`` uses to
compare the model with the code: anchors exist, a word is present in or absent
from files.  Words match whole identifiers; comments and strings count.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .check import anchor_problems

_ACTIVE: list["AnchorWatch"] = []          # the watch that records reads right now (innermost last)
_HOOKED = False


def _module_files() -> set[str]:
    return {os.path.realpath(f) for m in list(sys.modules.values())
            if isinstance(f := getattr(m, "__file__", None), str)}


def _on_audit(event: str, args: tuple) -> None:
    if event != "open" or not _ACTIVE or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    watch = _ACTIVE[-1]
    if watch._busy:
        return
    watch._busy = True
    try:
        real = os.path.realpath(os.fsdecode(args[0]))
        if real in watch._files:
            watch._opened.add(real)
    finally:
        watch._busy = False


class AnchorWatch:
    """Which IMPLEMENTED_BY anchors a model consulted while it ran: called (Python) or read (any file)."""

    def __init__(self, root: str | Path, anchors: Iterable[str]) -> None:
        self.anchors = sorted(set(anchors))
        self._symbols: dict[str, dict[str, str]] = {}    # real path -> {symbol: anchor}, Python only
        self._files: dict[str, set[str]] = {}            # real path -> anchors in that file
        for anchor in self.anchors:
            rel, _, symbol = anchor.partition(":")
            real = os.path.realpath(Path(root) / rel)
            self._files.setdefault(real, set()).add(anchor)
            if rel.endswith(".py"):
                self._symbols.setdefault(real, {})[symbol] = anchor
        self.called: set[str] = set()
        self.read_files: set[str] = set()
        self._opened: set[str] = set()
        self._by_code: dict[str, dict[str, str]] = {}
        self._busy = False

    def _trace(self, frame, event, arg):
        if event != "call":
            return None
        code = frame.f_code
        symbols = self._by_code.get(code.co_filename)
        if symbols is None:
            symbols = self._by_code[code.co_filename] = self._symbols.get(os.path.realpath(code.co_filename), {})
        if symbols:
            qualname = code.co_qualname
            for symbol, anchor in symbols.items():
                if qualname == symbol or ("." not in symbol and qualname.startswith(symbol + ".")):
                    self.called.add(anchor)
        return None                       # never trace lines

    def __enter__(self) -> "AnchorWatch":
        global _HOOKED
        if not self._files:
            return self
        if not _HOOKED:
            sys.addaudithook(_on_audit)
            _HOOKED = True
        self._before = _module_files()
        self._opened = set()
        _ACTIVE.append(self)
        self._previous = sys.gettrace()
        self._previous_thread = threading.gettrace()
        if self._symbols:
            sys.settrace(self._trace)
            threading.settrace(self._trace)
        return self

    def __exit__(self, *exc) -> None:
        if not self._files:
            return
        if self._symbols:
            sys.settrace(self._previous)
            threading.settrace(self._previous_thread)
        _ACTIVE.remove(self)
        imported = _module_files() - self._before         # opened only to be imported: not a read
        self.read_files |= {f for f in self._opened if f not in imported}

    def consulted(self) -> set[str]:
        return self.called | {a for f in self.read_files for a in self._files.get(f, ())}

    def missing(self) -> list[str]:
        """Python anchors that were neither called nor read."""
        done = self.consulted()
        return sorted(a for a in self.anchors if a.partition(":")[0].endswith(".py") and a not in done)

    def unobserved(self) -> list[str]:
        """Non-Python anchors that were not read (their execution cannot be observed in-process)."""
        done = self.consulted()
        return sorted(a for a in self.anchors if not a.partition(":")[0].endswith(".py") and a not in done)


@dataclass(frozen=True)
class Fact:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class CodeFactsReport:
    """Conformance report of static code facts; ``ok`` needs at least one fact and no failed fact."""

    facts: tuple[Fact, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.facts) and all(fact.ok for fact in self.facts)

    @property
    def violations(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if not fact.ok)

    def format_text(self, max_examples: int | None = None) -> str:
        shown = self.violations[:max_examples] if max_examples else self.violations
        lines = [f"code facts: {len(self.facts) - len(self.violations)} of {len(self.facts)} hold"
                 + ("" if self.facts else " (no fact was checked)")]
        lines += [f"- {fact.name}: {fact.detail}" for fact in shown]
        return "\n".join(lines)


def _word(word: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])")


class CodeFacts:
    """Read the real code statically and record facts that a model's conformance() compares with the model."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path.cwd()
        self.facts: list[Fact] = []

    def text(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8", errors="replace")

    def references(self, word: str, paths: Iterable[str]) -> list[str]:
        """'path:line' of every whole-identifier occurrence of word in the files."""
        pattern, hits = _word(word), []
        for path in paths:
            if (self.root / path).is_file():
                hits += [f"{path}:{n}" for n, line in enumerate(self.text(path).splitlines(), 1) if pattern.search(line)]
        return hits

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.facts.append(Fact(name, bool(ok), "" if ok else detail))
        return bool(ok)

    def anchors_exist(self, anchors: Mapping[str, str] | Iterable[str]) -> bool:
        """Each 'path:Symbol' names a real file and symbol (its file is read)."""
        names = list(anchors.values()) if isinstance(anchors, Mapping) else list(anchors)
        problems = anchor_problems(self.root, names)
        for anchor in names:
            if anchor not in problems and not anchor.partition(":")[0].endswith(".py"):
                self.text(anchor.partition(":")[0])
            self.check(f"anchor {anchor} exists", anchor not in problems, problems.get(anchor, ""))
        return not problems

    def present(self, word: str, paths: Iterable[str], name: str = "") -> bool:
        """word occurs (as a whole identifier) in at least one of the files."""
        paths = list(paths)
        return self.check(name or f"{word} is present", bool(self.references(word, paths)),
                          f"{word!r} not found in {', '.join(paths) or '(no files)'}")

    def absent(self, word: str, paths: Iterable[str], name: str = "") -> bool:
        """word occurs nowhere in the files (for example a removed field)."""
        paths = list(paths)
        missing = [p for p in paths if not (self.root / p).is_file()]
        hits = self.references(word, paths)
        return self.check(name or f"{word} is absent", not hits and not missing,
                          f"still referenced at {', '.join(hits[:5])}" if hits else f"files missing: {', '.join(missing)}")

    def report(self) -> CodeFactsReport:
        return CodeFactsReport(tuple(self.facts))


def load_anchor(anchor: str, root: str | Path | None = None):
    """Import the object an anchor names ('path/to/module.py:Name' or ':Class.method') for replay."""
    import importlib
    import importlib.util

    from .check import PLACEHOLDER_ANCHOR

    path, _, symbol = anchor.partition(":")
    if PLACEHOLDER_ANCHOR in anchor or not path.endswith(".py") or not symbol:
        raise ValueError(f"placeholder anchor {anchor!r}: replace it with the real 'path:Symbol' this model is about"
                         if PLACEHOLDER_ANCHOR in anchor else f"anchor {anchor!r} must look like 'path/to/module.py:Name'")
    dotted = path[:-3].replace("/", ".").removesuffix(".__init__")
    module = None
    for name in (dotted, dotted.removeprefix("src.")):
        try:
            module = importlib.import_module(name)
            break
        except ModuleNotFoundError as exc:
            if exc.name is None or not name.startswith(exc.name):
                raise
    if module is None:
        spec = importlib.util.spec_from_file_location(f"_flowguard_anchor_{dotted}", Path(root or Path.cwd()) / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    value = module
    for part in symbol.split("."):
        value = getattr(value, part)
    return value


__all__ = ["AnchorWatch", "CodeFacts", "CodeFactsReport", "Fact", "load_anchor"]
