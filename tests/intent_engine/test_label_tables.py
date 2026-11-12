"""Label tables that disagree: copies of one table of labels, and lookup tables that lack a key.

Planning Tool 0.6.28 kept three tables of org-unit type labels ('Main Department' / 'Main department', one
without ENTITY), two of role labels ('Sys Admin' / 'System Admin'), two backend ENTRY_TYPE_LABELS ('Flextime'
/ 'Flex Time') and ORG_UNIT_TYPE_TO_ROLE without ENTITY; the label check read none of them, because object
values are not literals it groups. The fixture below is synthetic and small; its expectations were written
from the files, not from a run.
"""
from contextlib import closing
import subprocess
import textwrap

from flowguard.intent import anchors, owners
from flowguard.intent.config import load_config
from flowguard.structure import build

FILES = {
    'frontend/src/utils/type-label.ts': '''
        const TYPE_LABELS: Record<string, string> = {
          ENTITY: 'Entity', BU: 'Business Unit', MAIN_DEPARTMENT: 'Main Department', TEAM: 'Team',
        };
        export const typeLabel = (type: string) => TYPE_LABELS[type] ?? type;
    ''',
    'frontend/src/pages/Detail.tsx': '''
        const DETAIL_LABELS: Record<string, string> = { BU: 'Business Unit', MAIN_DEPARTMENT: 'Main Department', TEAM: 'Team' };
        export const detail = (type: string) => DETAIL_LABELS[type] ?? type;
    ''',
    'frontend/src/pages/Admin.tsx': '''
        const TYPES = [
          { value: '', label: 'All types' },
          { value: 'ENTITY', label: 'Entity' },
          { value: 'BU', label: 'Business unit' },
          { value: 'MAIN_DEPARTMENT', label: 'Main department' },
          { value: 'TEAM', label: 'Team (all)' },
        ];
        export const types = () => TYPES;
    ''',
    'backend/src/role.ts': '''
        export const TYPE_TO_ROLE: Record<string, string> = { BU: 'HIGHER_MANAGEMENT', MAIN_DEPARTMENT: 'HIGHER_MANAGEMENT', TEAM: 'TEAM_LEADER' };
        export const OrgType = { ENTITY: 'ENTITY', BU: 'BU', MAIN_DEPARTMENT: 'MAIN_DEPARTMENT', TEAM: 'TEAM', AREA: 'AREA' };
    ''',
    'backend/src/grid.ts': "const ENTRY_LABELS = { SICK: 'Sick Leave', FLEXTIME: 'Flex Time', VACATION: 'Vacation' };\n",
    'backend/src/usage.ts': "const ENTRY_LABELS = { SICK: 'Sickness', FLEXTIME: 'Flextime', VACATION: 'Vacation' };\n",
    # Not label copies: CSS class lists, "My ..." navigation labels that agree on no key, a test's table.
    'frontend/src/ui/Button.tsx': "const SIZES = { sm: 'px-2 text-sm', md: 'px-4 text-base', lg: 'px-6 text-lg' };\n",
    'frontend/src/ui/Spinner.tsx': "const SIZES = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' };\n",
    'frontend/src/layout/Sidebar.tsx': "const MINE = { BU: 'My Unit', MAIN_DEPARTMENT: 'My Department', TEAM: 'My Team' };\n",
    'frontend/tests/labels.test.ts': "const EXPECTED = { BU: 'Business Units', MAIN_DEPARTMENT: 'Main Department', TEAM: 'Team' };\n",
}
ORG = ("Label tables disagree: frontend/src/utils/type-label.ts:1 TYPE_LABELS, frontend/src/pages/Admin.tsx:1 TYPES, frontend/src/pages/Detail.tsx:1 DETAIL_LABELS, backend/src/role.ts:1 TYPE_TO_ROLE: BU 'Business Unit' (TYPE_LABELS, DETAIL_LABELS) versus 'Business unit' (TYPES); MAIN_DEPARTMENT 'Main Department' (TYPE_LABELS, DETAIL_LABELS) versus 'Main department' (TYPES); DETAIL_LABELS lacks ENTITY; TYPE_TO_ROLE lacks ENTITY")
ENTRY = ("Label tables disagree: backend/src/grid.ts:1 ENTRY_LABELS, backend/src/usage.ts:1 ENTRY_LABELS: FLEXTIME 'Flex Time' (ENTRY_LABELS (grid.ts:1)) versus 'Flextime' (ENTRY_LABELS (usage.ts:1)); SICK 'Sick Leave' (ENTRY_LABELS (grid.ts:1)) versus 'Sickness' (ENTRY_LABELS (usage.ts:1))")


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=20).stdout


def _write(root, files):
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body).lstrip(), encoding='utf-8')


def _findings(root, base, everything):
    cfg = load_config(root)
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return owners.static_findings(cfg, graph, anchors.collect(graph), base, everything=everything)


def test_label_tables_that_disagree_are_findings_new_when_this_change_edits_one(tmp_path):
    _write(tmp_path, {'.gitignore': '.flowguard/cache/\n', **FILES})
    _git(tmp_path, 'init', '-q', '-b', 'main')
    _git(tmp_path, 'add', '.')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline')
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    def labels(found):
        return {issue.text: issue for issue in found.issues if issue.family == 'labels'}
    found = labels(_findings(tmp_path, base, True))
    assert sorted(found) == sorted([ENTRY, ORG]), found
    assert found[ORG].entry[0] == '[structure."labels:frontend/src/utils/type-label.ts:TYPE_LABELS"]'
    assert all(issue.fresh == frozenset() for issue in found.values())
    # An edit elsewhere in a file with a table leaves the finding old; an edit of a table makes it new, with the entry
    # to copy.
    detail = tmp_path / 'frontend/src/pages/Detail.tsx'
    detail.write_text(detail.read_text(encoding='utf-8') + 'export const other = 1;\n', encoding='utf-8')
    assert all(issue.fresh == frozenset() for issue in labels(_findings(tmp_path, base, False)).values())
    detail.write_text(detail.read_text(encoding='utf-8').replace("TEAM: 'Team' }", "TEAM: 'Teams' }"), encoding='utf-8')
    fresh = [issue for issue in labels(_findings(tmp_path, base, False)).values() if issue.fresh]
    assert len(fresh) == 1 and fresh[0].text.startswith(ORG.replace('; DETAIL_LABELS lacks ', "; TEAM 'Team' (TYPE_LABELS) versus 'Teams' (DETAIL_LABELS); DETAIL_LABELS lacks ")), fresh
    assert ' '.join(fresh[0].entry).endswith('[structure."labels:frontend/src/utils/type-label.ts:TYPE_LABELS"] decision = "Replace with the owner\'s decision: who owns this and '
                                             'why (at least 8 words)" source = "R<n>"'), fresh
