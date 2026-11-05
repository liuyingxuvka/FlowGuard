"""Pilot semantic replay over the shared native test recorder."""
import json
from flowguard.native.testrec import _Recorder, _RecipeError, _json_value, record
from flowguard.native.session import UnsupportedWorld


def replay_prefixes(session, recordings):
    """Keep only concrete shipped public prefixes, never the original test assertions."""
    from .explore import _terms, plain, observations

    rows = recordings.get("recordings", []) if isinstance(recordings, dict) else recordings
    witnesses, ignored, divergences, prefixes, replays = {}, [], [], [], []
    original_start = session.start
    original_ledger = session.rule_ledger

    def retain(row):
        for kind, entity in session.spec["entities"].items():
            if not plain(session.query("system", entity["list"])):
                return False
        terms = _terms(session)
        last = session.last
        if last and last["call"].get("construct"):
            receiver = last["call"]["receiver"]
            if plain(session.query(receiver, "screen", property=True)) != "home":
                raise UnsupportedWorld("a test UI must be constructed at home")
        if last and "name" in last["call"] and last["call"]["name"] in session.spec["actions"]:
            terms.append({"kind": "action", "receiver": last["call"].get("receiver", "system"),
                          "name": last["call"]["name"], "outcome": last["outcome"]})
        for term in terms:
            witness = {"semantic": term, "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                       "start": {}, "origin": "test", "test": row["test"],
                       "source": row.get("source"), "digest": row.get("digest")}
            key = json.dumps(term, sort_keys=True)
            previous = witnesses.get(key)
            if previous is None or (len(witness["prefix"]), witness["test"]) < (len(previous["prefix"]), previous["test"]):
                witnesses[key] = witness
        prefixes.append({"test": row["test"], "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                         "start": {}, "observations": observations(session)})
        return True

    try:
        for recording in rows:
            if original_ledger is not None:
                from .capture import Ledger
                session.rule_ledger = Ledger(session.spec)
                session._capture_prefix = None
            accepted = []
            session.start = {}
            session.reset()
            profile = recording.get("settings", {})
            if profile and profile != session.spec.get("shipped", {}):
                ignored.append({"test": recording["test"], "settings": profile})
            valid_prefix, valid_outcomes = [], []
            eligible = retain(recording)
            if eligible and original_ledger is not None:
                accepted.append(session._capture_origin())
            stop = recording.get("stop")
            limit = min(len(recording["events"]), stop["index"]) if stop else len(recording["events"])
            for index, event in enumerate(recording["events"][:limit]):
                recipe = {key: value for key, value in event.items() if key != "outcome"}
                try:
                    row = session.step(recipe)
                    if row["outcome"] != event["outcome"]:
                        divergences.append({"test": recording["test"], "index": index,
                                            "expected": event["outcome"], "actual": row["outcome"]})
                        stop = {"kind": "outcome", "index": index}
                        break
                    valid_prefix.append(recipe)
                    valid_outcomes.append(row["outcome"])
                    eligible = retain(recording)
                    if eligible and original_ledger is not None:
                        accepted.append(session._capture_origin())
                except (UnsupportedWorld, ValueError, OSError) as exc:
                    divergences.append({"test": recording["test"], "index": index, "reason": str(exc)})
                    stop = {"kind": "unsupported", "index": index, "reason": str(exc)}
                    break
            if stop and stop["kind"] == "edit":
                divergences.append({"test": recording["test"], **stop})
            replays.append({"test": recording["test"], "prefix": valid_prefix, "outcomes": valid_outcomes,
                            "start": {}, "eligible": eligible, "stop": stop})
            if original_ledger is not None:
                original_ledger.update(session.rule_ledger.dump(accepted=accepted))
    finally:
        session.rule_ledger = original_ledger
        session._capture_prefix = None
        session.start = original_start
        session.reset()
    return {"witnesses": [witnesses[key] for key in sorted(witnesses)], "ignored_settings": ignored,
            "divergences": divergences, "prefixes": prefixes, "replays": replays,
            "recorded_tests": len(rows)}
