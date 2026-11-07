# Rules and anchors

Use `show "what it decides"` to find an existing owner. Optionally model repeated judgments or complex paths across sessions.

## Example

In this throwaway example, put this in `policy.txt`:

```text
At most three days.
```

```toml
[tool.flowguard]
authority_docs = ["policy.txt"]
```

In `orders.py`:

```python
# flowguard: sensor ACCEPT(days: day) -> allowed: bool
def accept(days: int) -> bool:
    return days <= 3

# flowguard: sensor ACCEPT(days: day) -> allowed: bool
def preview_accept(days: int) -> bool:
    return days <= 3
```

In `tests/intent/window.py`:

```python
from flowguard.intent import rule, row

@rule("WINDOW", decides="acceptance window", fields={"days": int},
      source='doc policy.txt "At most three days."', anchor="ACCEPT")
def WINDOW(days):
    return days <= 3

WINDOW.rows(row(days=4, expect=False, why="the fourth day was incorrectly accepted"))
```

Run `python -m flowguard init`, then `python -m flowguard check`. Change only the preview to allow four days: the real copy disagrees with the rule and its same-name peer. A newly written document is provisional green*, not independent confirmation.

`anchor draft orders:accept` proposes the comment and input bounds. Confirm meaning and units. Comments do not make product code depend on FlowGuard. Matching names assert the same judgment. Missing points, mismatched source signatures or units are red. Different policies can use different names and `distinct("A", "B", why="...", source="...")`; when a rule and anchor share a name, use the real `module:qual` to identify the anchor. `compare A B` lists differing classes.

## Checked scope

Rules have an ID, decision key, typed fields, source and independent predicate. Literal rows have inputs, `expect` and `why`; `retired` explains an inapplicable old case. Returning `None` means no opinion. `total=True` makes an uncovered decision an error. `Refused(ValueError, contains="...")` expects a real program exception; a tool error is not that exception.

Boolean and closed-enum domains can be fully enumerated. Numeric/date/duration inputs use all supported partition representatives. Joint old/new partitions retain both boundaries. Unsupported nonlinear operations or unknown domains stay grey. A safe result type can be a union or collection without making that type an enumerable input domain.

Pure observations call real, verified code. Unknown imports, initialization, mutable inputs or calls may require a test. Add `calibrated_by=tests/test_store.py::test_available` to that sensor's comment, naming exactly one ordinary test, including its parameter ID. The original full test must pass; an independent zero-replacement observation must agree before changed inputs count. Controlled probes can exit pytest with a stop and are never reported as ordinary test passes.

For a stateful outcome that occurs after the function returns, use a test scenario plus a small flow. The ordinary test prepares real inputs and calls real code; it accepts no function callback and does not calculate the expected policy answer. A test event can expose logical case inputs, production anchors expose actual outputs, and a `Relation` connects those readings to the existing rule. The engine derives the binding; there is no user adapter. Unsupported or ambiguous connections remain grey. Context supplied by that test is a boundary, not every possible filesystem or database state.

## Small paths and reading relations

A model in `tests/intent/` has only nodes, edges, transitions and relations. For example, with actual production `ENTRY`, `SAVED` and `PUBLISHED` anchors:

```python
from flowguard.intent import flow, Node, Read, Relation, rule

@rule("CURRENT", decides="published identity",
      fields={"saved": str, "published": str}, source="assumed: publish this artifact")
def CURRENT(saved, published):
    return saved == published

flow("PUBLISH", source="assumed: save before publishing this artifact",
     nodes=[Node("entry", "ENTRY"), Node("saved", "SAVED", phase="return"),
            Node("published", "PUBLISHED")],
     edges=[("entry", "saved"), ("saved", "published")],
     relations=[Relation(CURRENT, {"saved": Read("saved", "result.id"),
                         "published": Read("published", "arg.artifact_id")})])
```

Identifiers must be actual string readings. A call named save proves only an attempt; completion and the current artifact need actual readings. Match real types: a Path is not a string. Fixed read projections select named parameters, result keys/indices, explicit state fields or errors. The UTF-8 view is lossless, including BOM and line endings; empty/equals relations are explicit. Arbitrary conversion callbacks are not supported.

State comments identify existing fields, for example `# flowguard: states Job.status = new | saved | published`; `Transition` references that field and a real node. Finite states are explored; an oversized model reports its boundary. Keep about ten nodes per layer. Use `model=LOWER` for a Rule contract, or a registered child Flow with one end-reading Rule. Child paths, state and readings must pass for the same source/invocation; red/grey child evidence propagates. Joint witnesses reuse the original engine. Missing evidence, ambiguous exports and model cycles stay grey.

Tests record only anchors, with case, invocation, actual caller, order and source identity. Repeated readings are not collapsed to one value. Scenario models use their explicit test entry; production models do not ignore bypasses merely because their entry was absent. Missing exercised edges are grey. Definite source bypasses and observed invalid paths are red; unsupported dispatch/control stays unknown. Models and code can share a wrong interpretation; retain original words and independent tests.

## Sources and maintenance

`check` prints changed outcome classes, at most ten plus totals; this information alone does not fail tests. Ordinary pytest uses the same plugin. Expensive, coupled or unclosed automatic comparisons are check-only; explicit checks retain full supported partitions. Red means a demonstrated mismatch. Grey is not success.

The Map reads Python, JS/TS, C/C++ and C#. Foreign syntax is navigation, not execution. Query `capabilities()` and `query_coverage()`; unsupported scope stays grey. A `structure_rule` returns violating ownership/dependency rows. Fingerprints and proposed moves are clues, not equivalence.

`owner R1` cites archived actual words; `req add` stores their exact bytes. Never archive this guide or an AI plan as owner words. Document sources require quoted text and an `authority_docs` entry. `assumed:` and `lesson:` do not create owner authority. An archive proves bytes, not an interpretation.

The CLI prepares imports. Treat direct Model/Engine instances as fixed snapshots. Native tests cover effects outside modeled relations. Reuse needs closed dependencies; external inputs can require reruns. CI uses `check --all` and an environment outside the project. Observations retain the project's assertions, teardown and skip/collection policy.
