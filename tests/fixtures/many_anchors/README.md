# A project with many anchors and rules (round 20, speed item 6)

A synthetic stand-in for a larger program: 30 anchors in 15 modules (an owner `STANDING` with two
copies, one under other parameter names; an owner `ROUND_HALF` with two copies; two `FREE_SHIPPING`
copies; two sqlite reads; four events), ten rules in `tests/intent/rules.py` (one quoting the owner
words in `R1_owner.txt`), and 34 ordinary tests that take about one second without the plugin
(most of it `tests/test_reports.py`, which uses no anchor).

Files end in `.txt` so that neither pytest nor FlowGuard's own map reads them as this repository's
code; `tests/intent_engine/test_many_anchors_fixture.py` copies them without the suffix, commits the
baseline and stores `R1_owner.txt` with `req add --id R1`. That test only checks behaviour: the run
time with and without the plugin is measured outside the suite (see the round-20 speed report).
