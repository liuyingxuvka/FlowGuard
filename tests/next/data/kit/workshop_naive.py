"""Tool life after R10 (repairs only at the main branch).
Left out: fees and members (no guard or rule reads them)."""
from flowguard._next import Model, need

m = Model("workshop", covers=["counter/core.py:Counter"], config="counter.config:Config",
          note="two tools: tools do not interact here except through the shelf")
S = m.settings
m.setting("maintain_every", source="R9", vary=[0, 2])     # 4, read from Config.maintain_every
TOOLS = m.objects("tool", "T1", "T2")
m.field("cond", ["shop", "loan", "transit", "repair"], "shop", over=TOOLS, source="R4",
        value_sources={"transit": "R10"})
m.field("branch", ["main", "library"], "main", over=TOOLS, source="R6")
m.field("rentals", range(0, S["maintain_every"] + 1), 0, over=TOOLS, source="R9",
        note="clamped at maintain_every: more rentals behave the same")


@m.action(t=TOOLS, source="R4")
def rent(s, t):
    need(s["cond", t] == "shop", "not on the shelf")
    s["cond", t] = "loan"
    s["rentals", t] = min(s["rentals", t] + 1, S["maintain_every"])


@m.action(t=TOOLS, source="R9")
def give_back(s, t):
    need(s["cond", t] == "loan", "not on loan")
    if S["maintain_every"] == 0 or s["rentals", t] < S["maintain_every"]:
        s["cond", t] = "shop"
    elif s["branch", t] == "main":
        s["cond", t] = "repair"
    else:
        with s.source("R10"):                # due away from main: it travels to main first
            s["cond", t] = "repair"


@m.action(t=TOOLS, source="R10")
def arrive(s, t):
    need(s["cond", t] == "transit", "not on the way")
    s["cond", t], s["branch", t] = "repair", "main"


@m.action(t=TOOLS, source="R9")
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "repairs only at main", source="R10")
    s["cond", t], s["rentals", t] = "shop", 0


@m.action(t=TOOLS, b=["main", "library"], source="R6")
def move(s, t, b):
    need(s["cond", t] == "shop", "only shelf tools move")
    need(s["branch", t] != b, "already there")
    s["branch", t] = b


m.option("workshop: repaired", lambda s, t: s["cond", t] == "repair", action="repaired", t=TOOLS, source="R10")
m.always("a tool in repair is at main",
         lambda s: all(s["branch", t] == "main" for t in TOOLS if s["cond", t] == "repair"), source="R10")
m.only_when("rent only from the shelf", "rent", lambda s, t: s["cond", t] == "shop", source="R4")
m.after("a repair restarts the count", "repaired", lambda b, a, t: a["rentals", t] == 0, source="R9")
m.progress("a tool in repair or on the way gets back to a shelf", over=TOOLS, source="R10",
           when=lambda s, t: s["cond", t] in ("transit", "repair"), goal=lambda s, t: s["cond", t] == "shop")
m.reach("a tool due at the library goes to main", lambda s: any(s["cond", t] == "transit" for t in TOOLS),
        source="R10")
MODEL = m
