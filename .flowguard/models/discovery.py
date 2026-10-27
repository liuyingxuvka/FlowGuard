"""Discovery finds every entrypoint shape, attributes each state write to its writer and follows effects through injection.

Each event adds one code shape to an empty project. The state is a projection of
what discover_inventory reports for it: entrypoints, state writers, the effect
kinds each entrypoint reaches and the calls resolved through an injected object.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import shutil
import tempfile

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.discover import discover_inventory, reachable_effects
from flowguard.map.inventory import build_inventory

MODEL_ID = "discovery"
COMPONENTS = ["map-discover", "map-inventory"]
IMPLEMENTED_BY = {
    "ResolveModule": "flowguard/map/inventory.py:resolve_module",
    "Discover": "flowguard/map/discover.py:discover",
    "ConsoleScripts": "flowguard/map/discover.py:console_scripts",
    "Function": "flowguard/map/discovery_syntax.py:_FileVisitor._visit_function",
    "Decorator": "flowguard/map/discovery_syntax.py:_FileVisitor._decorator_entrypoint",
    "WriteTarget": "flowguard/map/discovery_syntax.py:_FileVisitor._write_target",
    "Assign": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_Assign",
    "AnnotatedAssign": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_AnnAssign",
    "Call": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_Call",
    "Class": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_ClassDef",
    "Global": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_Global",
    "MainGuard": "flowguard/map/discovery_syntax.py:_FileVisitor.visit_If",
}
TESTED_BY = {'script_and_closure_calls_resolve': ['tests/test_discovery.py:test_nested_function_call_resolves', 'tests/test_discovery.py:test_import_local_to_enclosing_function_resolves', 'tests/test_discovery.py:test_sibling_script_import_resolves', 'tests/test_discovery.py:test_import_root_import_resolves'], 'entrypoints_found': ['tests/test_discovery.py:DiscoverTests.test_routes_commands_effects_and_state_writers', 'tests/test_discovery.py:test_discovery_finds_each_entry_and_effect_shape'], 'writes_attributed_to_writer': ['tests/test_discovery.py:test_discovery_finds_each_entry_and_effect_shape'], 'effects_reach_their_entrypoints': ['tests/test_discovery.py:DiscoverTests.test_routes_commands_effects_and_state_writers', 'tests/test_discovery.py:test_discovery_finds_each_entry_and_effect_shape'], 'injected_attribute_resolves': ['tests/test_discovery.py:test_injected_collaborator_resolves_to_its_class'], 'nothing_invented': ['tests/test_discovery.py:test_discovery_finds_each_entry_and_effect_shape']}

SHAPES = {
    "argparse_command": {"cmd.py": "import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser()\n"
                                   "    sub = parser.add_subparsers()\n    sub.add_parser('sync')\n    return parser.parse_args()\n"},
    "route_decorator": {"web.py": "from flask import Flask\napp = Flask(__name__)\n\n\n@app.route('/items', methods=['POST'])\n"
                                  "def create_item():\n    return 'ok'\n"},
    "console_script": {"tool.py": "def run():\n    return 0\n",
                       "pyproject.toml": "[project]\nname = 'probe'\n[project.scripts]\nprobe-tool = 'tool:run'\n"},
    "main_guard": {"job.py": "def work():\n    return 1\n\n\nif __name__ == '__main__':\n    work()\n"},
    "self_write": {"counter.py": "class Counter:\n    def __init__(self):\n        self.count = 0\n\n"
                                 "    def bump(self):\n        self.count += 1\n"},
    "module_global_write": {"registry.py": "SEEN = 0\n\n\ndef mark():\n    global SEEN\n    SEEN = SEEN + 1\n"},
    "file_write_effect": {"save.py": "def save(text):\n    with open('out.txt', 'w') as handle:\n        handle.write(text)\n\n\n"
                                     "if __name__ == '__main__':\n    save('x')\n"},
    "subprocess_effect": {"shell.py": "import subprocess\n\n\ndef build():\n    return subprocess.run(['make'])\n\n\n"
                                      "if __name__ == '__main__':\n    build()\n"},
    "injected_writer": {
        "store.py": "class Store:\n    def __init__(self, path):\n        self.path = path\n\n"
                    "    def save(self, text):\n        with open(self.path, 'w') as handle:\n            handle.write(text)\n",
        "service.py": "class Service:\n    def __init__(self, store):\n        self.store: \"Store\" = store\n\n"
                      "    def add(self, text):\n        self.store.save(text)\n",
        "app.py": "from service import Service\nfrom store import Store\n\n\ndef main():\n    Service(Store('notes.txt')).add('a')\n\n\n"
                  "if __name__ == '__main__':\n    main()\n"},
    "effect_word_in_string": {"words.py": "HELP = 'run subprocess or open a socket'\n\n\n"
                                          "def describe():\n    return 'subprocess.run and requests.post'\n"},
    "script_closure_calls": {'scripts/run.py': 'from helper import _sibling\nfrom rootdep import _root\n\ndef sibling(): return _sibling()\n\ndef outer():\n    def _nested(): return 1\n    def inner(): return _nested()\n    return inner()\n\ndef outer_local():\n    from localdep import _local\n    def inner(): return _local()\n    return inner()\n\ndef rooted(): return _root()\n', 'scripts/helper.py': 'def _sibling(): return 1\n', 'scripts/localdep.py': 'def _local(): return 1\n', 'lib/rootdep.py': 'def _root(): return 1\n'},
}
# What discovery reports for each shape: (entrypoints, state writers, entrypoint -> reached effect kind, injected calls).
EXPECTED = {
    "argparse_command": (("cli_command cmd.py:main",), (), (), ()),
    "route_decorator": (("http_route web.py:create_item",), (), (), ()),
    "console_script": (("console_script tool.py:run",), (), (), ()),
    "main_guard": (("main_call job.py:work", "main_guard job.py:<module>"), (), (), ()),
    "self_write": ((), ("Counter.count <- Counter.__init__", "Counter.count <- Counter.bump"), (), ()),
    "module_global_write": ((), ("<module>.SEEN <- mark",), (), ()),
    "file_write_effect": (("main_call save.py:save", "main_guard save.py:<module>"), (), ("save.py:save fs_write",), ()),
    "subprocess_effect": (("main_call shell.py:build", "main_guard shell.py:<module>"), (), ("shell.py:build subprocess",), ()),
    "injected_writer": (("main_call app.py:main", "main_guard app.py:<module>"), (), ("app.py:main fs_write",),
                        ("service.py#Service.add -> store.py#Store.save",)),
    "effect_word_in_string": ((), (), (), ()),
    "script_closure_calls": ((), (), (), ('scripts/run.py#outer.inner -> scripts/run.py#outer._nested', 'scripts/run.py#outer_local.inner -> scripts/localdep.py#_local', 'scripts/run.py#rooted -> lib/rootdep.py#_root', 'scripts/run.py#sibling -> scripts/helper.py#_sibling')),
}
ENTRY_KIND = {"argparse_command": "cli_command", "route_decorator": "http_route", "console_script": "console_script",
              "main_guard": "main_guard"}
WRITERS = {"self_write": "Counter.bump", "module_global_write": "mark"}
EFFECT = {"file_write_effect": "fs_write", "subprocess_effect": "subprocess", "injected_writer": "fs_write"}


@dataclass(frozen=True)
class State:
    event: str = ""
    entrypoints: tuple = ()
    writers: tuple = ()
    reach: tuple = ()
    injected: tuple = ()


class Discover:
    name = "Discover"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        result = State(event, *EXPECTED[event])
        if self.defect == "misses_command" and event == "argparse_command":
            result = replace(result, entrypoints=())
        elif self.defect == "writer_is_the_attribute" and event == "injected_writer":
            result = replace(result, writers=("Service.store <- Service.store",))
        elif self.defect == "reach_stops_at_injection" and event == "injected_writer":
            result = replace(result, reach=())
        elif self.defect == "ignores_injection" and event == "injected_writer":
            result = replace(result, injected=())
        elif self.defect == "invents_effect" and event == "effect_word_in_string":
            result = replace(result, reach=("words.py:describe subprocess",))
        if self.defect == "drops_sibling_script_import" and event == "script_closure_calls":
            result = replace(result, injected=tuple(edge for edge in result.injected if "#sibling ->" not in edge))
        return (FunctionResult(event, result, label=event),)


def _rule(name, events, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in events or predicate(state)
                     else InvariantResult.fail(message))


INVARIANTS = (
    _rule("script_and_closure_calls_resolve", {"script_closure_calls"},
          lambda state: state.injected == EXPECTED["script_closure_calls"][3],
          "sibling scripts, declared roots and enclosing functions must resolve through one module resolver"),
    _rule("entrypoints_found", set(ENTRY_KIND),
          lambda state: any(entry.startswith(ENTRY_KIND[state.event] + " ") for entry in state.entrypoints),
          "an entrypoint shape was not listed as an entrypoint"),
    _rule("writes_attributed_to_writer", {"self_write", "module_global_write", "injected_writer"},
          lambda state: all(writer.partition(" <- ")[2] != writer.partition(" <- ")[0] for writer in state.writers)
          and all(not writer.startswith("Service.store") for writer in state.writers)
          and (state.event not in WRITERS or any(writer.endswith(" <- " + WRITERS[state.event]) for writer in state.writers)),
          "a state write was not attributed to the function that performs it"),
    _rule("effects_reach_their_entrypoints", set(EFFECT),
          lambda state: any(item.endswith(" " + EFFECT[state.event]) for item in state.reach),
          "an entrypoint does not reach the effect its calls perform"),
    _rule("injected_attribute_resolves", {"injected_writer"},
          lambda state: "service.py#Service.add -> store.py#Store.save" in state.injected,
          "a call through an injected attribute did not resolve to the injected class"),
    _rule("nothing_invented", {"effect_word_in_string"}, lambda state: not state.entrypoints and not state.reach,
          "a word inside a string produced an entrypoint or an effect"),
)


def _explorer(defect=""):
    return Explorer(Workflow((Discover(defect),)), (State(),), tuple(SHAPES), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in
            ("drops_sibling_script_import", "misses_command", "writer_is_the_attribute", "reach_stops_at_injection", "ignores_injection", "invents_effect")}


def _observe(event):
    with tempfile.TemporaryDirectory(prefix="flowguard-discovery-model-") as directory:
        root = Path(directory)
        for relative, source in SHAPES[event].items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(source, encoding="utf-8")
        import inspect
        kwargs = {"import_roots": ("lib",)} if event == "script_closure_calls" and "import_roots" in inspect.signature(build_inventory).parameters else {}
        inv = build_inventory(root, [], write_cache=False, **kwargs)
        raw = discover_inventory(root, inv, write_cache=False)
        entries, writers, reach = [], [], []
        for path, facts in sorted(raw["files"].items()):
            for entry in facts.get("entrypoints", []):
                entries.append(f"{entry['kind']} {path}:{entry['symbol']}")
                reach.extend(f"{path}:{entry['symbol']} {kind}"
                             for kind in reachable_effects(raw, f"{path}#{entry['symbol']}"))
            writers.extend(f"{attr} <- {writer}" for attr, found in facts.get("state", {}).items() for writer in found)
        injected = [f"{source} -> {target}" for source, targets in raw.get("injected_edges", {}).items() for target in targets]
        if event == "script_closure_calls":
            callers = {"scripts/run.py#sibling", "scripts/run.py#outer.inner", "scripts/run.py#outer_local.inner", "scripts/run.py#rooted"}
            injected = [f"{source} -> {target}" for source, targets in raw.get("edges", {}).items()
                        if source in callers for target in targets]
        return State(event, tuple(sorted(entries)), tuple(sorted(writers)), tuple(sorted(reach)), tuple(sorted(injected)))


class RealDiscovery:
    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, step):
        self.state = _observe(step.function_input)
        return ReplayObservation(function_name=step.function_name, observed_output=step.function_input,
                                 observed_state=self.state)

    def observe_state(self):
        return self.state


def conformance():
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        last = replay_trace(trace=trace, adapter=RealDiscovery(), invariants=INVARIANTS,
                            rules=(projected_state_matches(), projected_output_matches()))
        if not last.ok:
            return last
    return last
