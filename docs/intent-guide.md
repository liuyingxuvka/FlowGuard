# Intent guide

The canonical API guide and executable two-anchor example are in [the skill's local reference](../.agents/skills/flowguard/references/rules.md). The skill installer copies that reference with SKILL.md, so the first rule does not depend on retrieving a web page or guessing the API.

## Generated source queries

The same Map reads Python, JS/JSX, TS/TSX, C, C++ and C#. Normal installation supplies their grammar packages, loaded only when the source language is present. Python remains the only language with executable behavior anchors. Foreign grammar facts support navigation and explicit source checks; they do not execute the application or replace a compiler. Dynamic calls, macros, overloads and external/build-dependent bindings remain unknown with reasons.

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

An upper behavior rule can declare `uses=[LOWER]`. A scenario relation connects actual lower and upper readings; the engine derives the logical-input binding and supplies verified joint witnesses. Lower sources, anchors and liveness must pass too. Joint checks combine all verified lower inputs, through nested uses, instead of changing one lower input at a time. Closed boolean/enum domains can have complete finite coverage. Open domains use supported partition representatives and report that boundary; they are not enumerated value by value.

Keep behavior decomposition in those actual uses relations and source constraints in `structure_rule` at their owner. Neither requires a whole-application model, a separate hierarchy format, or modeling the current development task.

Source anchors replace the old `.home` decorator. See [the 3.0 migration](upgrade-3.0.md) for direct sensors, ordinary calibration tests and scenario relations. Complex flows have nodes, edges, existing state transitions and existing-rule reading relations; they do not repeat the implementation.
