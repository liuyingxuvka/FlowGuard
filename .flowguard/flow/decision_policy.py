"""S2 decisions retain open conflicts; a receipt may permit only its exact index."""
from flowguard.flow import Model, need

m = Model("decision and staged receipt")
CASES = ("missing_ledger_live_owner", "missing_ledger_retired_owner", "live_owner", "missing_owner", "retired_owner", "unrelated_quote", "two_rules",
         "offered_refused", "stuck", "never", "drift", "running", "stale_index", "unstaged_decision", "unknown_finished")
m.field("phase", ("ready", "allowed", "held"), "ready")
m.field("case", ("none", *CASES), "none")
m.field("owner_closed", (False,), False)
m.field("provisional_open", (False, True), False)

@m.action(case=CASES)
def assess(s, case):
    need(s["phase"] == "ready")
    s["case"] = case
    s["phase"] = "allowed" if case in ("missing_ledger_live_owner", "live_owner", "two_rules", "unknown_finished") else "held"
    s["provisional_open"] = case == "two_rules"

@m.action()
def reconsider(s):
    need(s["phase"] != "ready")
    s["phase"] = "ready"
    s["case"] = "none"
    s["provisional_open"] = False

m.always("a decision never pretends the code was fixed", lambda s: not s["owner_closed"])
m.always("temporary requires two sourced rules", lambda s: not s["provisional_open"] or s["case"] == "two_rules")
m.always("no running or stale receipt permits commit", lambda s: s["case"] not in ("running", "stale_index", "unstaged_decision") or s["phase"] == "held")
m.reach("finished unknown is allowed and visible", lambda s: s["case"] == "unknown_finished" and s["phase"] == "allowed")
m.reach("a missing ledger does not change live owner authority", lambda s:
        s["case"]=="missing_ledger_live_owner" and s["phase"]=="allowed")
m.reach("a missing ledger does not revive retired owner authority", lambda s:
        s["case"]=="missing_ledger_retired_owner" and s["phase"]=="held")
MODEL = m
