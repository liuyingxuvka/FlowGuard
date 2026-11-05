"""Private S2 foundation, design M6 / FG-822 (round13 complete-only amendment).

This models the model-side comparison, not native confirmation or owner decisions.
An added repair or source-bound model correction may preserve scope; a text edit
alone never proves weakening. Native/regression evidence is a later owner.
"""
from flowguard.flow import Model, need

m = Model("conflict history")
CASES = ("cap_replay_gone", "complete_replay_present", "scope_shrunk", "scope_unknown", "obligation_removed",
         "source_descriptors_missing",
         "added_repair", "model_correction")
m.field("phase", ("open", "held", "candidate"), "open")
m.field("case", ("not_seen", *CASES), "not_seen")
m.field("complete", (False, True), False)
m.field("condition_absent", (False, True), False)
m.field("scope_retained", (False, True), False)
m.field("obligations_retained", (False, True), False)
m.field("code_fixed", (False,), False)


@m.action(case=CASES, note="M6: retain incomplete/different/unknown/removed obligations")
def compare(s, case):
    need(s["phase"] == "open")
    s["case"] = case
    s["complete"] = case != "cap_replay_gone"
    s["condition_absent"] = case != "complete_replay_present"
    s["scope_retained"] = case not in ("scope_shrunk", "scope_unknown")
    s["obligations_retained"] = case not in ("obligation_removed", "source_descriptors_missing")
    ready = s["complete"] and s["condition_absent"] and s["scope_retained"] and s["obligations_retained"]
    s["phase"] = "candidate" if ready else "held"


@m.action(note="A later final check can reconsider a retained conflict")
def next_check(s):
    need(s["phase"] != "open")
    s["phase"] = "open"
    s["case"] = "not_seen"
    s["complete"] = False
    s["condition_absent"] = False
    s["scope_retained"] = False
    s["obligations_retained"] = False


m.always("only retained complete scope permits model absence",
         lambda s: s["phase"] != "candidate" or
         (s["complete"] and s["condition_absent"] and s["scope_retained"] and s["obligations_retained"]))
m.always("model comparison never claims a code fix", lambda s: not s["code_fixed"])
m.reach("added repair can be compared", lambda s: s["case"] == "added_repair" and s["phase"] == "candidate")
m.reach("model correction needs no new owner approval",
        lambda s: s["case"] == "model_correction" and s["phase"] == "candidate")
MODEL = m
