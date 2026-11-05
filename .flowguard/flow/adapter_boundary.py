"""One adapter boundary; native execution is the only production owner.
Left out: business data and worker scheduling, which their own models describe.
"""
from flowguard.flow import Model, need

m = Model("native adapter boundary",
          covers=["flowguard/flow/adapter.py:AdapterBinding.execute",
                  "flowguard/flow/adapter.py:_RecordedAdapter.apply_step"],
          note="expected data stays on the comparison side")
m.field("phase", ["fresh", "ready", "called", "observed", "compared", "failed"], "fresh")

@m.action()
def construct(s):
    need(s["phase"] == "fresh", "construct once")
    s["phase"] = "ready"

@m.action()
def native_call(s):
    need(s["phase"] == "ready", "native construction required")
    s["phase"] = "called"

@m.action()
def native_engine_failure(s):
    need(s["phase"] == "ready", "native construction required")
    s["phase"] = "failed"

@m.action()
def project_actual(s):
    need(s["phase"] == "called", "a native call is observed first")
    s["phase"] = "observed"

@m.action()
def compare(s):
    need(s["phase"] == "observed", "project actual observations before comparison")
    s["phase"] = "compared"

m.terminal("phase", ["compared", "failed"])
m.progress("ready work reaches comparison or visible engine failure",
           when=lambda s: s["phase"] == "ready",
           goal=lambda s: s["phase"] in ("compared", "failed"))
MODEL = m
