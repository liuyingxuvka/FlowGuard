"""A clean model, native correspondence and an executed regression have distinct roles."""
from flowguard.flow import Model, need

m = Model("native confirmation")
m.field("phase", ("open", "held", "candidate", "tested", "closed"), "open")
m.field("full_scope", (False, True), False)
m.field("native_matches", (False, True), False)
m.field("condition_gone", (False, True), False)
m.field("regression_passed", (False, True), False)


@m.action(full=(False, True), native=(False, True), gone=(False, True))
def compare(s, full, native, gone):
    need(s["phase"] == "open")
    s["full_scope"], s["native_matches"], s["condition_gone"] = full, native, gone
    s["phase"] = "candidate" if full and native and gone else "held"


@m.action()
def execute_regression(s):
    need(s["phase"] == "candidate")
    s["regression_passed"] = True
    s["phase"] = "tested"


@m.action()
def close(s):
    need(s["phase"] == "tested")
    s["phase"] = "closed"


@m.action()
def next_check(s):
    need(s["phase"] in ("held", "closed"))
    s["phase"] = "open"
    s["full_scope"] = s["native_matches"] = s["condition_gone"] = s["regression_passed"] = False


m.always("closing needs the complete scope, real correspondence and an executed regression",
         lambda s: s["phase"] != "closed" or all(s[k] for k in
         ("full_scope", "native_matches", "condition_gone", "regression_passed")))
m.reach("a confirmed repair can close", lambda s: s["phase"] == "closed")
MODEL = m
