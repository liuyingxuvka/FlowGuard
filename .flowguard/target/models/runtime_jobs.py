"""One execution owner per input key; retain facts, never a current judgment."""
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "runtime_jobs"
PARENT = "map-jobs"
IMPLEMENTED_BY = {"Owner": "flowguard/map/jobs.py:key_lock",
                  "Run": "flowguard/map/jobs.py:run_or_attach",
                  "Store": "flowguard/map/jobs.py:Writer.save_slice",
                  "Inputs": "flowguard/map/jobs.py:prepare"}
TESTED_BY = {
    "one_owner_per_key": ["tests/behave/test_jobs.py:test_same_content_worktrees_attach_and_keep_the_original_snapshot"],
    "completed_facts_execute_once": ["tests/behave/test_jobs.py:test_slice_reuse_revalidates_inputs_and_never_stores_a_verdict"],
    "changed_inputs_reopen": ["tests/behave/test_jobs.py:test_slice_reuse_revalidates_inputs_and_never_stores_a_verdict"],
    "judgments_are_not_cached": ["tests/behave/test_jobs.py:test_slice_reuse_revalidates_inputs_and_never_stores_a_verdict"],
    "dead_owner_pending_resume": ["tests/behave/test_jobs.py:test_dead_worker_lock_is_released_and_foreground_reuses_completed_native_slice"],
}


@dataclass(frozen=True)
class Event:
    action: str
    owner: str = "first"
    slice: str = "one"


@dataclass(frozen=True)
class State:
    key: str = "v1"
    owners: tuple = ()
    done: tuple = ()
    executions: tuple = ()
    dead: bool = False
    reopened: bool = False
    resumed: bool = False
    previous_done: tuple = ()
    persisted: tuple = ("facts",)


class Protocol:
    name = "Run"
    reads = ("key", "owners", "done", "executions", "dead", "persisted")
    writes = ("key", "owners", "done", "executions", "dead", "reopened", "resumed", "previous_done", "persisted")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        current = replace(state, reopened=False, resumed=False, previous_done=state.done)
        if event.action == "claim" and len(state.done) < 2:
            owners = state.owners or (event.owner,)
            if self.defect == "two_owners" and event.owner not in owners:
                owners += (event.owner,)
            done = () if state.dead and self.defect == "forget_resume" else state.done
            current = replace(current, owners=owners, done=done, dead=False, resumed=state.dead)
        elif event.action == "finish":
            repeated = event.slice in state.done
            allowed = event.owner in state.owners and not repeated
            if repeated and self.defect == "rerun_completed":
                allowed = True
            if allowed:
                done = tuple(sorted(set((*state.done, event.slice))))
                current = replace(current, done=done, owners=() if len(done) == 2 else state.owners,
                                  executions=(*state.executions, (state.key, event.slice)))
        elif event.action == "die":
            owners = state.owners if self.defect == "dead_lock" else ()
            current = replace(current, owners=owners, dead=True)
        elif event.action == "inputs" and state.key != "v2":
            current = replace(current, key="v2", owners=(), dead=False, reopened=True,
                              done=state.done if self.defect == "reuse_changed" else ())
        elif event.action == "judge" and self.defect == "cache_judgment":
            current = replace(current, persisted=(*state.persisted, "judgment"))
        return (FunctionResult(event.action, current),)


INVARIANTS = (
    Invariant("one_owner_per_key", "concurrent callers attach to one active input-key owner",
              lambda s, t: len(s.owners) <= 1),
    Invariant("completed_facts_execute_once", "a validated completed slice is not executed again for the same inputs",
              lambda s, t: len(s.executions) == len(set(s.executions))),
    Invariant("changed_inputs_reopen", "changed execution inputs create pending work rather than reuse old facts",
              lambda s, t: not s.reopened or not s.done and not s.owners),
    Invariant("judgments_are_not_cached", "J and current verdicts are derived outside persisted execution facts",
              lambda s, t: "judgment" not in s.persisted),
    Invariant("dead_owner_pending_resume", "a dead owner releases ownership and resumption retains completed slices",
              lambda s, t: (not s.dead or not s.owners) and
              (not s.resumed or set(s.previous_done) <= set(s.done))),
)
EVENTS = (Event("claim"), Event("claim", "second"), Event("die"), Event("inputs"), Event("judge"),
          *(Event("finish", owner, part) for owner in ("first", "second") for part in ("one", "two")))
INITIAL = (State(), State(owners=("first",)),
           State(owners=("first",), done=("one",), executions=(("v1", "one"),)),
           State(dead=True, done=("one",), executions=(("v1", "one"),)),
           State(done=("one", "two"), executions=(("v1", "one"), ("v1", "two"))))


def make(defect=""):
    return Explorer(Workflow((Protocol(defect),)), INITIAL, EVENTS, invariants=INVARIANTS,
                    max_sequence_length=2, progress_steps=0)


def build_explorer():
    return make()


def broken_variants():
    return {name: make(name) for name in ("two_owners", "rerun_completed", "reuse_changed",
                                         "cache_judgment", "dead_lock", "forget_resume")}


def conformance():
    try:
        from flowguard.map import jobs
        from flowguard.map.inputs import file_stamp
    except ImportError as exc:
        return CodeFactsReport((Fact("native_jobs_api", False, str(exc)),))
    facts = []
    try:
        with TemporaryDirectory(prefix="fg-runtime-jobs-") as directory:
            root = Path(directory)
            (root / "src").mkdir()
            source = root / "src/data.txt"
            source.write_text("original execution input")
            request = {"operation": "model source-read facts", "slices": ["one", "two"],
                       "bases": [], "parameters": {}}
            job = jobs.prepare(root, files=["src/data.txt"], directories=["src"], request=request)
            executed = []

            def capture(writer, name):
                path = job.snapshot / "src/data.txt"
                row = {"data": path.read_text(), "footprint": {"reusable": True,
                       "files": {str(path): file_stamp(path)}, "directories": {}, "untracked": []}}
                writer.save_slice(name, row)
                executed.append(name)

            def execute(active, writer, deadline):
                for name in active.planned:
                    if writer.load_slice(name) is None:
                        capture(writer, name)

            with jobs.key_lock(job.path / "owner.lock") as first:
                with jobs.key_lock(job.path / "owner.lock") as second:
                    facts.append(Fact("one_owner_per_key", first and not second, repr((first, second))))
                attached = jobs.run_or_attach(job, execute=execute, worker_command=[], env={}, wait=0)
                facts.append(Fact("attach_does_not_execute", not attached["complete"] and not executed, repr(attached)))
                writer = jobs.Writer(job)
                capture(writer, "one")
                writer.progress()
            # A released OS lease with recorded pending work is the recovery
            # boundary; the bound regression additionally kills a real worker.
            resumed = jobs.run_or_attach(job, execute=execute, worker_command=[], env={}, wait=None)
            facts.append(Fact("dead_owner_pending_resume", resumed["complete"] and executed == ["one", "two"], repr(executed)))
            again = jobs.run_or_attach(job, execute=execute, worker_command=[], env={}, wait=None)
            facts.append(Fact("completed_facts_execute_once", again["complete"] and executed == ["one", "two"], repr(executed)))
            row = jobs.Writer(job).load_slice("one")
            for field in ("verdict", "judgment"):
                try:
                    jobs.Writer(job).save_slice("one", {**row, field: "current J / CLEAR"})
                except ValueError:
                    rejected = True
                else:
                    rejected = False
                facts.append(Fact("judgments_are_not_cached:" + field, rejected, field))
            source.write_text("changed execution input")
            changed = jobs.prepare(root, files=["src/data.txt"], directories=["src"], request=request)
            reopened = changed.key != job.key and not job.matches(root) and jobs.Writer(changed).load_slice("one") is None
            facts.append(Fact("changed_inputs_reopen", reopened, repr((job.key, changed.key))))
    except Exception as exc:
        facts.append(Fact("native_jobs_protocol", False, type(exc).__name__ + ": " + str(exc)))
    return CodeFactsReport(tuple(facts))
