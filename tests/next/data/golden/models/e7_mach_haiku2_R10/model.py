"""Design model for REQUEST.md ("one workshop for all repairs"): one tool, two branches.

Five variants of the same machine, one per design question. Run:

    python3 tools/machine.py design/model.py

  today      the code as it is: repaired works at any branch (the rule the request changes)
  A literal  only the branch check added to repaired; transfer as today (available tools only)
  B manual   A, plus staff may send a tool in repair to main; receive returns it to repair
  B bug      B, but receive puts every arriving tool on the shelf (forgets the repair)
  C auto     A, plus a tool that needs repair away from main is sent to main by the system

The model covers one tool's condition, its branch, and the rentals that make it due for
inspection or maintenance. A lost tool is left out: it never comes back to repair, so it
does not change what the repair rules need. Counters are small (inspect_every and maintain_every are 2 here,
5 and 4 in the code). Holds, members and money are left out: none of them changes whether
a tool can get back to the shop.
"""
from machine import Machine, need

BRANCHES = ["main", "library"]
CONDS = ["shop", "loan", "repair", "inspection", "transit"]
CARRY = ["shop", "repair"]          # what a tool in transit comes back to on receive

VARIANTS = {
    "today":     dict(branch_rule=False, move="none",   keep_carry=True),
    "A literal": dict(branch_rule=True,  move="none",   keep_carry=True),
    "B manual":  dict(branch_rule=True,  move="manual", keep_carry=True),
    "B bug":     dict(branch_rule=True,  move="manual", keep_carry=False),
    "C auto":    dict(branch_rule=True,  move="auto",   keep_carry=True),
}


def build(label, v):
    m = Machine(label, settings=dict(inspect_every=2, maintain_every=2))
    S = m.settings
    E, M = S["inspect_every"], S["maintain_every"]

    m.field("where", BRANCHES, "main")                 # the branch the tool is at (or going to)
    m.field("cond", CONDS, "shop")                     # its condition
    m.field("carry", CARRY, "shop")                    # what it comes back to, when in transit
    m.field("since_insp", range(0, E + 1), 0)          # rentals since the last inspection (capped)
    m.field("since_maint", range(0, M + 1), 0)         # rentals since the last repair (capped)
    m.field("maint", (False, True), False)             # the repair in hand is a maintenance

    def send_to_repair(s, maintenance):
        """The tool needs repair: it goes to repair where it is, or (variant C) to main."""
        s["maint"] = maintenance
        if v["move"] == "auto" and s["where"] != "main":
            s["cond"], s["carry"], s["where"] = "transit", "repair", "main"
        else:
            s["cond"] = "repair"

    @m.action()
    def rent(s):
        need(s["cond"] == "shop", "not on the shelf")
        s["cond"] = "loan"
        s["since_insp"] = min(s["since_insp"] + 1, E)
        s["since_maint"] = min(s["since_maint"] + 1, M)

    @m.action()
    def return_ok(s):                                   # back, nothing wrong
        need(s["cond"] == "loan", "not on loan")
        if s["since_insp"] >= E:
            s["cond"] = "inspection"
        elif s["since_maint"] >= M:
            send_to_repair(s, True)                     # maintenance is a repair too
        else:
            s["cond"] = "shop"

    @m.action()
    def return_damaged(s):
        need(s["cond"] == "loan", "not on loan")
        send_to_repair(s, False)

    @m.action()
    def inspect_pass(s):
        need(s["cond"] == "inspection", "not waiting for inspection")
        s["since_insp"] = 0
        if s["since_maint"] >= M:
            send_to_repair(s, True)
        else:
            s["cond"] = "shop"

    @m.action()
    def inspect_fail(s):
        need(s["cond"] == "inspection", "not waiting for inspection")
        s["since_insp"] = 0
        send_to_repair(s, False)

    @m.action(to=BRANCHES)
    def transfer(s, to):
        need(s["where"] != to, "already at that branch")
        if s["cond"] == "shop":
            s["carry"] = "shop"
        else:
            need(v["move"] == "manual" and s["cond"] == "repair" and to == "main",
                 "only a shop tool can be sent")
            s["carry"] = "repair"
        s["cond"], s["where"] = "transit", to

    @m.action()
    def receive(s):
        need(s["cond"] == "transit", "not in transit")
        s["cond"] = s["carry"] if v["keep_carry"] else "shop"
        s["carry"] = "shop"

    @m.action()
    def repaired(s):
        need(s["cond"] == "repair", "not in repair")
        if v["branch_rule"]:
            need(s["where"] == "main", "repairs are done at main only")
        s["cond"] = "shop"                              # back in the shop, at its branch
        s["since_maint"] = 0
        if not s["maint"]:
            s["since_insp"] = 0
        s["maint"] = False

    # ------------------------------------------------------------ the promises
    m.only_when("repaired only at main", "repaired", lambda s: s["where"] == "main")
    m.after("a repaired tool is in the shop", "repaired", lambda b, a: a["cond"] == "shop")
    m.after("a tool sent for repair is not put on the shelf by a move", "receive",
            lambda b, a: not (b["carry"] == "repair" and a["cond"] == "shop"))
    m.progress("a tool in repair is always repaired",
               when=lambda s: s["cond"] == "repair", goal=lambda s: s["cond"] == "shop")
    m.progress("a tool not on the shelf can always get back to it",
               when=lambda s: s["cond"] != "shop", goal=lambda s: s["cond"] == "shop")
    return m


MACHINES = [build(label, v) for label, v in VARIANTS.items()]
