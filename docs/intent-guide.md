# Intent guide

The canonical API guide and executable two-anchor example are in [the skill's local reference](../.agents/skills/flowguard/references/rules.md). The skill installer copies that reference with SKILL.md, so the first rule does not depend on retrieving a web page or guessing the API.

Run ordinary pytest with the plugin enabled. Its default output compares supported old/new behavior, checks same-name sensors, and reports violated independent rules. It uses at most ten lines; unobserved or unsupported behavior remains grey. No source change is quiet unless a constraint fails. Rules, source comments and small models preserve useful decisions; there is no task-modeling ceremony.

`check --deep` explicitly adds decision-site probes and mutation-survival checks. Default tests and checks do not claim mutation adequacy. `check --all --deep` runs all intent items and ordinary tests in CI, with live pytest output; a partial or non-deep collection cannot substitute. Publication requires one complete successful CI run on the exact main commit, with all three supported unsharded platforms and their required execution steps. There is no observation subprocess, nested pytest session, shard aggregator or separate diagnostic pipeline.

The shortest source comment is `# flowguard: sensor NAME`. Confirm the proposed meaning and units after `anchor draft module:function`; full comments remain valid. Simple input parameters can be varied, while context objects remain supplied by the actual test. Static call checking and an original-value recheck guard replay; unknown or effectful calls are not silently repeated. A `calibrated_by=tests/test_file.py::test_name` binding names one real ordinary test, including a parameter ID when relevant. Scenarios reuse that collected session and fresh function fixtures; unavailable shared-scope or ambiguous context stays grey.

Optional views use the same runtime and historical cache. `show NAME` displays anchor parameters, result distributions and citing rules, or a model's node/edge counts and missing or invalid paths. Old observations are labelled historical and become stale after source changes. `try NAME days=4` explores an exact input; `--grid` prints every evaluated representative without claiming that unknown partitions are complete. `watch -- python app.py` runs Python normally, records anchors and checks the loaded models. `model draft NAME` proposes existing Flow nodes and edges from recorded paths; it does not invent required paths, transitions or relations. These commands are not extra default steps.

The brief from `python -m flowguard` fits ten lines and remembers the current task's baseline commit. `check --base COMMIT` explicitly changes the comparison baseline. A rule cites only its relevant original words or authority document; preserve those bytes once with `req add`, never an AI's interpretation or plan. See [the 4.0 migration](upgrade-4.0.md) for removed interfaces.

## Generated source queries

The base installation maps Python. The seven foreign readers are frozen optional additions: install the `languages` extra to map JS/JSX, TS/TSX, C, C++ and C#. Grammars load only when their source language is present; unavailable grammars are reported explicitly. Python remains the only language with executable behavior anchors. Foreign syntax supports navigation and explicit source checks; it does not execute the application or replace a compiler. Dynamic calls, macros, overloads and external/build-dependent bindings remain unknown with reasons.

For example, if an agreed `architecture.md` says `Literal assignments to retry_limit use only 0, 1 or 2.` and the file is listed in `[tool.flowguard].authority_docs`, a small Python-only source constraint can live with the component that owns this field:

```python
from flowguard.intent import structure_rule

@structure_rule("RETRY_LITERALS", source='doc architecture.md "Literal assignments to retry_limit use only 0, 1 or 2."')
def RETRY_LITERALS(graph):
    return [write for write in graph.assignments(language="python")
            if write["field"] == "retry_limit" and write["value"] not in (0, 1, 2)]
```

This checks the declared literal assignments, not computed keys or every runtime write. A source predicate returns violating rows/nodes, rather than a boolean or a copied implementation. A newly written policy remains green*, not independent authority. Use the source scope the actual requirement specifies; removing languages or files to obtain green changes the claim.

`graph.capabilities()` exposes actual languages/files, parser errors, available grammars and supported queries. `graph.query_coverage()` reports the queries this handle actually served and any unavailable or failed source scope. `functions()` tracks nodes, assignments and keys are tracked, and `calls(include_reads=True)` also requests symbol-read coverage. `nodes(file=...)` and `language="python"` make an intentional source boundary explicit. Foreign handlers, literal sets, test discovery and full symbol reads are not yet implemented. A structure rule using unavailable coverage, failed parsing, or no source query is grey. Each structure check has its own scope; direct library users can call `reset_query_coverage()` before a separate predicate.

The shared cache is invalidated by source changes, reader/grammar versions and project parser configuration or compilation-option content. Unsupported configuration, dependencies outside mapped roots and unresolved bindings stay unknown; cached syntax is not evidence of successful compilation or execution.

Fingerprints help find changed code and possible moves. They do not establish cross-language equivalence or prove behavior merely because names or shapes match.

## Use hierarchy only when it removes repetition

An upper behavior rule can declare `uses=[LOWER]`. A scenario relation connects actual lower and upper readings; the engine derives the logical-input binding and supplies verified joint witnesses. Lower sources and anchors must pass too; explicit deep checks additionally require mutation liveness. Joint checks combine all verified lower inputs, through nested uses, instead of changing one lower input at a time. Closed boolean/enum domains can have complete finite coverage. Open domains use supported partition representatives and report that boundary; they are not enumerated value by value.

Keep behavior decomposition in those actual uses relations and source constraints in `structure_rule` at their owner. Neither requires a whole-application model, a separate hierarchy format, or modeling the current development task.

Source anchors replace the old `.home` decorator. The [3.0 guide](upgrade-3.0.md) describes that older input migration; [4.0](upgrade-4.0.md) changes the execution boundary. A complex flow has only nodes, edges, existing state transitions and existing-rule reading relations. `model draft NAME` starts from real observed paths rather than repeating the implementation.

A `Node(..., model="CHILD_FLOW", phase="return")` can consume a registered child Flow's output. The child exports one existing Rule through an explicit `Relation(..., actual=Read("end"), on="end")` at a terminal return/raise node; the parent names that same source anchor and phase. Its Rule contract and joint witnesses still apply, and the child graph's finite and runtime checks must also pass on the same observed invocation batch. Deleting an internal save cannot leave that parent green merely because the exported boolean stayed unchanged. A test-entry Flow can supply the existing ordinary-test scenario binding separately from the production graph.

Each exported event needs one declared production start call in the child graph. Its matching return can be the export; nested check/save calls remain steps inside that start. Different invocations retain separate event scopes and share only coverage accounting. Missing or multiple exports, unregistered Flow objects, cycles, unavailable source identities and unobserved model edges remain grey. There is no fixed ten-layer depth cap; keep each layer near ten meaningful nodes so it is understandable. Finite state spaces are fully explored without a default fixed state cap. A same-named Rule or saved green metadata does not verify a child graph.

Default Flow verdicts cover observed anchor paths and the declared finite model. Unexecuted source routes remain unverified; an observed green does not prove that the source has no other route. Static path analysis is frozen and is not run by the engine; its direct SDK helpers remain available for their narrower explicit source scope.
