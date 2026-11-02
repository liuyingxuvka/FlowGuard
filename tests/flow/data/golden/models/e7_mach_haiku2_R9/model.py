"""Design model for REQUEST.md (request 9): regular maintenance of tools.

One tool and three members: members only interact through the queue and the hold; three
are needed so that the queue can hold two people behind the holder. The tool is one object,
so that its fields are frozen on purpose once it is lost.

Modelled: the tool's condition (shop, loan, inspection, repair, lost), who has it on
loan, the rental count since the last repair (maintain_every), the rental count since
the last inspection (inspect_every, the existing feature), the hold and the queue.

Not modelled (they do not change which state follows which): days, due days and
overdue, fees and charges, renewals, blocks, branches, messages.

The count fields saturate at the setting they are compared with, so the domains are
0..maintain_every and 0..inspect_every; the variations below stay inside them.
"""
from machine import Machine, need

from itertools import permutations

MEMBERS = ["M1", "M2", "M3"]
NONE = "none"
TOOL = "T"                    # the tool is one object (its life ends when it is lost)
# the holder is not in the queue and cannot queue: at most all the others wait
QUEUES = [q for n in range(len(MEMBERS)) for q in permutations(MEMBERS, n)]

m = Machine("request 9: maintenance of a tool (one tool, three members)",
            settings=dict(maintain_every=4, inspect_every=5),
            variations=dict(maintain_every=[0, 1, 2, 3], inspect_every=[0, 1, 2, 3]))
S = m.settings

m.field("cond", ["shop", "loan", "inspection", "repair", "lost"], "shop", over=[TOOL])
m.field("who", [NONE] + MEMBERS, NONE, over=[TOOL])                     # the member with it on loan
m.field("count", range(0, 5), 0, over=[TOOL])                           # rentals since the last repair
m.field("ins", range(0, 6), 0, over=[TOOL])                             # rentals since the last inspection/repair
m.field("held", [NONE] + MEMBERS, NONE, over=[TOOL])                    # held for the member first in line
m.field("queue", QUEUES, (), over=[TOOL])
m.terminal("cond", ["lost"])


def back_in_shop(s):
    """The tool is on the shelf: hold it for the first member in the queue, if any."""
    s["cond", TOOL] = "shop"
    q = s["queue", TOOL]
    if q:
        s["held", TOOL], s["queue", TOOL] = q[0], q[1:]
    else:
        s["held", TOOL] = NONE


@m.action(p=MEMBERS)
def rent(s, p):
    need(s["cond", TOOL] == "shop", "not in the shop")
    need(s["held", TOOL] in (NONE, p), "held for another member")
    s["cond", TOOL], s["who", TOOL], s["held", TOOL] = "loan", p, NONE
    s["count", TOOL] = min(s["count", TOOL] + 1, max(S["maintain_every"], 1))
    s["ins", TOOL] = min(s["ins", TOOL] + 1, max(S["inspect_every"], 1))


@m.action()
def return_tool(s):
    need(s["cond", TOOL] == "loan", "not on loan")
    s["who", TOOL] = NONE
    every, insp = S["maintain_every"], S["inspect_every"]
    if every > 0 and s["count", TOOL] >= every:
        s["cond", TOOL] = "repair"             # maintenance: a normal return, goes to repair, no charge
    elif insp > 0 and s["ins", TOOL] >= insp:
        s["cond", TOOL] = "inspection"
    else:
        back_in_shop(s)


@m.action()
def return_damaged(s):
    need(s["cond", TOOL] == "loan", "not on loan")
    s["who", TOOL], s["cond", TOOL] = NONE, "repair"


@m.action()
def mark_lost(s):
    need(s["cond", TOOL] == "loan", "not on loan")
    s["who", TOOL], s["cond", TOOL], s["held", TOOL], s["queue", TOOL] = NONE, "lost", NONE, ()


@m.action()
def inspect_pass(s):
    need(s["cond", TOOL] == "inspection", "not waiting for inspection")
    s["ins", TOOL] = 0
    back_in_shop(s)


@m.action()
def inspect_fail(s):
    need(s["cond", TOOL] == "inspection", "not waiting for inspection")
    s["ins", TOOL] = 0
    s["cond", TOOL] = "repair"


@m.action()
def repaired(s):
    need(s["cond", TOOL] == "repair", "not in repair")
    s["count", TOOL] = 0                       # every repair restarts both counts
    s["ins", TOOL] = 0
    back_in_shop(s)


@m.action(p=MEMBERS)
def reserve(s, p):
    need(s["who", TOOL] != p, "member has it on loan")
    need(p not in s["queue", TOOL] and s["held", TOOL] != p, "member already waits for it")
    need(s["cond", TOOL] == "loan" or s["held", TOOL] != NONE, "only a tool on loan or held can be reserved")
    s["queue", TOOL] = s["queue", TOOL] + (p,)


@m.action(p=MEMBERS)
def cancel(s, p):
    if p in s["queue", TOOL]:
        s["queue", TOOL] = tuple(x for x in s["queue", TOOL] if x != p)
    else:
        need(s["held", TOOL] == p, "no reservation")
        back_in_shop(s)                  # the hold goes to the next in line, or is released


# ---------------------------------------------------------------- the promises of the request
m.always("on loan exactly when someone has it",
         lambda s: (s["cond", TOOL] == "loan") == (s["who", TOOL] != NONE))
m.always("a hold is only for a tool in the shop",
         lambda s: s["held", TOOL] == NONE or s["cond", TOOL] == "shop")
m.always("a tool in the shop with people waiting is held for one of them",
         lambda s: not (s["cond", TOOL] == "shop" and s["held", TOOL] == NONE and s["queue", TOOL]))

m.only_when("no rental starts while the tool is due its maintenance", "rent",
            lambda s, p: not (S["maintain_every"] > 0 and s["count", TOOL] >= S["maintain_every"]))
m.after("exactly the Nth rental's normal return goes to repair", "return_tool",
        lambda b, a: (a["cond", TOOL] == "repair") ==
        (S["maintain_every"] > 0 and b["count", TOOL] >= S["maintain_every"]))
m.after("maintenance holds nothing and keeps the queue", "return_tool",
        lambda b, a: a["cond", TOOL] != "repair" or (a["held", TOOL] == NONE and a["queue", TOOL] == b["queue", TOOL]))
m.after("damage does not restart the count (only the repair does)", "return_damaged",
        lambda b, a: a["cond", TOOL] == "repair" and a["count", TOOL] == b["count", TOOL])
m.after("a repair restarts the count from 0", "repaired",
        lambda b, a: a["count", TOOL] == 0 and a["ins", TOOL] == 0)
m.after("an inspection that passes does not restart the maintenance count", "inspect_pass",
        lambda b, a: a["count", TOOL] == b["count", TOOL])
m.after("a failed inspection does not restart the maintenance count", "inspect_fail",
        lambda b, a: a["count", TOOL] == b["count", TOOL])

m.progress("a tool in repair or inspection is eventually back in the shop or lost",
           when=lambda s: s["cond", TOOL] in ("repair", "inspection"),
           goal=lambda s: s["cond", TOOL] in ("shop", "lost"))
m.progress("a member waiting for a tool gets it held, unless it is lost", over=MEMBERS,
           when=lambda s, p: p in s["queue", TOOL],
           goal=lambda s, p: s["held", TOOL] == p or s["cond", TOOL] == "lost")

MACHINE = m
