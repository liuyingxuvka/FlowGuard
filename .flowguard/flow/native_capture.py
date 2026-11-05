"""One native call keeps every actual outcome; observation and judgment may fail explicitly.

Arguments, heap graphs, output bytes and source identities are verified by native tests.
This finite model covers only outcome retention and publication, not the SUT's behavior.
"""
from flowguard.flow import Model, need

m = Model("native capture outcomes",
          note="One public call; unknown evidence and engine failure never publish a judgment.")
CALLS = m.objects("call", "C1")
m.field("phase", ["idle", "captured", "published", "unknown", "import-unknown", "class-unknown", "engine-error"], "idle", over=CALLS, source="R15")
m.field("actual", ["none", "success", "refusal", "crash", "unknown", "engine-error"], "none", over=CALLS, source="R15")
m.field("retained", [False, True], False, over=CALLS, source="R15")
m.field("judged", [False, True], False, over=CALLS, source="R15")
m.field("initialized", [False, True], False, over=CALLS, source="R15")
m.field("environment", ["none", "temporary", "unsupported"], "none", over=CALLS, source="R15")
m.field("env_inputs_retained", [False, True], False, over=CALLS, source="R15")
m.field("env_current", [False, True], True, over=CALLS, source="R15")
m.field("initializations", [0, 1], 0, over=CALLS, source="R15")
m.field("env_changes", [0, 1], 0, over=CALLS, source="R15")
m.field("class_scope", ["pending", "unused-tool", "business-read", "business-mutated", "dynamic"], "pending", over=CALLS, source="R15")


@m.action(c=CALLS, event=["none", "temporary", "unsupported"], source="R15")
def initialize(s, c, event):
    need(s["phase", c] == "idle" and not s["initialized", c], "one bounded import initialization")
    s["environment", c] = event
    s["initializations", c] += 1
    s["initialized", c] = True
    s["env_inputs_retained", c] = event == "temporary"
    if event == "unsupported":
        s["phase", c], s["actual", c] = "import-unknown", "unknown"


@m.action(c=CALLS, source="R15")
def inherited_environment_changed(s, c):
    need(s["env_inputs_retained", c] and s["env_current", c], "an identified inherited key changed")
    s["env_current", c] = False
    s["env_changes", c] += 1


@m.action(c=CALLS, access=["unused-tool", "business-read", "business-mutated", "dynamic"], source="R15")
def observe_class(s, c, access):
    need(s["phase", c] == "idle" and s["initialized", c] and s["class_scope", c] == "pending", "one class observation boundary")
    s["class_scope", c] = access
    if access in ("business-mutated", "dynamic"):
        s["phase", c], s["actual", c] = "class-unknown", "unknown"


@m.action(c=CALLS, outcome=["success", "refusal", "crash", "unknown", "engine-error"], source="R15")
def capture(s, c, outcome):
    need(s["phase", c] == "idle", "a call is captured once")
    need(s["class_scope", c] != "pending", "actual class cells have an observation scope")
    s["actual", c] = outcome
    s["retained", c] = outcome in ("success", "refusal", "crash")
    s["phase", c] = "captured" if s["retained", c] else outcome


@m.action(c=CALLS, fault=[False, True], source="R15")
def judge(s, c, fault):
    need(s["phase", c] == "captured", "judgment requires an actual retained call")
    s["phase", c] = "engine-error" if fault else "published"
    s["judged", c] = not fault


m.terminal("phase", ["published", "unknown", "import-unknown", "class-unknown", "engine-error"], source="R15")
m.always("all actual call outcomes remain evidence",
         lambda s: all(s["actual", c] not in ("success", "refusal", "crash") or s["retained", c] for c in CALLS), source="R15")
m.always("unknown and engine errors never become a successful judgment",
         lambda s: all(not s["judged", c] or s["phase", c] == "published" for c in CALLS), source="R15")
m.always("publication requires retained actual evidence",
         lambda s: all(s["phase", c] != "published" or s["retained", c] for c in CALLS), source="R15")
m.always("publication records the completed judgment",
         lambda s: all((s["phase", c] == "published") == s["judged", c] for c in CALLS), source="R15")
m.always("temporary import environment changes retain their keyed inputs",
         lambda s: all(s["environment", c] != "temporary" or s["env_inputs_retained", c] for c in CALLS), source="R15")
m.always("unsupported environment effects never publish calls",
         lambda s: all(s["environment", c] != "unsupported" or
                       (s["phase", c] == "import-unknown" and s["actual", c] == "unknown") for c in CALLS), source="R15")
m.always("initialization occurs once before capture",
         lambda s: all(s["initializations", c] <= 1 and (s["phase", c] == "idle" or s["initialized", c]) for c in CALLS), source="R15")
m.always("changed inherited keys invalidate current input identity",
         lambda s: all(s["env_changes", c] <= 1 and (s["env_current", c] == (s["env_changes", c] == 0)) and
                       (not s["env_changes", c] or s["env_inputs_retained", c]) for c in CALLS), source="R15")
m.always("business class changes and dynamic namespace reads remain unknown",
         lambda s: all(s["class_scope", c] not in ("business-mutated", "dynamic") or
                       (s["phase", c] == "class-unknown" and s["actual", c] == "unknown" and not s["judged", c]) for c in CALLS), source="R15")
m.always("published calls have an actual class observation scope",
         lambda s: all(s["retained", c] is False or s["class_scope", c] != "pending" for c in CALLS), source="R15")
MODEL = m
