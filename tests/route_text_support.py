"""Shared assertions for repository-owned skill route tests."""
from collections import Counter
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

LINKS = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")
CODES = re.compile(r"`([^`\n]+)`")


def _slug(heading):
    return re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")


def local_link(origin, link):
    value = urlsplit(link)
    if value.scheme or value.netloc:
        return None
    path = (origin.parent / unquote(value.path)).resolve() if value.path else origin
    return path, unquote(value.fragment)


def check_route_texts(route, texts, flags, *, skill_root, project_root, project_prefixes):
    """Check the common route-text contract; callers own route and CLI discovery."""
    paragraphs = Counter(
        " ".join(part.split())
        for text in texts.values()
        for part in re.split(r"\n\s*\n", text)
        if len(part.split()) >= 8
    )
    for paragraph, count in paragraphs.items():
        assert count == 1, f"{route}: repeated paragraph: {paragraph}"
    for origin, text in texts.items():
        for link in LINKS.findall(text):
            resolved = local_link(origin, link)
            if resolved is None:
                continue
            target, fragment = resolved
            assert target.exists(), f"{route}: dead link: {link} in {origin}"
            if fragment:
                headings = re.findall(r"^#+ (.+)$", target.read_text(encoding="utf-8"), re.M)
                assert fragment in {
                    _slug(heading) for heading in headings
                }, f"{route}: missing heading: {link} in {origin}"
        for code in CODES.findall(text):
            if code.startswith(
                ("grep ", "git ", "pip ", "python -m pytest", "python -m flowguard")
            ):
                continue
            for option in re.findall(r"--[a-z0-9][\w-]*", code):
                assert option in flags, f"{route}: unknown option: {code}"
            if code.startswith(("references/", "assets/", "scripts/", "agents/")):
                target = skill_root / code.split()[0].split("#", 1)[0]
            elif code.startswith(project_prefixes):
                target = project_root / code.split()[0].split("#", 1)[0]
            else:
                continue
            if "<" in code or "*" in code:
                continue
            assert target.exists(), f"{route}: missing path: {code}"
