"""Windows coordinates each mutable record; unrelated records are independent."""
from flowguard.flow import Model, need

m = Model("record publication", covers=["flowguard/flow/_process.py", "flowguard/flow/project.py"])
m.field("owner", ("none", "reader", "writer"), "none")
m.field("generation", (0, 1), 0)


@m.action(actor=("reader", "writer"))
def acquire(s, actor):
    need(s["owner"] == "none")
    s["owner"] = actor


@m.action()
def publish(s):
    need(s["owner"] == "writer")
    s["generation"] = 1 - s["generation"]


@m.action()
def release_or_process_exit(s):
    need(s["owner"] != "none")
    s["owner"] = "none"


m.progress("a held record can be released", lambda s:s["owner"] != "none", lambda s:s["owner"] == "none")
m.only_when("publication requires the writer's ownership", "publish", lambda s:s["owner"] == "writer")
m.only_when("acquiring never steals a live owner", "acquire", lambda s,actor:s["owner"] == "none")
m.only_when("release requires an owner", "release_or_process_exit", lambda s:s["owner"] != "none")
m.reach("a complete replacement is possible", lambda s:s["generation"] == 1)
MODEL = m
