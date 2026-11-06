"""Identity (`moved?` never re-points), constant identity, incremental re-linking and impact."""
import subprocess

STANDING = """
def refusal(member, today):
    if member.suspended:
        return "suspended"
    if (today - member.expires_on).days > 3:
        return "expired"
    if member.owed > 50:
        return "owes"
    return None
"""


def test_rename_and_move_is_proposed_never_repointed(repo):
    repo.write({"standing.py": STANDING, "policy.py": "LIMIT = 1\n",
                "rooms.py": "from standing import refusal\n\ndef book(m, t):\n    return refusal(m, t) is None\n"})
    m = repo.build()
    old_fp = m.node("standing:refusal")["fp"]
    m.close()
    repo.write({"standing.py": "", "policy.py": "LIMIT = 1\n" + STANDING.replace("def refusal", "def standing_refusal")})
    m = repo.build()
    assert m.node("standing:refusal") is None                       # never silently re-pointed
    assert m.node("policy:standing_refusal")["fp"] == old_fp
    proposals = m.moved()
    assert [p["line"] for p in proposals] == ["moved? standing:refusal -> policy:standing_refusal (same body)"]
    impact = m.impact(["standing.py", "policy.py"])
    assert impact["removed"] == ["standing:refusal"] and "policy:standing_refusal" in impact["added"]
    assert impact["removed_readers"]["standing:refusal"] == ["rooms", "rooms:book"]
    assert {e["dst"] for e in m.edges("rooms")} == {"missing:standing:refusal"}


def test_moved_with_an_edited_body_reads_similar_or_gone(repo):
    body = STANDING + "".join(f"\ndef helper{i}(x):\n    return x + {i}\n" for i in range(3))
    repo.write({"standing.py": body})
    m = repo.build()
    m.close()
    repo.write({"standing.py": body.replace("def refusal", "def why_not").replace("> 50", "> 60")})
    m = repo.build()
    [p] = m.moved(["standing:refusal"])
    assert p["new"] == "standing:why_not" and p["how"].startswith("similar body")


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def test_moved_from_git_history_and_shallow_clone(repo, tmp_path):
    repo.write({"standing.py": STANDING})
    git(repo.path, "init", "-q")
    git(repo.path, "add", ".")
    git(repo.path, "commit", "-qm", "one")
    repo.write({"standing.py": "# moved\n", "policy.py": STANDING.replace("def refusal", "def refusal_v2")})
    git(repo.path, "add", ".")
    git(repo.path, "commit", "-qm", "two")
    m = repo.build()                                                  # a fresh store: no memory of refusal
    [p] = m.moved(["standing:refusal"], rev="HEAD~1")
    assert p["line"] == "moved? standing:refusal -> policy:refusal_v2 (same body)"
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo.path}", str(shallow)], check=True)
    from flowguard.structure import build
    s = build(shallow, tmp_path / "s2" / "map.sqlite")
    [p] = s.moved(["standing:refusal"], rev="HEAD~1")
    assert p["new"] is None and p["line"] == "anchor gone (no history: use fetch-depth 0)"


CONST = {
    "limits.py": """
        GRACE_DAYS = 3
        POLICY = {"grace": 3, "cap": 50}
        class Limits:
            GRACE = 3
    """,
    "pkg/__init__.py": "from limits import GRACE_DAYS as G\n",
    "a.py": """
        from limits import GRACE_DAYS
        def a(ended):
            if ended > GRACE_DAYS:
                raise ValueError("late")
    """,
    "b.py": """
        import limits
        def b(days):
            if days > limits.GRACE_DAYS:
                return False
            return True
    """,
    "c.py": """
        def c(x):
            if x > 3:
                raise ValueError("literal three")
    """,
    "d.py": """
        from limits import Limits, POLICY
        from pkg import G
        class Desk(Limits):
            def open(self, days):
                return days <= self.GRACE
        def d(days, owed):
            if owed > POLICY["cap"]:
                return "owes"
            if days > G:
                return "late"
    """,
}


def ident(m, node):
    return [(s["const"], s["value"], s["identity"]) for s in m.sites(node)]


def test_constant_identity_and_readers_of_a_changed_constant(repo):
    repo.write(CONST)
    m = repo.build()
    assert ident(m, "a:a") == [("GRACE_DAYS", "3", "limits:GRACE_DAYS")]
    assert ident(m, "b:b") == [("limits.GRACE_DAYS", "3", "limits:GRACE_DAYS")]
    assert ident(m, "c:c") == [("3", "3", None)]
    assert ident(m, "d:Desk.open") == [("self.GRACE", "3", "limits:Limits.GRACE")]   # through the base class
    assert ident(m, "d:d") == [("POLICY['cap']", "50", "limits:POLICY['cap']"), ("G", "3", "limits:GRACE_DAYS")]
    home = m.other_homes("a:a", weak=True)
    assert "b:b" in [h["id"] for h in home]
    m.close()
    repo.write({"limits.py": CONST["limits.py"].replace("GRACE_DAYS = 3", "GRACE_DAYS = 7")})
    m = repo.build()
    assert m.stats["parsed"] == 1                                       # importers re-linked, not re-read
    assert ident(m, "a:a") == [("GRACE_DAYS", "7", "limits:GRACE_DAYS")]
    assert ident(m, "d:d")[1] == ("G", "7", "limits:GRACE_DAYS")       # through the package re-export
    impact = m.impact(["limits.py"])
    assert impact["constants"] == [{"id": "limits:GRACE_DAYS", "old": "3", "new": "7"}]
    assert impact["constant_readers"]["limits:GRACE_DAYS"] == ["a:a", "b:b", "d:d"]
    assert "c:c" not in impact["dirty"]


def test_incremental_relinks_only_changed_files_and_importers(repo):
    files = {f"m{i}.py": f"def f{i}(x):\n    return x + {i}\n" for i in range(6)}
    files["user.py"] = "from m0 import f0\n\ndef use(x):\n    return f0(x)\n"
    files["tests/test_user.py"] = "from user import use\n\ndef test_use():\n    assert use(1) == 1\n"
    repo.write(files)
    m = repo.build()
    assert (m.stats["parsed"], m.stats["linked"]) == (8, 8)
    m.close()
    m = repo.build()
    assert (m.stats["parsed"], m.stats["linked"], m.stats["changed"]) == (0, 0, False)
    m.close()
    repo.write({"m0.py": "def f0(x):\n    return x - 1\n"})
    m = repo.build()
    assert (m.stats["parsed"], m.stats["linked"]) == (1, 2)             # m0 and its importer user
    impact = m.impact(["m0.py"])
    assert impact["changed"] == ["m0:f0"] and impact["callers"] == ["user:use"]
    assert impact["tests"] == ["tests/test_user.py"]
    m.close()
    repo.write({"m5.py": "def f5(x):\n    return x * 5\n"})
    m = repo.build()
    assert (m.stats["parsed"], m.stats["linked"]) == (1, 1)             # nothing imports m5
    assert m.impact(["m5.py"])["tests"] == []
