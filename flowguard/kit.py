"""Model kits: build a complete FlowGuard model from a concern's cases or edits and an existing review.

Every model has the same five abilities: a state model, counterexamples from
bounded exploration, known-bad variants that must fail, a binding to the real
code (anchors plus conformance) and a binding to tests.  Two generic shapes
give a capability or a self-model all five with little code:

* **Case table** - the input universe is a finite set of named cases, each with
  the verdict the design expects (accepted or rejected, and the finding codes a
  rejection must report).  ``case_table_explorer`` explores every case;
  ``case_table_variants`` returns the known-bad designs that accept every case
  and reject every case; ``case_table_conformance`` runs each case against the
  real code through a small ``observe(case)`` adapter and compares.
* **Plan edits** - the state is a capability plan reached by named edits, and
  an existing review (``review_field_lifecycle``, ``review_ui_interaction_model``,
  ...) is the invariant every reachable plan must pass (``plan_explorer``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from .core import FunctionResult, Invariant, InvariantResult
from .explorer import Explorer
from .workflow import Workflow


@dataclass(frozen=True)
class Case:
    """One named input of a case table and the verdict the design expects for it."""

    name: str
    accept: bool
    codes: tuple[str, ...] = ()          # finding codes the real code must report when it rejects

    def __post_init__(self) -> None:
        object.__setattr__(self, "codes", tuple(self.codes))


class _Verdict:
    """Function block: give the verdict of one case (design: the table; known-bad: always accept or reject)."""

    name = "Verdict"
    reads = ("verdicts",)
    writes = ("verdicts",)

    def __init__(self, cases: Sequence[Case], mode: str) -> None:
        self.cases = {case.name: case for case in cases}
        self.mode = mode

    def apply(self, name: str, verdicts: tuple):
        accepted = self.cases[name].accept if self.mode == "design" else self.mode == "accept"
        output = "accepted" if accepted else "rejected"
        return (FunctionResult(output, verdicts + ((name, accepted),), label=f"{name}:{output}"),)


def _verdict_invariant(cases: Sequence[Case]) -> Invariant:
    expected = {case.name: case.accept for case in cases}

    def check(verdicts: tuple, trace) -> InvariantResult:
        wrong = [name for name, accepted in verdicts if accepted != expected[name]]
        if wrong:
            return InvariantResult.fail(f"verdict differs from the case table for {', '.join(wrong)}")
        return InvariantResult.pass_()

    return Invariant("verdict_matches_case", "every case gets the verdict the case table expects", check)


def case_table_explorer(cases: Sequence[Case], *, mode: str = "design") -> Explorer:
    """Explore every case once; mode 'accept' or 'reject' builds the known-bad designs."""
    cases = tuple(cases)
    if not cases or len({case.name for case in cases}) != len(cases):
        raise ValueError("a case table needs at least one case and unique case names")
    return Explorer(workflow=Workflow((_Verdict(cases, mode),)), initial_states=((),),
                    external_inputs=tuple(case.name for case in cases), invariants=(_verdict_invariant(cases),),
                    max_sequence_length=1, progress_steps=0)


def case_table_variants(cases: Sequence[Case]) -> dict[str, Explorer]:
    """Known-bad designs: one that accepts every case (needs a rejected case), one that rejects every case."""
    variants = {}
    if any(not case.accept for case in cases):
        variants["accepts_every_case"] = case_table_explorer(cases, mode="accept")
    if any(case.accept for case in cases):
        variants["rejects_every_case"] = case_table_explorer(cases, mode="reject")
    return variants


@dataclass(frozen=True)
class CaseResult:
    case: str
    expected: str                         # accepted | rejected
    observed: str                         # accepted | rejected | declared only | error
    ok: bool
    message: str = ""
    rule_name: str = "case_verdict"


@dataclass(frozen=True)
class CaseTableReport:
    """Conformance of a case table: each case executed against the real code and compared with the model."""

    results: tuple[CaseResult, ...] = ()

    @property
    def executed(self) -> int:
        return sum(result.observed in {"accepted", "rejected"} for result in self.results)

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(result.ok for result in self.results)

    @property
    def violations(self) -> tuple[CaseResult, ...]:
        return tuple(result for result in self.results if not result.ok)

    def format_text(self, max_examples: int | None = None) -> str:
        declared = sum(result.observed == "declared only" for result in self.results)
        lines = [f"executed against code: {self.executed} of {len(self.results)} cases; "
                 f"declared only: {declared}; disagree with the model: {len(self.violations)}"]
        shown = self.violations[:max_examples] if max_examples else self.violations
        lines += [f"- {r.case}: expected {r.expected}, observed {r.observed}" + (f" ({r.message})" if r.message else "")
                  for r in shown]
        return "\n".join(lines)


def case_table_conformance(cases: Sequence[Case], observe: Callable[[Case], Any]) -> CaseTableReport:
    """Run every case against the real code.

    ``observe(case)`` executes the case and returns ``True`` (accepted), ``False``
    (rejected) or ``(accepted, codes)``; it returns ``None`` when it cannot build
    the case, which leaves the case declared only and fails conformance.
    """
    results = []
    for case in cases:
        expected = "accepted" if case.accept else "rejected"
        try:
            value = observe(case)
        except Exception as exc:  # noqa: BLE001 - an adapter crash is a reported disagreement
            results.append(CaseResult(case.name, expected, "error", False, f"{type(exc).__name__}: {exc}",
                                      rule_name="adapter_exception"))
            continue
        if value is None:
            results.append(CaseResult(case.name, expected, "declared only", False,
                                      "no input was built; extend the adapter or remove the case from the model"))
            continue
        accepted, codes = (value if isinstance(value, tuple) else (value, ()))
        observed = "accepted" if accepted else "rejected"
        missing = [code for code in case.codes if code not in set(codes)]
        message = f"missing finding codes: {', '.join(missing)}" if missing and observed == expected else ""
        results.append(CaseResult(case.name, expected, observed, observed == expected and not missing, message))
    return CaseTableReport(tuple(results))


@dataclass(frozen=True)
class PlanState:
    """State of a plan-edit model: the edits applied so far (the plan itself is rebuilt from them)."""

    edits: tuple[str, ...] = ()


class _PlanEdit:
    name = "PlanEdit"
    reads = ("edits",)
    writes = ("edits",)

    def apply(self, edit: str, state: PlanState):
        return (FunctionResult(edit, PlanState(state.edits + (edit,)), label=edit),)


def review_invariant(name: str, review: Callable[[Any], Any], plan_of: Callable[[Any], Any] | None = None,
                     description: str = "") -> Invariant:
    """An existing capability review used as a model invariant: every reachable plan must pass it."""

    def check(state, trace) -> InvariantResult:
        report = review(plan_of(state) if plan_of else state)
        if getattr(report, "ok", False):
            return InvariantResult.pass_()
        codes = [getattr(finding, "code", "") for finding in getattr(report, "findings", ())]
        return InvariantResult.fail(f"the review rejects the plan: {', '.join(c for c in codes[:5] if c) or 'not ok'}")

    return Invariant(name, description or f"{name}: the capability review accepts every reachable plan", check)


def plan_explorer(initial: Callable[[], Any], edits: Mapping[str, Callable[[Any], Any]], review: Callable[[Any], Any],
                  *, explore: Sequence[str] | None = None, invariant_name: str = "review_accepts_plan",
                  max_sequence_length: int = 2, extra_invariants: Iterable[Invariant] = ()) -> Explorer:
    """Explore every sequence of the named edits in ``explore`` (default: all) from the initial plan.

    The review must accept every plan reached.  Give the design and its known-bad variants the same
    ``edits`` mapping and different ``explore`` lists, so each can rebuild the other's plans.
    """
    edits = dict(edits)
    cache: dict[tuple, Any] = {}

    def plan_of(state: PlanState):
        if state.edits not in cache:
            plan = initial()
            for edit in state.edits:
                plan = edits[edit](plan)
            cache[state.edits] = plan
        return cache[state.edits]

    invariants = (review_invariant(invariant_name, review, plan_of), *extra_invariants)
    return Explorer(workflow=Workflow((_PlanEdit(),)), initial_states=(PlanState(),),
                    external_inputs=tuple(edits if explore is None else explore),
                    invariants=invariants, max_sequence_length=max_sequence_length, progress_steps=0)


__all__ = ["Case", "CaseResult", "CaseTableReport", "PlanState", "case_table_conformance", "case_table_explorer",
           "case_table_variants", "plan_explorer", "review_invariant"]
