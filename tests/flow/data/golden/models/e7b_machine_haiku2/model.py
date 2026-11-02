"""Regular maintenance and repair of one tool, as the counter's return and repair rules see it.

Requirement (Request 9): after every `maintain_every`-th rental the tool gets a maintenance;
its normal return sends it to repair (no charge), not to the shelf; the rentals are counted
from the last repair, whatever the repair was for; a damaged or lost return keeps its
old path (damaged: repair and a charge; lost: gone for good). Repair ends with the staff
recording it. The existing inspection rule (`inspect_every`) shares the return path and is
modelled too, so the interaction is explicit.

Requirement (Request 10): every repair is done at the workshop of the main branch. `repaired`
is refused at any other branch; a tool in repair at another branch is sent to main first (and
is still in repair when it arrives); a repaired tool is back in the shop at main.

Requirement (Request 11): the holder of a held tool may ask for it to be brought to another
branch (`bring`, refused unless the tool is on the shelf at a different branch). A brought tool
is in transit and still held for the same member; when it arrives it is on the shelf, still held
(its queue is kept). A hold ends by the holder giving it up or by expiry (`end_hold`); the
hold clock is not modelled, but it does not run while the tool is in transit. Staff `transfer`
still refuses held tools: only `bring` moves them.

Charges, messages and the audit log are left out: they do not change what the tool does.
Members are reduced to "the holder" (the member the tool is held for) and "the waiter"
(at most one in the queue).
"""
from machine import Machine, need

m = Machine("regular maintenance and repair", settings=dict(maintain_every=4, inspect_every=5))
S = m.settings
T = "T"                       # the one tool; the fields are its life-cycle fields
IN_TRANSIT = ("transit", "transit_repair")

m.field("where", ["shop", "loan", "repair", "inspection", "lost", "transit", "transit_repair"],
        "shop", over=[T])
m.field("at", ["main", "other"], "main", over=[T])   # the branch it is at, or travelling to
m.field("held", [0, 1], 0, over=[T])          # 1: the shelf is held for the waiter
m.field("waiting", [0, 1], 0, over=[T])       # 1: a member is in the queue
m.field("rented", range(0, S["maintain_every"] + 1), 0, over=[T])       # since last repair
m.field("inspected_since", range(0, S["inspect_every"] + 1), 0, over=[T])  # since last inspection


def to_shelf(s):
    """_back_in_shop: the tool is on the shelf; a waiting member gets it held for them,
    unless it is already held (a brought tool keeps its holder and its queue)."""
    s["where", T] = "shop"
    if s["held", T] == 0 and s["waiting", T]:
        s["held", T], s["waiting", T] = 1, 0


def due_maintenance(s):
    n = S["maintain_every"]
    return n > 0 and s["rented", T] >= n


@m.action(who=["holder", "other"])
def rent(s, who):
    need(s["where", T] == "shop", "not on the shelf")
    need((s["held", T] == 1) == (who == "holder"), "held for someone else")
    s["where", T], s["held", T] = "loan", 0
    s["rented", T] = min(s["rented", T] + 1, S["maintain_every"])
    s["inspected_since", T] = min(s["inspected_since", T] + 1, S["inspect_every"])


@m.action()
def reserve(s):
    need(s["waiting", T] == 0, "already one member waiting")
    need(s["where", T] == "loan" or s["held", T] == 1,
         "only a tool on loan or held can be reserved")
    s["waiting", T] = 1


# ---- Request 11: a holder may ask for the held tool to be brought to another branch.
@m.action(to=["main", "other"])
def bring(s, to):
    """The holder asks for the tool held for them to be sent to `to`; it stays held."""
    need(s["held", T] == 1, "not held for a member")
    need(s["where", T] == "shop", "not on the shelf (it is on its way already)")
    need(s["at", T] != to, "already at that branch")
    s["where", T], s["at", T] = "transit", to


@m.action()
def end_hold(s):
    """The holder gives up the hold (or it expires on the shelf); the next member gets it."""
    need(s["held", T] == 1, "not held")
    s["held", T] = 0
    if s["where", T] == "shop" and s["waiting", T]:
        s["held", T], s["waiting", T] = 1, 0


@m.action()
def return_tool(s):
    need(s["where", T] == "loan", "not on loan")
    k = S["inspect_every"]
    if due_maintenance(s):                     # the maintenance rental: repair, no charge
        s["where", T] = "repair"
    elif k > 0 and s["inspected_since", T] >= k:
        s["where", T] = "inspection"
    else:
        to_shelf(s)


@m.action()
def return_damaged(s):
    need(s["where", T] == "loan", "not on loan")
    s["where", T] = "repair"


@m.action()
def mark_lost(s):
    need(s["where", T] == "loan", "not on loan")
    s["where", T], s["waiting", T] = "lost", 0


@m.action(result=["pass", "fail"])
def inspected(s, result):
    need(s["where", T] == "inspection", "not waiting for inspection")
    s["inspected_since", T] = 0
    if result == "pass":
        to_shelf(s)
    else:
        s["where", T] = "repair"


@m.action()
def repaired(s):
    need(s["where", T] == "repair", "not in repair")
    need(s["at", T] == "main", "not at main: repairs are done at the workshop")
    s["rented", T], s["inspected_since", T] = 0, 0
    to_shelf(s)


@m.action(to=["main", "other"])
def transfer(s, to):
    need(s["at", T] != to, "already at that branch")
    if s["where", T] == "repair":
        need(to == "main", "a tool in repair is only sent to main")
        s["where", T], s["at", T] = "transit_repair", to
    else:
        need(s["where", T] == "shop" and s["held", T] == 0, "only an available tool can be sent")
        s["where", T], s["at", T] = "transit", to


@m.action()
def receive(s):
    need(s["where", T] in IN_TRANSIT, "not in transit")
    if s["where", T] == "transit_repair":
        s["where", T] = "repair"
    else:
        to_shelf(s)


m.terminal("where", ["lost"])

m.always("a tool due for maintenance is never on the shelf",
         lambda s: not (s["where", T] == "shop" and due_maintenance(s)))
m.always("a tool on the shelf with someone waiting is held for them",
         lambda s: not (s["where", T] == "shop" and s["waiting", T] == 1 and s["held", T] == 0))
m.always("a held tool is on the shelf or on its way to a branch",
         lambda s: s["held", T] == 0 or s["where", T] in ("shop", "transit"))

m.after("a brought tool stays held for the same member, on its way",
        "bring", lambda b, a, to: a["held", T] == 1 and a["where", T] == "transit")
m.after("a held tool arrives still held", "receive",
        lambda b, a: b["held", T] == 0 or a["held", T] == 1)
m.after("a member waiting for a held tool stays in the queue when it arrives", "receive",
        lambda b, a: not (b["held", T] == 1 and b["waiting", T] == 1 and a["waiting", T] == 0))
m.after("ending a hold on the shelf passes the tool on", "end_hold",
        lambda b, a: b["where", T] != "shop" or a["held", T] == b["waiting", T])
m.progress("a held tool is rented or its hold ends", when=lambda s: s["held", T] == 1,
           goal=lambda s: s["held", T] == 0)
m.reach("a held tool is brought to another branch",
        lambda s: s["where", T] == "transit" and s["held", T] == 1)
m.reach("a brought tool arrives and is handed to its holder at the new branch",
        lambda s: s["where", T] == "shop" and s["held", T] == 1 and s["at", T] == "other")
m.reach("a held tool in transit is waited for",
        lambda s: s["where", T] == "transit" and s["held", T] == 1 and s["waiting", T] == 1)

m.after("the maintenance rental goes to repair, not to the shelf or inspection", "return_tool",
        lambda b, a: not (due_maintenance(b)) or a["where", T] == "repair")
m.after("a damaged return goes to repair", "return_damaged",
        lambda b, a: a["where", T] == "repair")
m.after("repair counts the rentals again from 0", "repaired",
        lambda b, a: a["rented", T] == 0)
m.after("a repaired tool is back in the shop at main", "repaired",
        lambda b, a: a["where", T] == "shop" and a["at", T] == "main")
m.after("a tool sent for repair arrives in repair", "receive",
        lambda b, a: b["where", T] != "transit_repair" or a["where", T] == "repair")
m.only_when("a tool in repair is only sent to main", "transfer",
            lambda s, to: s["where", T] != "repair" or to == "main")

m.progress("a tool in repair is repaired", when=lambda s: s["where", T] == "repair",
           goal=lambda s: s["where", T] != "repair")
m.progress("a tool on loan comes back or is lost", when=lambda s: s["where", T] == "loan",
           goal=lambda s: s["where", T] != "loan")
m.progress("a tool waiting for inspection is inspected",
           when=lambda s: s["where", T] == "inspection",
           goal=lambda s: s["where", T] != "inspection")
m.progress("a tool sent to another branch arrives",
           when=lambda s: s["where", T] in IN_TRANSIT,
           goal=lambda s: s["where", T] not in IN_TRANSIT)
m.progress("the waiting member gets the tool or the queue empties",
           when=lambda s: s["waiting", T] == 1, goal=lambda s: s["waiting", T] == 0)

m.reach("a tool goes to repair for its maintenance",
        lambda s: due_maintenance(s) and s["where", T] == "repair")
m.reach("a damaged tool goes to repair before its maintenance is due",
        lambda s: s["where", T] == "repair" and 0 < s["rented", T] < S["maintain_every"])
m.reach("a tool is inspected", lambda s: s["where", T] == "inspection")
m.reach("a tool in repair is sent from another branch to main",
        lambda s: s["where", T] == "transit_repair")
m.reach("a tool is repaired at main", lambda s: s["where", T] == "shop" and s["rented", T] == 0
        and s["at", T] == "main")

MACHINE = m
