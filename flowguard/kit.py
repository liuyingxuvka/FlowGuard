"""Model kits: build a complete FlowGuard model from a concern's features or edits and an existing review.

Every model has the same five abilities: a state model, counterexamples from
bounded exploration, known-bad variants that must fail, a binding to the real
code (anchors plus conformance) and a binding to tests.  Two generic shapes
give a capability or a self-model all five with little code:

* **Features** - a feature is one named property of an input (``Feature``): a
  rejecting feature is a defect the code must reject and report, a benign
  feature is a variation that must not change the verdict, and ``apply``
  changes a clean base input to have the property.  The state is the set of
  applied features; exploration reaches every single feature and every pair
  (``max_features=2``).  The design rejects exactly when a rejecting feature
  is present and reports the codes of all of them.  The kit owns four
  invariants (``clean_input_accepted``, ``each_defect_rejected``,
  ``every_defect_reported``, ``benign_features_neutral``) and generates the
  known-bad variants (``feature_variants``).  ``feature_conformance`` explores
  the same universe on the real code: it builds each input from the clean base,
  runs the real review and reports a counterexample trace (the feature
  sequence, the expected and the observed verdict) for every combination that
  breaks an invariant or differs from the design.
* **Plan edits** - the state is a capability plan reached by named edits, and
  existing reviews (``review_field_lifecycle``, ``review_code_structure_recommendation``
  and ``review_structure_mesh``, ...) are the invariants every reachable plan must
  pass (``plan_explorer``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from .core import FunctionResult, Invariant, InvariantResult
from .explorer import Explorer
from .workflow import Workflow

ACCEPTED, REJECTED, DECLARED_ONLY, ERROR = "accepted", "rejected", "declared only", "error"
FEATURE_INVARIANTS = ("clean_input_accepted", "each_defect_rejected", "every_defect_reported",
                      "benign_features_neutral")


@dataclass(frozen=True)
class Feature:
    """One named property of an input.

    ``rejects`` marks a defect the real code must reject, reporting ``codes``; a benign feature is a
    variation that must not change the verdict.  ``apply(plan)`` returns the clean base input changed to
    have this property.  An ``exclusive`` feature cannot be combined with the others (for example it
    removes what they change); it is explored alone.  Use it rarely and say why.
    """

    name: str
    rejects: bool
    codes: tuple[str, ...] = ()
    apply: Callable[[Any], Any] | None = field(default=None, compare=False)
    exclusive: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "codes", tuple(self.codes))
        if self.codes and not self.rejects:
            raise ValueError(f"benign feature {self.name!r} cannot report finding codes")


@dataclass(frozen=True)
class FeatureState:
    """State of a feature model: the applied features (declaration order) and the verdict on that input.

    ``codes`` holds the reported codes that belong to the model's features; ``plain_*`` is the verdict on
    the same input without its benign features (``benign_features_neutral`` compares the two).
    """

    features: tuple[str, ...] = ()
    outcome: str = ACCEPTED                      # accepted | rejected | declared only | error
    codes: frozenset = frozenset()
    plain_outcome: str = ACCEPTED
    plain_codes: frozenset = frozenset()


def _verdict(outcome: str, codes) -> str:
    return f"{outcome} [{', '.join(sorted(codes))}]" if codes else outcome


class _Universe:
    """The features of one model, the design verdict and the kit's invariants."""

    def __init__(self, features: Sequence[Feature], max_features: int) -> None:
        self.features = tuple(features)
        names = [feature.name for feature in self.features]
        if not names or len(set(names)) != len(names):
            raise ValueError("a feature model needs at least one feature and unique feature names")
        if max_features < 1:
            raise ValueError("max_features must be at least 1")
        self.by_name = {feature.name: feature for feature in self.features}
        self.order = {name: index for index, name in enumerate(names)}
        self.max_features = max_features
        self.vocabulary = frozenset(code for feature in self.features for code in feature.codes)

    def ordered(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted(set(names), key=self.order.__getitem__))

    def rejecting(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names if self.by_name[name].rejects)

    def expected(self, names: tuple[str, ...]) -> tuple[str, frozenset]:
        """The design verdict: rejected iff a rejecting feature is present, with all of their codes."""
        rejecting = self.rejecting(names)
        return (REJECTED if rejecting else ACCEPTED), frozenset(c for n in rejecting for c in self.by_name[n].codes)

    def add(self, names: tuple[str, ...], name: str) -> tuple[str, ...] | None:
        """The feature set after adding ``name``; None when it is present, exclusive or the bound is reached."""
        if name in names or len(names) >= self.max_features:
            return None
        if names and (self.by_name[name].exclusive or any(self.by_name[n].exclusive for n in names)):
            return None
        return self.ordered(names + (name,))

    def state(self, names: tuple[str, ...], judge: Callable[[tuple[str, ...]], tuple[str, frozenset]]) -> FeatureState:
        outcome, codes = judge(names)
        plain = self.rejecting(names)
        plain_outcome, plain_codes = (outcome, codes) if plain == names else judge(plain)
        return FeatureState(names, outcome, frozenset(codes), plain_outcome, frozenset(plain_codes))

    def invariants(self) -> tuple[Invariant, ...]:
        def judged(state: FeatureState) -> bool:
            return state.outcome in (ACCEPTED, REJECTED)

        def where(state: FeatureState) -> str:
            return " + ".join(state.features) or "clean input"

        def clean_input_accepted(state: FeatureState, trace) -> InvariantResult:
            if judged(state) and not self.rejecting(state.features) and state.outcome != ACCEPTED:
                return InvariantResult.fail(f"{where(state)}: no defect is present, but the input is rejected")
            return InvariantResult.pass_()

        def each_defect_rejected(state: FeatureState, trace) -> InvariantResult:
            defects = self.rejecting(state.features)
            if judged(state) and defects and state.outcome != REJECTED:
                return InvariantResult.fail(f"{where(state)}: defect {', '.join(defects)} is accepted")
            return InvariantResult.pass_()

        def every_defect_reported(state: FeatureState, trace) -> InvariantResult:
            missing = sorted(self.expected(state.features)[1] - state.codes)
            if state.outcome == REJECTED and missing:
                return InvariantResult.fail(f"{where(state)}: the rejection does not report {', '.join(missing)}")
            return InvariantResult.pass_()

        def benign_features_neutral(state: FeatureState, trace) -> InvariantResult:
            if (judged(state) and state.plain_outcome in (ACCEPTED, REJECTED)
                    and (state.outcome, state.codes) != (state.plain_outcome, state.plain_codes)):
                return InvariantResult.fail(f"{where(state)}: the benign features change the verdict from "
                                            f"{_verdict(state.plain_outcome, state.plain_codes)} to "
                                            f"{_verdict(state.outcome, state.codes)}")
            return InvariantResult.pass_()

        checks = (clean_input_accepted, each_defect_rejected, every_defect_reported, benign_features_neutral)
        descriptions = ("an input with no defect is accepted", "an input with any defect is rejected",
                        "a rejection reports the codes of every defect present (no masking)",
                        "removing the benign features does not change the verdict")
        return tuple(Invariant(check.__name__, text, check) for check, text in zip(checks, descriptions))

    def explorer(self, judge, extra_invariants: Iterable[Invariant] = ()) -> Explorer:
        return Explorer(workflow=Workflow((_AddFeature(self, judge),)), initial_states=(self.state((), judge),),
                        external_inputs=tuple(feature.name for feature in self.features),
                        invariants=self.invariants() + tuple(extra_invariants),
                        max_sequence_length=self.max_features, progress_steps=0)


class _AddFeature:
    """Function block: add one feature to the input and give the verdict on the result."""

    name = "AddFeature"
    reads = ("features",)
    writes = ("features", "outcome", "codes")

    def __init__(self, universe: _Universe, judge) -> None:
        self.universe = universe
        self.judge = judge

    def apply(self, name: str, state: FeatureState):
        names = self.universe.add(state.features, name)
        if names is None:
            return (FunctionResult("not combined", state, label=f"{name}:not combined"),)
        new = self.universe.state(names, self.judge)
        return (FunctionResult(new.outcome, new, label=f"{name}:{new.outcome}"),)


def feature_explorer(features: Sequence[Feature], *, max_features: int = 2) -> Explorer:
    """The intended design: explore every single feature and every pair (up to ``max_features``)."""
    universe = _Universe(features, max_features)
    return universe.explorer(universe.expected)


def feature_variants(features: Sequence[Feature], *, max_features: int = 2) -> dict[str, Explorer]:
    """Generated known-bad designs; each must fail the kit's invariants.

    ``ignores_<first rejecting feature>`` accepts that defect. ``reports_first_defect_only`` needs a
    reachable ordered defect pair whose later feature adds a code absent from the earlier one; only
    then can reporting the first defect actually mask a code. ``rejects_<first benign feature>`` treats
    that variation as a defect.
    """
    universe = _Universe(features, max_features)
    rejecting = [feature for feature in universe.features if feature.rejects]
    benign = [feature for feature in universe.features if not feature.rejects]
    variants: dict[str, Explorer] = {}
    if rejecting:
        ignored = rejecting[0].name
        variants[f"ignores_{ignored}"] = universe.explorer(
            lambda names: universe.expected(tuple(name for name in names if name != ignored)))
    if any(universe.add((earlier.name,), later.name) is not None
           and bool(set(later.codes) - set(earlier.codes))
           for index, earlier in enumerate(rejecting)
           for later in rejecting[index + 1:]):
        def first_only(names):
            outcome, _codes = universe.expected(names)
            first = next(iter(universe.rejecting(names)), None)
            return outcome, frozenset(universe.by_name[first].codes) if first else frozenset()

        variants["reports_first_defect_only"] = universe.explorer(first_only)
    if benign:
        loud = benign[0].name
        variants[f"rejects_{loud}"] = universe.explorer(
            lambda names: (REJECTED, universe.expected(names)[1]) if loud in names else universe.expected(names))
    return variants


@dataclass(frozen=True)
class FeatureViolation:
    """One counterexample of a feature conformance run (or an input the adapter could not build or run)."""

    rule_name: str
    features: tuple[str, ...]          # the feature sequence that reached the input
    expected: str
    observed: str
    message: str = ""

    def format_text(self) -> str:
        note = f" ({self.message})" if self.message else ""
        return (f"- {self.rule_name}: {' + '.join(self.features) or 'clean input'}: "
                f"expected {self.expected}, observed {self.observed}{note}")


@dataclass(frozen=True)
class FeatureReport:
    """Conformance of a feature model: every explored combination executed against the real code."""

    executed: int = 0
    combinations: int = 0
    declared_only: int = 0
    errors: int = 0
    violations: tuple[FeatureViolation, ...] = ()

    @property
    def ok(self) -> bool:
        return self.executed > 0 and not self.violations

    @property
    def counterexamples(self) -> tuple[FeatureViolation, ...]:
        return tuple(v for v in self.violations if v.rule_name not in {"declared_only", "adapter_exception"})

    def format_text(self, max_examples: int | None = None) -> str:
        lines = [f"executed against code: {self.executed} of {self.combinations} feature combinations; "
                 f"declared only: {self.declared_only}; errors: {self.errors}; "
                 f"counterexamples: {len(self.counterexamples)}"]
        shown = self.violations[:max_examples] if max_examples else self.violations
        lines += [violation.format_text() for violation in shown]
        if len(shown) < len(self.violations):
            lines.append(f"- ... {len(self.violations) - len(shown)} more")
        return "\n".join(lines)


def feature_conformance(features: Sequence[Feature], base: Callable[[], Any], review: Callable[[Any], Any],
                        *, max_features: int = 2) -> FeatureReport:
    """Explore the feature universe on the real code.

    For every combination the kit builds the input (``base()``, then each present feature's ``apply`` in
    declaration order) and runs ``review(input)``, the adapter around the real code.  It returns ``True``
    (accepted), ``False`` (rejected) or ``(accepted, codes)``; ``None`` leaves the combination declared
    only, and an exception is an adapter error - both fail conformance.  The four invariants must hold
    and every observed verdict must equal the design verdict (``matches_design``).
    """
    universe = _Universe(features, max_features)
    seen: dict[tuple[str, ...], tuple[str, frozenset, str]] = {}

    def observe(names: tuple[str, ...]) -> tuple[str, frozenset, str]:
        if names not in seen:
            seen[names] = _observe(universe, names, base, review)
        return seen[names]

    def judge(names):
        outcome, codes, _note = observe(names)
        return outcome, codes

    def matches_design(state: FeatureState, trace) -> InvariantResult:
        expected = universe.expected(state.features)
        if state.outcome in (ACCEPTED, REJECTED) and (state.outcome, state.codes) != expected:
            return InvariantResult.fail(f"{' + '.join(state.features) or 'clean input'}: the real code differs "
                                        "from the design verdict")
        return InvariantResult.pass_()

    explorer = universe.explorer(judge, (Invariant("matches_design", "the real verdict equals the design verdict",
                                                   matches_design),))
    report = explorer.explore()
    found: dict[tuple[str, frozenset], FeatureViolation] = {}

    def record(rule: str, state: FeatureState, sequence: Sequence[str], message: str = "") -> None:
        key = (rule, frozenset(state.features))
        if key not in found:
            order = [name for name in dict.fromkeys(sequence) if name in state.features]
            found[key] = FeatureViolation(rule, tuple(order), _verdict(*universe.expected(state.features)),
                                          _verdict(state.outcome, state.codes), message)

    clean = explorer.initial_states[0]
    for invariant in explorer.invariants:
        if not invariant.check(clean, None).ok:
            record(invariant.name, clean, ())
    for violation in report.violations:
        record(violation.invariant_name, violation.state, violation.trace.external_inputs)
    for branch in report.exception_branches:
        record("exception", branch.state, branch.trace.external_inputs, f"{branch.error_type}: {branch.message}")
    for names, (outcome, codes, note) in seen.items():
        if outcome in (DECLARED_ONLY, ERROR):
            rule = "declared_only" if outcome == DECLARED_ONLY else "adapter_exception"
            record(rule, FeatureState(names, outcome, codes), names, note)
    explained = {combination for rule, combination in found if rule != "matches_design"}
    rank = {name: index for index, name in enumerate(FEATURE_INVARIANTS + ("matches_design",))}
    violations = sorted((v for (rule, combination), v in found.items()      # matches_design only adds news
                         if rule != "matches_design" or combination not in explained),
                        key=lambda v: (len(v.features), [universe.order[n] for n in v.features],
                                       rank.get(v.rule_name, len(rank))))
    if not report.exploration_complete:
        violations.append(FeatureViolation("exploration_incomplete", (), "complete", report.termination_reason))
    outcomes = [outcome for outcome, _codes, _note in seen.values()]
    return FeatureReport(executed=sum(o in (ACCEPTED, REJECTED) for o in outcomes), combinations=len(seen),
                         declared_only=outcomes.count(DECLARED_ONLY), errors=outcomes.count(ERROR),
                         violations=tuple(violations))


def _observe(universe: _Universe, names: tuple[str, ...], base, review) -> tuple[str, frozenset, str]:
    unbuilt = [name for name in names if universe.by_name[name].apply is None]
    if unbuilt:
        return DECLARED_ONLY, frozenset(), f"feature {unbuilt[0]} has no apply(); give it one or remove it"
    try:
        plan = base()
        for name in names:
            plan = universe.by_name[name].apply(plan)
        value = review(plan)
    except Exception as exc:  # noqa: BLE001 - an adapter crash is a reported disagreement
        return ERROR, frozenset(), f"{type(exc).__name__}: {exc}"
    if value is None:
        return DECLARED_ONLY, frozenset(), "the adapter ran no code for this input; extend it or remove the feature"
    accepted, codes = value if isinstance(value, tuple) else (value, ())
    return (ACCEPTED if accepted else REJECTED), frozenset(codes) & universe.vocabulary, ""


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
        findings = list(getattr(report, "findings", ()))
        codes = [getattr(finding, "code", "") for finding in findings]
        first = next((getattr(f, "message", "") for f in findings if getattr(f, "severity", "blocker") == "blocker"), "")
        return InvariantResult.fail(f"the review rejects the plan: {', '.join(c for c in codes[:5] if c) or 'not ok'}"
                                    + (f" ({first})" if first else ""))

    return Invariant(name, description or f"{name}: the capability review accepts every reachable plan", check)


def plan_explorer(initial: Callable[[], Any], edits: Mapping[str, Callable[[Any], Any]], review: Callable[[Any], Any],
                  *, explore: Sequence[str] | None = None, invariant_name: str = "review_accepts_plan",
                  max_sequence_length: int = 2, extra_invariants: Iterable[Invariant] = (),
                  extra_reviews: Mapping[str, Callable[[Any], Any]] | None = None) -> Explorer:
    """Explore every sequence of the named edits in ``explore`` (default: all) from the initial plan.

    The review (invariant ``invariant_name``) and each of ``extra_reviews`` ({invariant name: review}) must
    accept every plan reached.  Give the design and its known-bad variants the same ``edits`` mapping and
    different ``explore`` lists, so each can rebuild the other's plans.
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

    invariants = (review_invariant(invariant_name, review, plan_of),
                  *(review_invariant(name, check, plan_of) for name, check in (extra_reviews or {}).items()),
                  *extra_invariants)
    return Explorer(workflow=Workflow((_PlanEdit(),)), initial_states=(PlanState(),),
                    external_inputs=tuple(edits if explore is None else explore),
                    invariants=invariants, max_sequence_length=max_sequence_length, progress_steps=0)


def reachable_states(explorer: Explorer, project=None) -> tuple:
    """Initial states and every step state in the report's retained traces, in first-seen order.

    Compact or incomplete reports bound what can be collected; this does not expand their traces.
    """
    report = explorer.explore()
    candidates = [*explorer.initial_states, *(step.new_state for trace in report.traces for step in trace.steps)]
    states = []
    for state in candidates:
        value = project(state) if project is not None else state
        if value is not None and value not in states:
            states.append(value)
    return tuple(states)


__all__ = ["FEATURE_INVARIANTS", "Feature", "FeatureReport", "FeatureState", "FeatureViolation", "PlanState",
           "feature_conformance", "feature_explorer", "feature_variants", "plan_explorer", "review_invariant",
           "reachable_states"]
