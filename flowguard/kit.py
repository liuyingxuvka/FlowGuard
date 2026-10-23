"""Model kits: build a complete FlowGuard model from a concern's features or edits and an existing review.

Every model has the same five abilities: a state model, counterexamples from
bounded exploration, known-bad variants that must fail, a binding to the real
code (anchors plus conformance) and a binding to tests.  Two generic shapes
give a capability or a self-model all five with little code:

* **Features** - a feature is one named property of an input (``Feature``): a
  rejecting feature is a defect the code must reject and report, a benign
  feature is a variation that must not change the verdict, and ``apply``
  changes a clean base input to have the property.  The state is the set of
  applied features; exploration reaches each allowed set once, up to
  ``max_features=2`` by default.  The design rejects exactly when a rejecting feature
  is present and reports all codes, or the first defect's codes with ``codes="first"``. The kit owns
  invariants (``clean_input_accepted``, ``each_defect_rejected``,
  ``every_defect_reported``, ``benign_features_neutral``) and generates the
  known-bad variants (``feature_variants``).  ``feature_conformance`` explores
  the same universe on the real code: it builds each input from the clean base,
  runs the real review and reports a counterexample trace (the feature
  sequence, the expected and the observed verdict) for every combination that
  breaks an invariant or differs from the design.
* **Plan edits** - the state is a capability plan reached by named edits;
  ``plan_explorer`` checks every reachable plan against existing review invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
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
    removes what they change); it is explored alone. ``requires`` names features that must be present;
    ``conflicts`` names features that cannot occur together (a symmetric restriction).
    """

    name: str
    rejects: bool
    codes: tuple[str, ...] = ()
    apply: Callable[[Any], Any] | None = field(default=None, compare=False)
    exclusive: bool = False
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "codes", tuple(self.codes))
        object.__setattr__(self, "requires", tuple(self.requires))
        object.__setattr__(self, "conflicts", tuple(self.conflicts))
        if self.codes and not self.rejects:
            raise ValueError(f"benign feature {self.name!r} cannot report finding codes")


@dataclass(frozen=True)
class FeatureState:
    """State of a feature model: the applied features (declaration order) and the verdict on that input.

    ``codes`` holds the reported codes that belong to the model's features; ``plain_*`` is the verdict on
    the same input without its benign features, when that projection is legal.
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

    def __init__(self, features: Sequence[Feature], max_features: int, codes: str = "all") -> None:
        self.features = tuple(features)
        names = [feature.name for feature in self.features]
        if not names or len(set(names)) != len(names):
            raise ValueError("a feature model needs at least one feature and unique feature names")
        if max_features < 1:
            raise ValueError("max_features must be at least 1")
        self.by_name = {feature.name: feature for feature in self.features}
        self.order = {name: index for index, name in enumerate(names)}
        self.max_features = max_features
        if codes not in ("all", "first"):
            raise ValueError("codes must be 'all' or 'first'")
        self.codes = codes
        for feature in self.features:
            unknown = set(feature.requires + feature.conflicts) - self.by_name.keys()
            if unknown:
                raise ValueError(f"feature {feature.name!r} names unknown features: {sorted(unknown)}")
        for feature in self.features:
            required = {feature.name}
            pending = [feature.name]
            while pending:
                for name in self.by_name[pending.pop()].requires:
                    if name not in required:
                        required.add(name)
                        pending.append(name)
            if not self.allowed(required):
                raise ValueError(f"feature {feature.name!r} requirements cannot fit a legal set within max_features={max_features}")
        self.combinations = tuple(group for size in range(1, min(max_features, len(names)) + 1)
                                  for group in combinations(names, size) if self.allowed(group))
        self.vocabulary = frozenset(code for feature in self.features for code in feature.codes)

    def rejecting(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names if self.by_name[name].rejects)

    def allowed(self, names: Iterable[str]) -> bool:
        names = frozenset(names)
        return (len(names) <= self.max_features
                and all(set(self.by_name[name].requires) <= names for name in names)
                and all(not (self.by_name[left].exclusive or self.by_name[right].exclusive
                             or right in self.by_name[left].conflicts or left in self.by_name[right].conflicts)
                        for left, right in combinations(names, 2)))

    def expected(self, names: tuple[str, ...]) -> tuple[str, frozenset]:
        """Rejected iff a defect is present; report all defects or the first in declaration order."""
        rejecting = self.rejecting(names)
        reported = rejecting[:1] if self.codes == "first" else rejecting
        return (REJECTED if rejecting else ACCEPTED), frozenset(c for n in reported for c in self.by_name[n].codes)

    def state(self, names: tuple[str, ...], judge: Callable[[tuple[str, ...]], tuple[str, frozenset]]) -> FeatureState:
        outcome, codes = judge(names)
        plain = self.rejecting(names)
        plain_outcome, plain_codes = (outcome, codes) if plain == names or not self.allowed(plain) else judge(plain)
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

        checks = []
        if any(not self.rejecting(names) for names in self.combinations):
            checks.append(Invariant("clean_input_accepted", "an input with no defect is accepted", clean_input_accepted))
        if any(feature.rejects for feature in self.features):
            checks.append(Invariant("each_defect_rejected", "an input with any defect is rejected", each_defect_rejected))
        if any(self.expected(names)[1] for names in self.combinations):
            name = "first_defect_reported" if self.codes == "first" else "every_defect_reported"
            checks.append(Invariant(name, "a rejection reports the declared codes of the expected defects", every_defect_reported))
        if any(self.rejecting(names) != names and self.allowed(self.rejecting(names)) for names in self.combinations):
            checks.append(Invariant("benign_features_neutral", "removing legal benign features does not change the verdict",
                                    benign_features_neutral))
        return tuple(checks)

    def explorer(self, judge, extra_invariants: Iterable[Invariant] = ()) -> Explorer:
        return Explorer(workflow=Workflow((_AddFeature(self, judge),)), initial_states=(self.state((), judge),),
                        external_inputs=self.combinations,
                        invariants=self.invariants() + tuple(extra_invariants),
                        max_sequence_length=1, progress_steps=0)


class _AddFeature:
    """Function block: apply one complete allowed feature set to the clean input."""

    name = "AddFeature"
    reads = ("features",)
    writes = ("features", "outcome", "codes")

    def __init__(self, universe: _Universe, judge) -> None:
        self.universe = universe
        self.judge = judge

    def apply(self, names: tuple[str, ...], state: FeatureState):
        new = self.universe.state(names, self.judge)
        return (FunctionResult(new.outcome, new, label=f"{' + '.join(names)}:{new.outcome}"),)


def feature_explorer(features: Sequence[Feature], *, max_features: int = 2, codes: str = "all") -> Explorer:
    """The intended design: explore every allowed feature set once, up to ``max_features``."""
    universe = _Universe(features, max_features, codes)
    return universe.explorer(universe.expected)


def feature_variants(features: Sequence[Feature], *, max_features: int = 2, codes: str = "all") -> dict[str, Explorer]:
    """Generate bad verdicts with real witnesses in the legal feature sets.

    Code masking reports only the first defect in all-code mode, or the last in first-code mode.
    If neither can mask an expected code, dropping codes supplies the reporting witness instead.
    """
    universe = _Universe(features, max_features, codes)
    rejecting = [feature for feature in universe.features if feature.rejects]
    benign = [feature for feature in universe.features if not feature.rejects]
    variants: dict[str, Explorer] = {}
    if rejecting:
        ignored = rejecting[0].name
        def ignores(names):
            remaining = tuple(name for name in names if name != ignored)
            return universe.expected(remaining)

        # Required co-defects can prevent removal of one defect from accepting an input.
        # In that case an ignoring implementation accepts an input containing that defect.
        if not any(universe.expected(names)[0] != ignores(names)[0] for names in universe.combinations):
            variants[f"ignores_{ignored}"] = universe.explorer(
                lambda names: (ACCEPTED, frozenset()) if ignored in names else universe.expected(names))
        else:
            variants[f"ignores_{ignored}"] = universe.explorer(ignores)
    def limited(names):
        outcome, _codes = universe.expected(names)
        defects = universe.rejecting(names)
        selected = defects[-1:] if codes == "first" else defects[:1]
        return outcome, frozenset(code for name in selected for code in universe.by_name[name].codes)

    if any(universe.expected(names)[1] - limited(names)[1] for names in universe.combinations):
        key = "reports_last_defect_only" if codes == "first" else "reports_first_defect_only"
        variants[key] = universe.explorer(limited)
    elif any(universe.expected(names)[1] for names in universe.combinations):
        coded = next(feature for feature in universe.features if feature.codes)
        variants[f"drops_codes_of_{coded.name}"] = universe.explorer(
            lambda names: (universe.expected(names)[0], frozenset()))
    neutral = next((feature for feature in benign
                    if any(feature.name in names and universe.allowed(universe.rejecting(names))
                           for names in universe.combinations)), None)
    if neutral is not None:
        loud = neutral.name
        has_clean_witness = any(loud in names and not universe.rejecting(names) for names in universe.combinations)
        variants[f"rejects_{loud}"] = universe.explorer(
            lambda names: ((REJECTED if has_clean_witness else ACCEPTED), universe.expected(names)[1])
            if loud in names else universe.expected(names))
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
                        *, max_features: int = 2, codes: str = "all") -> FeatureReport:
    """Explore the feature universe on the real code.

    For every combination the kit builds the input (``base()``, then each present feature's ``apply`` in
    declaration order) and runs ``review(input)``, the adapter around the real code.  It returns ``True``
    (accepted), ``False`` (rejected) or ``(accepted, codes)``; ``None`` leaves the combination declared
    only, and an exception is an adapter error - both fail conformance.  The four invariants must hold
    and every observed verdict, including the clean base, must equal the design verdict (``matches_design``).
    The kit omits invariants that have no witness among the allowed nonempty feature sets.
    """
    universe = _Universe(features, max_features, codes)
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
            order = list(state.features)
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
    rank = {name: index for index, name in enumerate(FEATURE_INVARIANTS + ("first_defect_reported", "matches_design",))}
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
        if (project is None or value is not None) and value not in states:
            states.append(value)
    return tuple(states)


__all__ = ["FEATURE_INVARIANTS", "Feature", "FeatureReport", "FeatureState", "FeatureViolation", "PlanState",
           "feature_conformance", "feature_explorer", "feature_variants", "plan_explorer", "review_invariant",
           "reachable_states"]
