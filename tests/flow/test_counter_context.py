"""A finite count must not hide a lost business action behind an unrelated cycle."""
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model

RENTAL = 'from flowguard.flow import Model, need\nm = Model("rental")\nm.field("uses", range(4), 0)\nm.field("cond", ["available", "loan", "inspection"], "available")\n@m.action()\ndef rent(s):\n    need(s["cond"] == "available", "not available")\n    need(s["uses"] < 3, "maintenance is needed")\n    s["uses"] += 1\n    s["cond"] = "loan"\n@m.action()\ndef return_tool(s):\n    need(s["cond"] == "loan", "not on loan")\n    s["cond"] = "available"\n@m.action()\ndef inspect(s):\n    need(s["cond"] == "available", "not available")\n    s["cond"] = "inspection"\n@m.action()\ndef inspected(s):\n    need(s["cond"] == "inspection", "not inspected")\n    s["cond"] = "available"\nMODEL = m\n'

def test_counted_rental_is_stuck_without_maintenance_despite_inspection_cycle(project):
    project.flow("rental", RENTAL)
    report = check_model(load_model(project.root / ".flowguard/flow/rental.py", project.root))
    stuck = [f for f in report.findings if f.kind == "STUCK"]
    assert stuck and any("rent" in f.text for f in stuck), [f.text for f in report.findings]
    repaired = RENTAL.replace("MODEL = m", '@m.action()\ndef maintain(s):\n    need(s["cond"] == "available", "not available")\n    s["uses"] = 0\nMODEL = m')
    project.flow("rental", repaired)
    report = check_model(load_model(project.root / ".flowguard/flow/rental.py", project.root))
    assert not [f for f in report.findings if f.kind == "STUCK"], [f.text for f in report.findings]
