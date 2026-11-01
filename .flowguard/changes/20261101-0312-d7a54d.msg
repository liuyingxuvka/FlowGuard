FG-698: Derived views and the text-rule report in the main command line

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 1 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- changes: release_gate.advice_never_gates because "Preserve independent advice/non-gating behavior while replacing duty counts with source-bound cohesion facts"
  old rule:
    Invariant('advice_never_gates', 'size and count lint findings are advice: release never fails on them and they need no accepted debt', lambda s, t: s.expired_debt or s.snapshot_failed or s.lint != 'advice' or (s.check != 'clean') or (s.models != 'pass') or (s.shards and s.suite != 'pass') or (s.verdict == 'pass'))
  new rule:
    Invariant('advice_never_gates', 'size, fan-out and source-bound cohesion findings are advice: release never fails on them and they need no accepted debt', lambda s, t: s.expired_debt or s.snapshot_failed or s.lint != 'advice' or (s.check != 'clean') or (s.models != 'pass') or (s.shards and s.suite != 'pass') or (s.verdict == 'pass'))
- touch: flowguard/__main__.py:_verb_parser
- touch: flowguard/__main__.py:main
- touch: flowguard/map/derived.py:text_reference_hint
- touch: flowguard/map/derived.py:text_references
- touch: flowguard/map/derived.py:_architecture
- touch: flowguard/map/derived.py:where
- touch: flowguard/map/textrules.py:_literal_groups
- touch: flowguard/map/textrules.py:report
- touch: flowguard/map/textrules.py:render
- touch: flowguard/map/lint.py:shape_findings
- touch: flowguard/map/lint.py:run_lint
- touch: flowguard/map/textrules.py:_paragraphs
