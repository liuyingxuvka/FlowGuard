"""Inventory omissions belong to the declared feature, not unrelated methods.

Native execution and projection are owned by adapter_boundary; this small model
describes only membership in the existing inventory check.
"""
from flowguard.flow import Model, need

m = Model("native operation scope", covers=["flowguard/flow/adapter.py"])
m.field("phase", ("new", "checked"), "new")
m.field("scope", ("pending", "all", "class", "method"), "pending")
m.field("operation", ("pending", "covered", "sibling", "unknown"), "pending")
m.field("result", ("pending", "required", "outside", "unknown"), "pending")

@m.action(scope=("all", "class", "method"), operation=("covered", "sibling", "unknown"))
def inventory(s, scope, operation):
    need(s["phase"] == "new")
    s["scope"], s["operation"] = scope, operation
    s["result"] = ("required" if scope == "all" or operation == "covered" else
                   "unknown" if operation == "unknown" else
                   "outside" if scope == "method" else "required")
    s["phase"] = "checked"

m.terminal("phase", ("checked",))
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
