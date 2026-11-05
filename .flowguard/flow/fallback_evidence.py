"""One finite test scope licenses a route label only through actual native receipts.

Source AST candidates and expected labels never manufacture native events. The
implementation tests bind these finite evidence recipes to real Python/pytest runs.
"""
from flowguard.flow import Model, need

m = Model("fallback evidence", note="One analysis scope; private disable probes retain the original primary failure.")
SCOPES = m.objects("scope", "S1")
CASES = ("missing", "unreached", "visible", "masked", "probe_unknown", "both", "authorized", "default", "reported", "interrupted", "wrong_subject", "child_gap", "partial_masked", "partial_both", "partial_visible", "unrelated_visible", "ambiguous_call", "collection_stale", "collection_gap", "unassigned")
m.field("phase", ["pending", "done"], "pending", over=SCOPES, source="R15")
m.field("case", ["pending", *CASES], "pending", over=SCOPES, source="R15")
m.field("label", ["pending", "UNKNOWN", "DEAD", "VISIBLE", "MASKING", "BOTH", "DECLARED"], "pending", over=SCOPES, source="R15")
m.field("records", [0, 1], 0, over=SCOPES, source="R15")
for field in ("two_implementations", "scope_complete", "current", "primary", "alternate", "primary_failed", "passing_test", "probe_current", "disable_failed", "sourced", "propagated"):
    m.field(field, [False, True], False, over=SCOPES, source="R15")


@m.action(scope=SCOPES, case=CASES, source="R15")
def classify(s, scope, case):
    need(s["phase", scope] == "pending", "one result for this test scope")
    s["phase", scope], s["case", scope] = "done", case
    s["records", scope] += 1
    s["current", scope] = case not in ("missing", "wrong_subject", "collection_stale")
    s["scope_complete", scope] = case not in ("missing", "interrupted", "wrong_subject", "child_gap", "partial_masked", "partial_both", "partial_visible", "collection_stale", "collection_gap", "unassigned")
    s["two_implementations", scope] = case in ("both", "authorized", "partial_both")
    s["primary", scope] = case in ("unreached", "both", "authorized", "partial_both")
    s["alternate", scope] = case in ("masked", "probe_unknown", "both", "authorized", "partial_masked", "partial_both")
    s["primary_failed", scope] = case in ("visible", "masked", "probe_unknown", "partial_masked", "partial_visible", "unrelated_visible")
    s["passing_test", scope] = case in ("masked", "probe_unknown", "both", "authorized", "partial_masked", "partial_both")
    s["probe_current", scope] = s["disable_failed", scope] = case in ("masked", "partial_masked")
    s["sourced", scope] = case == "authorized"
    s["propagated", scope] = case in ("visible", "partial_visible")
    s["label", scope] = {"missing": "UNKNOWN", "unreached": "DEAD", "visible": "VISIBLE", "masked": "MASKING",
                         "probe_unknown": "UNKNOWN", "both": "BOTH", "authorized": "DECLARED", "default": "UNKNOWN", "reported": "UNKNOWN", "interrupted": "UNKNOWN", "wrong_subject": "UNKNOWN", "child_gap": "UNKNOWN", "partial_masked": "MASKING", "partial_both": "BOTH", "partial_visible": "VISIBLE", "unrelated_visible": "UNKNOWN", "ambiguous_call": "UNKNOWN", "collection_stale": "UNKNOWN", "collection_gap": "UNKNOWN", "unassigned": "UNKNOWN"}[case]


m.terminal("phase", ["done"], source="R15")
m.always("one result per finite scope", lambda s: all(s["records", x] <= 1 for x in SCOPES), source="R15")
m.always("masking retains actual failure, passing fallback and a current failing disable probe",
         lambda s: all(s["label", x] != "MASKING" or all(s[k, x] for k in
                       ("current", "alternate", "primary_failed", "passing_test", "probe_current", "disable_failed")) for x in SCOPES), source="R15")
m.always("both routes must have served", lambda s: all(s["label", x] != "BOTH" or
         (s["current", x] and s["two_implementations", x] and s["primary", x] and s["alternate", x] and s["passing_test", x] and not s["sourced", x]) for x in SCOPES), source="R15")
m.always("a visible failure really propagated", lambda s: all(s["label", x] != "VISIBLE" or
         (s["current", x] and s["primary_failed", x] and s["propagated", x]) for x in SCOPES), source="R15")
m.always("declared routes need live source evidence", lambda s: all((s["label", x] == "DECLARED") == s["sourced", x] for x in SCOPES), source="R15")
m.always("missing captures and input defaults remain unknown", lambda s: all(s["case", x] not in ("missing", "default", "reported", "interrupted", "wrong_subject", "child_gap", "unrelated_visible", "ambiguous_call", "collection_stale", "collection_gap", "unassigned") or
         s["label", x] == "UNKNOWN" for x in SCOPES), source="R15")
m.always("unreached alternates have current finite scope", lambda s: all(s["label", x] != "DEAD" or
         (s["current", x] and s["scope_complete", x] and not s["alternate", x]) for x in SCOPES), source="R15")
m.always("partial positive witnesses do not claim a complete negative scope",
         lambda s: all(s["case", x] not in ("partial_masked", "partial_both", "partial_visible") or not s["scope_complete", x] for x in SCOPES), source="R15")
MODEL = m
