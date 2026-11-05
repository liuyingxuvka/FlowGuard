"""Draft vocabulary once, then leave completed model/adapter files to their author."""
from flowguard.flow import Model, need

m = Model("draft ownership", covers=["flowguard/flow/draft.py"])
m.field("phase", ("new", "read", "written", "owned", "invalid", "existing"), "new")
m.field("known_source_bases_declared", (False, True), False)

@m.action()
def read(s):
    need(s["phase"] == "new")
    s["phase"] = "read"
    s["known_source_bases_declared"] = True

@m.action()
def invalid_source(s):
    need(s["phase"] == "new")
    s["phase"] = "invalid"
    s["known_source_bases_declared"] = True  # Invalid input offers no class bindings.

@m.action()
def write_once(s):
    need(s["phase"] == "read")
    s["phase"] = "written"

@m.action()
def existing_output(s):
    need(s["phase"] == "read")
    s["phase"] = "existing"

@m.action()
def author_completes(s):
    need(s["phase"] == "written")
    s["phase"] = "owned"

m.terminal("phase", ("owned", "invalid", "existing"))
m.terminal("known_source_bases_declared", (True,))
m.reach("invalid input remains an error", lambda s: s["phase"] == "invalid")
m.reach("existing files are refused", lambda s: s["phase"] == "existing")
m.reach("known source bases are declared in the new draft", lambda s: s["phase"] == "written" and s["known_source_bases_declared"])
m.after("static reading includes known source bases", "read", lambda before, after: after["known_source_bases_declared"])
m.after("creation produces TODO files", "write_once", lambda before, after: after["phase"] == "written")
m.after("completed files belong to their author", "author_completes", lambda before, after: after["phase"] == "owned")
MODEL = m
