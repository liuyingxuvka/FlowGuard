"""One tool's life: rentals, maintenance every N rentals, inspections, damage and loss.

The member is left out: a rental is just "the tool is on loan". The counts are the
ones the counter keeps: `rented` (rentals since the last repair, for maintenance) and
`inspected` (rentals since the last inspection, or since the last damage repair, as before).

The state "maint" is a tool waiting for its maintenance; the counter shows it as status
"repair", like any repair. A maintenance does not restart the inspection count, so
inspections still come every `inspect_every` rentals.
"""
from machine import Machine, need

m = Machine("tool maintenance", settings=dict(maintain_every=2, inspect_every=3))
S = m.settings
# The settings are read at call time (--set changes them after the model is loaded).


def maintenance_due(s):
    return S["maintain_every"] > 0 and s["rented"] >= S["maintain_every"]


def inspection_due(s):
    return S["inspect_every"] > 0 and s["inspected"] >= S["inspect_every"]


m.field("where", ["shop", "loan", "maint", "repair", "inspection", "lost"], "shop")
m.field("rented", range(0, 6), 0)           # rentals since the last repair (clamped at the setting)
m.field("inspected", range(0, 6), 0)        # rentals since the last inspection (clamped too)


@m.action()
def rent(s):
    need(s["where"] == "shop", "the tool is not in the shop")
    s["where"] = "loan"
    s["rented"] = min(s["rented"] + 1, S["maintain_every"])
    s["inspected"] = min(s["inspected"] + 1, S["inspect_every"])


@m.action()
def return_tool(s):                          # a normal return: maintenance, else inspection
    need(s["where"] == "loan", "the tool is not on loan")
    if maintenance_due(s):
        s["where"] = "maint"
    elif inspection_due(s):
        s["where"] = "inspection"
    else:
        s["where"] = "shop"


@m.action()
def return_damaged(s):
    need(s["where"] == "loan", "the tool is not on loan")
    s["where"] = "repair"


@m.action()
def mark_lost(s):
    need(s["where"] == "loan", "the tool is not on loan")
    s["where"] = "lost"
    s["rented"], s["inspected"] = 0, 0


@m.action(result=["pass", "fail"])
def inspect(s, result):
    need(s["where"] == "inspection", "the tool is not waiting for inspection")
    s["inspected"] = 0
    if result == "pass":
        s["where"] = "shop"
    else:
        s["where"] = "repair"


@m.action()
def repaired(s):
    need(s["where"] in ("maint", "repair"), "the tool is not in repair")
    if s["where"] == "repair":               # a damage repair or a failed inspection, as before
        s["inspected"] = 0
    s["rented"] = 0
    s["where"] = "inspection" if inspection_due(s) else "shop"


# "lost" is the end of the tool's life: its two counts stay where they were. The engine's
# STUCK finding on those two counts (in the lost state) is expected and is the only one.
m.terminal("where", ["lost"])

# Promises the requirements make.
m.always("a tool in the shop is due no maintenance and no inspection",
         lambda s: s["where"] != "shop" or not (maintenance_due(s) or inspection_due(s)))
m.after("a normal return of a tool due for maintenance sends it to maintenance",
        "return_tool",
        lambda b, a: not (b["where"] == "loan" and maintenance_due(b)) or a["where"] == "maint")
m.after("a damaged return goes to repair, even at the maintenance count",
        "return_damaged", lambda b, a: a["where"] == "repair")
m.after("recording a repair starts the maintenance count again from 0", "repaired",
        lambda b, a: a["rented"] == 0)
m.progress("a tool that is out or in repair or inspection gets back to the shop or is lost",
           when=lambda s: s["where"] in ("loan", "maint", "repair", "inspection"),
           goal=lambda s: s["where"] in ("shop", "lost"))
m.reach("a tool is sent to maintenance", lambda s: s["where"] == "maint")
m.reach("a tool is inspected after a maintenance",
        lambda s: s["where"] == "inspection" and s["rented"] == 0)
MACHINE = m
