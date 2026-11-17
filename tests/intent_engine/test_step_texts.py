"""FlowGuard is a tool for the agent (R101): its lines and rules say what is known and who decides. None orders the agent
to ask or tell the owner, or makes the owner's yes a step; the agent decides when to raise a question. FlowGuard 4.3
said `-> ask owner (not asked yet)`, `needs the owner's yes` and, in its rules block, `Tell the owner only when it says
ask owner`.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ('ask owner', 'ask the owner', 'tell the owner', "owner's yes", "owner's agreement", 'needs the owner',
          'until the owner answers')


def _texts(path):
    """The string literals of one module that are not docstrings: what FlowGuard prints, its templates and messages."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
                  and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value


def test_no_line_rule_or_template_orders_the_agent_to_ask_the_owner():
    found = [f'{path.relative_to(ROOT)}:{line}: {text[:120]!r}' for path in sorted((ROOT / 'flowguard').rglob('*.py'))
             for line, text in _texts(path) if any(order in text.casefold() for order in ORDERS)]
    assert found == [], '\n'.join(found)


def test_the_agent_facing_documents_leave_the_question_to_the_agent():
    # The skill's agent prompt still said `tell the owner when it says ask owner` after 5.0 removed that step, and the
    # intent guide and the reference made the owner's yes or agreement a condition of an except=.
    for name in ('AGENTS.md', 'README.md', '.agents/skills/flowguard/SKILL.md', '.agents/skills/flowguard/reference.md',
                 '.agents/skills/flowguard/agents/openai.yaml', 'docs/intent-guide.md'):
        text = (ROOT / name).read_text(encoding='utf-8').casefold()
        assert not [order for order in ORDERS if order in text], name
        if name != 'docs/intent-guide.md':
            assert 'who decides' in text, name
