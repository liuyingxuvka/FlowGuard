"""Bound operation probes precede honest, complete-scope native drift repair."""
from flowguard.flow import Model, need

m = Model("native operation coverage and drift reconciliation",
          covers=["flowguard/flow/native_evidence.py", "flowguard/flow/native_finding.py",
                  "flowguard/flow/project.py"])
m.field("phase", ("new", "observed", "drift", "held", "candidate", "tested", "closed"), "new")
m.field("operation_probed", (False, True), False)
m.field("inputs_retained", (False, True), False)
m.field("complete_scope", (False, True), False)
m.field("current_oracle_matches", (False, True), False)
m.field("regression_passed", (False, True), False)
m.field("classification", ("none", "drift_resolved", "model_corrected", "code_fixed"), "none")
m.field("probe_kind", ("none", "enabled", "refused"), "none")
m.field("code_relation", ("unknown", "same", "changed"), "unknown")
m.field("oracle_relation", ("unknown", "same", "changed"), "unknown")


@m.action(matches=(False, True), enabled=(False, True))
def probe_operation(s, matches, enabled):
    need(s["phase"] == "new")
    s["operation_probed"] = True
    s["probe_kind"] = "enabled" if enabled else "refused"
    s["phase"] = "observed" if matches else "drift"
    s["inputs_retained"] = not matches


@m.action(complete=(False, True), matches=(False, True), code=("unknown", "same", "changed"),
          oracle=("unknown", "same", "changed"))
def reconcile(s, complete, matches, code, oracle):
    need(s["phase"] == "drift")
    s["complete_scope"] = complete
    s["current_oracle_matches"] = matches
    s["code_relation"] = code
    s["oracle_relation"] = oracle
    ready = complete and matches and s["inputs_retained"]
    s["phase"] = "candidate" if ready else "held"
    if ready:
        s["classification"] = ("model_corrected" if code == "same" and oracle == "changed" else
                               "code_fixed" if code == "changed" and oracle == "same" else "drift_resolved")


@m.action()
def execute_repaired_regression(s):
    need(s["phase"] == "candidate")
    s["regression_passed"] = True
    s["phase"] = "tested"


@m.action()
def close(s):
    need(s["phase"] == "tested")
    s["phase"] = "closed"


@m.action()
def next_check(s):
    need(s["phase"] in ("observed", "held", "closed"))
    s["phase"] = "new"
    for key in ("operation_probed", "inputs_retained", "complete_scope", "current_oracle_matches", "regression_passed"):
        s[key] = False
    s["classification"] = s["probe_kind"] = "none"
    s["code_relation"] = "unknown"
    s["oracle_relation"] = "unknown"


m.always("a default native observation includes an operation",
         lambda s: s["phase"] == "new" or (s["operation_probed"] and s["probe_kind"] != "none"))
m.always("a new computation carries no previous closure authority",
         lambda s: s["phase"] != "new" or (not any(s[key] for key in
         ("operation_probed", "inputs_retained", "complete_scope", "current_oracle_matches", "regression_passed"))
         and s["classification"] == s["probe_kind"] == "none" and s["code_relation"] == s["oracle_relation"] == "unknown"))
m.always("repair labels follow actual code identity",
         lambda s: s["phase"] not in ("candidate", "tested", "closed") or s["classification"] ==
         ("model_corrected" if s["code_relation"] == "same" and s["oracle_relation"] == "changed" else
          "code_fixed" if s["code_relation"] == "changed" and s["oracle_relation"] == "same" else "drift_resolved"))
m.only_when("an operation probe starts the computation", "probe_operation",
            lambda s,matches,enabled: s["phase"] == "new")
m.only_when("a new check follows a finished observation", "next_check",
            lambda s: s["phase"] in ("observed", "held", "closed"))
m.always("drift closure keeps inputs, complete scope, current correspondence and an executed regression",
         lambda s: s["phase"] != "closed" or all(s[key] for key in
         ("inputs_retained", "complete_scope", "current_oracle_matches", "regression_passed")))
m.reach("model correction needs no new approval", lambda s: s["phase"] == "closed" and s["classification"] == "model_corrected")
m.reach("real code repair is distinct", lambda s: s["phase"] == "closed" and s["classification"] == "code_fixed")
m.reach("partial native absence stays held", lambda s: s["phase"] == "held" and not s["complete_scope"])
MODEL = m
