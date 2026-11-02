"""Design model for REQUEST.md (regular maintenance), as one tool's life.

Only what the request changes or touches is in: the shelf, a loan, the repair state,
the inspection that the code already has, and the members waiting for the tool.
Money, days, the outbox and the audit log do not change what can happen, so they are
left out. Renewal is left out too: it does not change the rental count.

Settings are read at action time (S[...]) so that `--set` works; the field domains
are sized for the shipped settings.
"""
from machine import Machine, need

MEMBERS = ["M1", "M2"]
T = "T1"                                                   # the one tool
QUEUES = [(), ("M1",), ("M2",), ("M1", "M2"), ("M2", "M1")]   # first in line first

m = Machine("tool maintenance (REQUEST 9)", settings=dict(maintain_every=4, inspect_every=5))
S = m.settings


def maintenance_due(s):
    """The rental count since the last repair has reached the maintenance interval."""
    return S["maintain_every"] > 0 and s["rentals", T] >= S["maintain_every"]


def inspection_due(s):
    """The existing inspection counter (reset by any inspection and by any repair)."""
    return S["inspect_every"] > 0 and s["insp", T] >= S["inspect_every"]


def to_shop(s):
    """The tool is on the shelf; the first member in the queue gets the hold."""
    s["cond", T] = "shop"
    if s["queue", T]:
        s["holder", T], s["queue", T] = s["queue", T][0], s["queue", T][1:]


# ---------------------------------------------------------------- state
m.field("cond", ["shop", "loan", "repair", "inspection", "lost"], "shop", over=[T])
m.field("holder", [None] + MEMBERS, None, over=[T])                 # the member the tool is held for
m.field("queue", QUEUES, (), over=[T])                              # members waiting, first in line first
m.field("rentals", range(0, S["maintain_every"] + 1), 0, over=[T])  # rentals since the last repair
m.field("insp", range(0, S["inspect_every"] + 1), 0, over=[T])      # rentals since the last inspection/repair
m.terminal("cond", ["lost"])


# ---------------------------------------------------------------- actions
@m.action(who=MEMBERS)
def rent(s, who):
    need(s["cond", T] == "shop", "not on the shelf")
    need(s["holder", T] in (None, who), "held for another member")
    s["cond", T], s["holder", T] = "loan", None
    s["rentals", T] = min(s["rentals", T] + 1, S["maintain_every"])
    s["insp", T] = min(s["insp", T] + 1, S["inspect_every"])


@m.action()
def return_tool(s):
    """A normal return. The 4th rental (maintenance) comes before the inspection."""
    need(s["cond", T] == "loan", "not on loan")
    if maintenance_due(s):
        s["cond", T] = "repair"
    elif inspection_due(s):
        s["cond", T] = "inspection"
    else:
        to_shop(s)


@m.action()
def return_damaged(s):
    need(s["cond", T] == "loan", "not on loan")
    s["cond", T] = "repair"          # the member is charged; the count restarts only at the repair


@m.action()
def mark_lost(s):
    need(s["cond", T] == "loan", "not on loan")
    s["cond", T], s["holder", T], s["queue", T] = "lost", None, ()


@m.action()
def inspect_pass(s):
    need(s["cond", T] == "inspection", "not waiting for inspection")
    s["insp", T] = 0
    to_shop(s)


@m.action()
def inspect_fail(s):
    need(s["cond", T] == "inspection", "not waiting for inspection")
    s["insp", T] = 0
    s["cond", T] = "repair"


@m.action()
def repaired(s):
    """Staff record the repair (maintenance or damage). Counts restart from 0."""
    need(s["cond", T] == "repair", "not in repair")
    s["rentals", T] = 0
    s["insp", T] = 0
    to_shop(s)


@m.action(who=MEMBERS)
def reserve(s, who):
    need(who not in s["queue", T], "already waiting")
    need(s["holder", T] != who, "held for you")
    need(s["cond", T] == "loan" or s["holder", T] is not None,
         "only a tool on loan or held for another member can be reserved")
    s["queue", T] = s["queue", T] + (who,)


@m.action(who=MEMBERS)
def cancel(s, who):
    if who in s["queue", T]:
        s["queue", T] = tuple(x for x in s["queue", T] if x != who)
    else:
        need(s["holder", T] == who, "no reservation")
        s["holder", T] = None
        to_shop(s)


# ---------------------------------------------------------------- screens
m.option("rent", lambda s, who: s["cond", T] == "shop" and s["holder", T] in (None, who),
         action="rent", who=MEMBERS)
m.option("reserve", lambda s, who: who not in s["queue", T] and s["holder", T] != who
         and (s["cond", T] == "loan" or s["holder", T] is not None), action="reserve", who=MEMBERS)
m.option("cancel", lambda s, who: who in s["queue", T] or s["holder", T] == who,
         action="cancel", who=MEMBERS)
m.option("return", lambda s: s["cond", T] == "loan", action="return_tool")
m.option("return damaged", lambda s: s["cond", T] == "loan", action="return_damaged")
m.option("mark lost", lambda s: s["cond", T] == "loan", action="mark_lost")
m.option("inspection pass", lambda s: s["cond", T] == "inspection", action="inspect_pass")
m.option("inspection fail", lambda s: s["cond", T] == "inspection", action="inspect_fail")
m.option("record repaired", lambda s: s["cond", T] == "repair", action="repaired")


# ---------------------------------------------------------------- promises
m.always("a tool on the shelf is never due for maintenance",
         lambda s: not (s["cond", T] == "shop" and maintenance_due(s)))
m.always("a hold is only on a tool on the shelf",
         lambda s: s["holder", T] is None or s["cond", T] == "shop")
m.always("nobody waits for a tool they hold",
         lambda s: s["holder", T] not in s["queue", T])

m.after("each rental counts once (a renewal is not a rental)", "rent",
        lambda b, a, who: a["rentals", T] == min(b["rentals", T] + 1, S["maintain_every"]))
m.after("the 4th rental comes back to repair, not to the shelf", "return_tool",
        lambda b, a: not maintenance_due(b) or a["cond", T] == "repair")
m.after("a damaged return goes to repair", "return_damaged",
        lambda b, a: a["cond", T] == "repair")
m.after("a repair restarts the count at 0", "repaired",
        lambda b, a: a["rentals", T] == 0)
m.after("an inspection pass is not a repair: the count is not restarted", "inspect_pass",
        lambda b, a: a["rentals", T] == b["rentals", T])
m.after("a lost tool is never left", "*",
        lambda b, a, name, args: b["cond", T] != "lost" or a["cond", T] == "lost")

m.progress("a tool in repair goes back to the shelf",
           when=lambda s: s["cond", T] == "repair", goal=lambda s: s["cond", T] == "shop")
m.progress("a tool on loan comes back",
           when=lambda s: s["cond", T] == "loan", goal=lambda s: s["cond", T] != "loan")
m.progress("an inspection ends",
           when=lambda s: s["cond", T] == "inspection", goal=lambda s: s["cond", T] in ("shop", "repair"))
m.progress("a waiting member is held the tool or leaves the queue", over=MEMBERS,
           when=lambda s, who: who in s["queue", T],
           goal=lambda s, who: s["holder", T] == who or who not in s["queue", T])

m.reach("a 4th rental goes to repair", lambda s: S["maintain_every"] > 0
        and s["cond", T] == "repair" and s["rentals", T] == S["maintain_every"])
m.reach("a waiting member gets the tool after its repair",
        lambda s: s["cond", T] == "shop" and s["holder", T] is not None and s["rentals", T] == 0)

MACHINE = m
