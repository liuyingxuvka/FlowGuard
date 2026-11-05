"""A static source query only links live request commits touching the symbol."""
from flowguard.flow import Model, need

m = Model("static where", covers=["flowguard/map/requests.py", "flowguard/map/derived.py"])
CASES = ("same_symbol", "other_symbol", "retired_request", "malformed_request", "missing_history")
m.field("phase", ("start", "shown"), "start")
m.field("case", ("unset", *CASES), "unset")
m.field("linked", (False, True), False)
m.field("unknown", (False, True), False)
m.field("executed", (False,), False)

@m.action(case=CASES)
def query(s, case):
    need(s["phase"] == "start")
    s["case"] = case
    s["linked"] = case == "same_symbol"
    s["unknown"] = case in ("retired_request", "malformed_request", "missing_history")
    s["phase"] = "shown"

@m.action()
def next_query(s):
    need(s["phase"] == "shown")
    s["phase"] = "start"
    s["case"] = "unset"
    s["linked"] = False
    s["unknown"] = False

m.always("source query never executes project code", lambda s: not s["executed"])
m.always("unrelated or invalid history does not authorize a link",
         lambda s: not s["linked"] or s["case"] == "same_symbol")
m.reach("real symbol commit is linked", lambda s: s["case"] == "same_symbol" and s["linked"])
m.reach("missing history stays visible", lambda s: s["case"] == "missing_history" and s["unknown"])
MODEL = m
