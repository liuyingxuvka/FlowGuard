"""Inventory omissions belong to the declared feature, not unrelated methods.

Native execution and projection are owned by adapter_boundary; this small model
describes inventory membership and scope selection before native comparisons.
"""
from flowguard.flow import Model, need

m = Model("native operation scope", covers=["flowguard/flow/adapter.py", "flowguard/flow/affected.py", "flowguard/flow/native_evidence.py"])
m.field("phase", ("new", "checked"), "new")
m.field("scope", ("pending", "all", "class", "method"), "pending")
m.field("operation", ("pending", "covered", "sibling", "unknown"), "pending")
m.field("result", ("pending", "required", "outside", "unknown"), "pending")
m.field("input_case", ("pending", "inventory", "same", "code", "data", "mixed"), "pending")
m.field("comparisons", ("pending", "changed", "all"), "pending")

@m.action(scope=("all", "class", "method"), operation=("covered", "sibling", "unknown"))
def inventory(s, scope, operation):
    need(s["phase"] == "new")
    s["input_case"], s["comparisons"] = "inventory", "changed"
    s["scope"], s["operation"] = scope, operation
    s["result"] = ("required" if scope == "all" or operation == "covered" else
                   "unknown" if operation == "unknown" else
                   "outside" if scope == "method" else "required")
    s["phase"] = "checked"

@m.action(code=(False, True), data=(False, True))
def select_changed_operations(s, code, data):
    need(s["phase"] == "new")
    s["input_case"] = "mixed" if code and data else "data" if data else "code" if code else "same"
    s["comparisons"] = "all" if data else "changed"
    s["scope"], s["operation"], s["result"] = "all", "covered", "required"
    s["phase"] = "checked"

m.always("changed physical inputs require every native operation",
         lambda s: s["input_case"] not in ("data", "mixed") or s["comparisons"] == "all")
m.reach("code-only changes retain operation selection", lambda s: s["input_case"] == "code" and s["comparisons"] == "changed")
m.reach("data-only changes compare the complete operation scope", lambda s: s["input_case"] == "data" and s["comparisons"] == "all")
m.reach("mixed code and data cannot omit another operation", lambda s: s["input_case"] == "mixed" and s["comparisons"] == "all")

m.terminal("phase", ("checked",))
m.terminal("input_case", ("inventory", "same", "code", "data", "mixed"))
m.terminal("comparisons", ("changed", "all"))
m.terminal("scope", ("all", "class", "method"))
m.terminal("operation", ("covered", "sibling", "unknown"))
m.terminal("result", ("required", "outside", "unknown"))
m.always("empty covers retains the full receiver boundary", lambda s:
         s["phase"] != "checked" or s["scope"] != "all" or s["result"] == "required")
m.always("a known method scope excludes unrelated siblings", lambda s:
         s["phase"] != "checked" or s["scope"] != "method" or s["operation"] != "sibling" or s["result"] == "outside")
m.always("unknown membership never proves absence", lambda s:
         s["phase"] != "checked" or s["scope"] == "all" or s["operation"] != "unknown" or s["result"] == "unknown")
MODEL = m
