"""One workshop for all repairs: a tool that needs repair is repaired at the main branch.

The tool's place is `where` (on the shelf, on loan, in repair, ...) and `branch`. Repairs
are done only at main, so a tool that needs repair anywhere else is sent to main first:
it is in transit with `pending` set to its kind of repair, and it is in repair when it
arrives. `repaired` is refused at any other branch. The counts (`rented` since the last
repair, `inspected` since the last inspection) are kept as in design/maintenance.py.

The shipped settings are small (maintain every 2, inspect every 2) so the search is
complete; the counts are clamped at the setting, as the counter does.
"""
from machine import Machine, need

m = Machine("workshop: one place for all repairs", settings=dict(maintain_every=2, inspect_every=2))
S = m.settings


def maintenance_due(s):
    return S["maintain_every"] > 0 and s["rented"] >= S["maintain_every"]


def inspection_due(s):
    return S["inspect_every"] > 0 and s["inspected"] >= S["inspect_every"]


m.field("where", ["shop", "loan", "repair", "maint", "inspection", "lost", "transit"], "shop")
m.field("branch", ["main", "north"], "main")
m.field("pending", ["none", "repair", "maint"], "none")   # the repair waiting for the tool at main
m.field("rented", range(0, 3), 0)                          # clamped at maintain_every
m.field("inspected", range(0, 3), 0)                       # clamped at inspect_every


def send_for(s, kind):
    """A tool that needs `kind` of repair: repaired here at main, else sent to main first."""
    if s["branch"] == "main":
        s["where"] = kind
    else:
        s["where"], s["branch"], s["pending"] = "transit", "main", kind


@m.action(to=["main", "north"])
def transfer(s, to):
    need(s["where"] == "shop", "only a tool in the shop can be sent")
    need(s["branch"] != to, "already at that branch")
    s["where"], s["branch"] = "transit", to


@m.action()
def receive(s):
    need(s["where"] == "transit", "not in transit")
    if s["pending"] != "none":                  # it arrives at main for its repair
        s["where"], s["pending"] = s["pending"], "none"
    else:
        s["where"] = "shop"


@m.action()
def rent(s):
    need(s["where"] == "shop", "not in the shop")
    s["where"] = "loan"
    s["rented"] = min(s["rented"] + 1, S["maintain_every"])
    s["inspected"] = min(s["inspected"] + 1, S["inspect_every"])


@m.action()
def return_tool(s):
    need(s["where"] == "loan", "not on loan")
    if maintenance_due(s):
        send_for(s, "maint")
    elif inspection_due(s):
        s["where"] = "inspection"
    else:
        s["where"] = "shop"


@m.action()
def return_damaged(s):
    need(s["where"] == "loan", "not on loan")
    send_for(s, "repair")


@m.action()
def mark_lost(s):
    need(s["where"] == "loan", "not on loan")
    s["where"] = "lost"
    s["rented"], s["inspected"] = 0, 0


@m.action(result=["pass", "fail"])
def inspect(s, result):
    need(s["where"] == "inspection", "not waiting for inspection")
    s["inspected"] = 0
    if result == "pass":
        s["where"] = "shop"
    else:
        send_for(s, "repair")


@m.action()
def repaired(s):
    need(s["branch"] == "main", "repairs are done at the main branch")
    need(s["where"] in ("repair", "maint"), "not in repair")
    if s["where"] == "repair":                  # a maintenance leaves the inspection count alone
        s["inspected"] = 0
    s["rented"] = 0
    s["where"] = "inspection" if inspection_due(s) else "shop"


# "lost" is the end of the tool's life: its branch and counts stay where they were. The
# engine's STUCK findings on those fields, in the lost state, are expected; the only
# others the model may show are the ones of the first version (repairs stay where the tool
# is, which the first run of this model showed to be stuck at another branch).
m.terminal("where", ["lost"])
m.always("a tool in repair or maintenance is at the main branch",
         lambda s: s["where"] not in ("repair", "maint") or s["branch"] == "main")
m.always("a tool waiting for a repair at main is in transit to main",
         lambda s: s["pending"] == "none" or (s["where"] == "transit" and s["branch"] == "main"))
m.always("a tool in the shop is due no maintenance and no inspection",
         lambda s: s["where"] != "shop" or not (maintenance_due(s) or inspection_due(s)))
m.progress("a tool out, in transit, in repair or waiting for inspection gets back or is lost",
           when=lambda s: s["where"] in ("loan", "transit", "repair", "maint", "inspection"),
           goal=lambda s: s["where"] in ("shop", "inspection", "lost"))
m.reach("a damaged tool from another branch is sent to main for repair",
        lambda s: s["where"] == "transit" and s["pending"] == "repair")
m.reach("a tool is in repair at the main branch", lambda s: s["where"] == "repair")
m.only_when("repaired is refused away from main", "repaired", lambda s: s["branch"] == "main")
m.after("a repaired tool is back in the shop or inspection at main", "repaired",
        lambda b, a: a["branch"] == "main" and a["where"] in ("shop", "inspection"))
m.after("a tool that needs repair away from main is sent to main for it", "return_damaged",
        lambda b, a: (b["branch"] == "main" and a["where"] == "repair")
        or (b["branch"] != "main" and a["where"] == "transit" and a["pending"] == "repair"))
MACHINE = m
