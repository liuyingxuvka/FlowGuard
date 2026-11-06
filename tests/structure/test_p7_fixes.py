"""Fixtures for the P7/P5 map-base defects: each test reproduces one defect pattern on synthetic code.

Long literal sets, nodes of a new file in the delta, PEP 420 namespace packages, one module name in
several roots, tuple-unpacked constants, an implicit root that shadows an installed package or names a
namespace directory beside its package, calls through (function-level) package re-exports, one edge per
import statement, and the other-home tokens for versions, environment variable names and large
thresholds that are assigned before they are returned."""
import json


def test_a_long_literal_set_is_stored_as_valid_json(repo):
    names = [f"option_number_{i:03d}" for i in range(40)]          # about 900 characters of JSON
    repo.write({
        "app/__init__.py": "",
        "app/opts.py": f"""
            KNOWN = {tuple(names)!r}

            def known(name):
                if name in KNOWN:
                    return True
                return False

            def also_known(value):
                return value in {tuple(names)!r}
        """,
    })
    m = repo.build()                                               # used to raise JSONDecodeError
    site = next(s for s in m.sites("app.opts:known") if s["op"] == "In")
    assert len(json.loads(site["value"])) == 40
    found = m.other_homes("app.opts:known")
    assert found and found[0]["id"] == "app.opts:also_known" and "literal set" in found[0]["reason"]


def test_nodes_of_a_new_file_are_added_in_the_delta(repo):
    repo.write({"pkg/__init__.py": "", "pkg/old.py": "def old(x):\n    return x > 1\n"})
    m = repo.build()
    repo.write({"pkg/rel.py": "def parse_relations(text):\n    if not text:\n        raise ValueError('empty')\n    return text.split()\n"})
    m.refresh()
    got = m.impact()
    assert "pkg.rel:parse_relations" in got["added"] and "pkg.rel:parse_relations" in got["dirty"]
    assert "pkg.rel:parse_relations" in m.impact(["pkg/rel.py"])["added"]


def test_namespace_packages_resolve_without_missing_nodes(repo):
    repo.write({
        "tools/parity/compare.py": "LIMIT = 3\n\ndef check(x):\n    return x > LIMIT\n",
        "tools/parity/run.py": """
            from tools.parity import compare
            from tools.parity.compare import LIMIT
            import tools.parity

            def main(x):
                return compare.check(x) and x < LIMIT
        """,
        "tools/parity/broken.py": "from tools.parity import never_written\n",
    })
    m = repo.build()
    edges = {(e["dst"], e["line"]) for e in m.edges("tools.parity.run", kind="imports")}
    assert ("tools.parity.compare", 1) in edges and ("tools.parity.compare", 2) in edges
    assert not any(d.startswith("missing:") for d, _ in edges)
    assert {e["dst"] for e in m.edges("tools.parity.broken")} == {"missing:tools.parity:never_written"}
    assert {e["dst"] for e in m.edges("tools.parity.run:main", kind="calls")} == {"tools.parity.compare:check"}


def test_one_module_name_in_several_roots_is_chosen_per_importer(repo):
    loader = "def load(path):\n    return path\n"
    repo.write({
        "StepA/pyproject.toml": "[project]\nname = 'a'\n", "StepA/loader.py": loader + "def overlay_a():\n    return 1\n",
        "StepA/run.py": "from loader import load, overlay_a\n\ndef go():\n    return load('x'), overlay_a()\n",
        "StepB/pyproject.toml": "[project]\nname = 'b'\n", "StepB/loader.py": loader + "def overlay_b():\n    return 2\n",
        "StepB/run.py": "import loader\n\ndef go():\n    return loader.load('y')\n",
        "tools/probe.py": """
            import sys
            sys.path.insert(0, "StepB")
            from loader import overlay_b

            def go():
                return overlay_b()
        """,
    })
    m = repo.build()
    a, b = m.node("StepA.loader") or m.node("loader"), None
    files = {n["id"]: n["file"] for n in m.nodes(kind="module")}
    def target(src, kind="imports"):
        return {files.get(e["dst"]) for e in m.edges(src, kind=kind)}
    assert target("StepA.run" if "StepA.run" in files else "run") == {"StepA/loader.py"}
    run_b = next(i for i, f in files.items() if f == "StepB/run.py")
    assert target(run_b) == {"StepB/loader.py"}
    assert target("tools.probe") == {"StepB/loader.py"}
    calls = {e["dst"] for e in m.edges("tools.probe:go", kind="calls")}
    assert calls and all(m.node(c)["file"] == "StepB/loader.py" for c in calls)
    assert not [n for n in m.nodes(kind="missing")]


def test_tuple_unpacked_constants_are_bound_and_mapped(repo):
    repo.write({
        "num/__init__.py": "",
        "num/tol.py": "ATOL, RTOL = 1e-8, 1e-9\nfor _name in ('A',):\n    pass\n",
        "num/use.py": "from num.tol import ATOL, RTOL, _name\n\ndef close(a, b):\n    return abs(a - b) <= ATOL + RTOL * abs(b)\n",
    })
    m = repo.build()
    assert m.node("num.tol:ATOL")["sig"] == "1e-08" and m.node("num.tol:RTOL")
    assert not m.nodes(kind="missing")


def test_an_implicit_root_neither_shadows_an_installed_package_nor_names_its_neighbours(repo):
    repo.write({
        "tools/json/__init__.py": "def dumps(x):\n    return str(x)\n",      # a package named like the stdlib
        "tools/kit/__init__.py": "", "tools/kit/core.py": "def f():\n    return 1\n",
        "tools/scan/report.py": "def g():\n    return 2\n",                 # a namespace directory beside them
        "tools/scan/use.py": "import json\nfrom kit.core import f\nfrom tools.scan.report import g\n",
    })
    m = repo.build()
    assert m.node("tools.json:dumps") and not m.node("json:dumps")
    assert m.node("kit.core:f")                                               # the package that made the root
    assert m.node("tools.scan.report:g") and not m.node("scan.report:g")
    dsts = {e["dst"] for e in m.edges("tools.scan.use", kind="imports")}
    assert dsts == {"kit.core", "tools.scan.report"}                          # json is the standard library


def test_calls_through_package_re_exports_are_linked(repo):
    repo.write({
        "rep/__init__.py": "from .reports import build_optional_reports\nfrom . import reports as _r\n",
        "rep/reports.py": "def build_optional_reports(x):\n    return [x]\n",
        "cli/__init__.py": "",
        "cli/main.py": """
            from rep import build_optional_reports as top_level

            def lazy(x):
                from rep import build_optional_reports
                return build_optional_reports(x)

            def eager(x):
                return top_level(x)

            def through_module(x):
                import rep
                return rep.build_optional_reports(x)
        """,
    })
    m = repo.build()
    assert set(m.callers("rep.reports:build_optional_reports")) == {
        "cli.main:lazy", "cli.main:eager", "cli.main:through_module"}


def test_every_import_statement_gets_its_edge(repo):
    repo.write({
        "lib/__init__.py": "", "lib/util.py": "def u():\n    return 1\n",
        "lib/use.py": """
            from lib.util import u

            def one():
                from lib.util import u
                return u()

            def two():
                from lib.util import u
                return u()
        """,
    })
    m = repo.build()
    assert sorted(e["line"] for e in m.edges("lib.use", kind="imports")) == [1, 4, 8]


VERSIONS = {
    "plat/__init__.py": "",
    "plat/runtime.py": """
        import sys

        MIN_PYTHON = (3, 12)
        MAX_PYTHON_EXCLUSIVE = (3, 13)

        def is_supported_python(info=None):
            major, minor = (info or sys.version_info)[:2]
            return MIN_PYTHON <= (major, minor) < MAX_PYTHON_EXCLUSIVE
    """,
    "jobs/__init__.py": "",
    "jobs/guard.py": """
        import platform
        import sys

        def require_interpreter():
            if platform.python_version() != "3.12.10":
                raise SystemExit("use the pinned interpreter")

        def interpreter_ok():
            if sys.version_info[:2] != (3, 12):
                return False
            return True
    """,
    "jobs/other.py": """
        def page_size(n):
            if n > 50:
                return 50
            return n
    """,
}


def test_a_version_policy_written_three_ways_is_one_decision(repo):
    repo.write(VERSIONS)
    m = repo.build()
    found = {h["id"]: h for h in m.other_homes("plat.runtime:is_supported_python", 10)}
    assert {"jobs.guard:require_interpreter", "jobs.guard:interpreter_ok"} <= set(found), found
    assert "version 3.12" in found["jobs.guard:interpreter_ok"]["reason"]
    assert "jobs.other:page_size" not in found


CREDENTIALS = {
    "plat/__init__.py": "",
    "plat/credentials.py": """
        import os

        PROVIDER_VARIABLES = {"maps": "ACME_MAPS_TOKEN", "store": "ACME_STORE_KEY"}

        class CredentialBroker:
            def __init__(self, environment=None):
                self._environment = os.environ if environment is None else environment

            def _secret_for(self, provider):
                environment_variable = PROVIDER_VARIABLES.get(provider)
                if environment_variable is None:
                    return None
                value = self._environment.get(environment_variable, "")
                return value.strip() or None
    """,
    "jobs/__init__.py": "",
    "jobs/fetch.py": """
        import os

        def maps_token():
            token = os.environ.get("ACME_MAPS_TOKEN")
            if not token:
                raise RuntimeError("set ACME_MAPS_TOKEN")
            return token

        def store_key():
            return os.getenv("ACME_STORE_KEY") or None
    """,
    "jobs/home.py": """
        import os

        def home_dir():
            return os.environ.get("HOME_DIRECTORY_PATH", "/tmp")
    """,
}


def test_credential_variable_names_link_a_table_driven_broker_to_literal_reads(repo):
    repo.write(CREDENTIALS)
    m = repo.build()
    found = {h["id"]: h for h in m.other_homes("plat.credentials:CredentialBroker._secret_for", 10)}
    assert {"jobs.fetch:maps_token", "jobs.fetch:store_key"} <= set(found), found
    assert "reads env ACME_" in found["jobs.fetch:maps_token"]["reason"]
    assert "jobs.home:home_dir" not in found


TRANSFER = {
    "plat/__init__.py": "",
    "plat/storage.py": """
        LARGE_TRANSFER_BYTES = 1024 ** 3

        def build_download_plan(expected_transfer_bytes, available_disk_bytes):
            status = "ready"
            if expected_transfer_bytes is not None and expected_transfer_bytes > LARGE_TRANSFER_BYTES:
                status = "confirmation_required"
            if available_disk_bytes is not None and available_disk_bytes < 5:
                status = "blocked_disk"
            return status
    """,
    "plat/readiness.py": """
        from plat.storage import LARGE_TRANSFER_BYTES

        class Matrix:
            def apply_download_plan(self, estimated_transfer_bytes=None, available_disk_bytes=None):
                needs_confirmation = (estimated_transfer_bytes or 0) > LARGE_TRANSFER_BYTES
                outcome = "confirmation_required" if needs_confirmation else "ready"
                return outcome
    """,
    "plat/limits.py": """
        def check_upload(size_bytes):
            verdict = "ok"
            if size_bytes > 1073741824:
                verdict = "too_large"
            return verdict
    """,
}


def test_an_assigned_threshold_is_a_decision_site_with_identity_and_value(repo):
    repo.write(TRANSFER)
    m = repo.build()
    sites = m.sites("plat.storage:build_download_plan")
    assert any(s["identity"] == "plat.storage:LARGE_TRANSFER_BYTES" and s["leads"] == "return" for s in sites), sites
    found = {h["id"]: h for h in m.other_homes("plat.storage:build_download_plan", 10, weak=True)}
    assert "plat.readiness:Matrix.apply_download_plan" in found, found
    assert found["plat.readiness:Matrix.apply_download_plan"]["strength"] == "strong"
    assert "plat.limits:check_upload" in found                     # same 1 GiB value, written as a literal
