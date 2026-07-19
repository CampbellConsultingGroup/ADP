"""SC-005: the Agent Review toolkit must not depend on any single domain
module, so a second adapter (for a different screen) could reuse it without
modification (ADP-SPEC-039 FR-005). Mechanically enforced here rather than
just asserted -- walks every import in src/adp/agents/, including ones
deferred inside a function body to dodge an import cycle, since a hidden
runtime dependency would violate FR-005 just as much as a module-level one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import adp.agents

# The concrete domain adapters that exist in this codebase today. FR-005 is
# actually about "any single domain module", not just these two, but these
# are the only domain packages that exist to violate it against.
_FORBIDDEN_PREFIXES = ("adp.business", "adp.application")


def _imported_module_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_agents_toolkit_has_no_domain_module_imports():
    agents_dir = Path(adp.agents.__file__).parent
    py_files = sorted(agents_dir.rglob("*.py"))
    assert py_files, "expected to find source files under src/adp/agents/"

    violations = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for name in _imported_module_names(tree):
            if name.startswith(_FORBIDDEN_PREFIXES):
                violations.append(f"{py_file.relative_to(agents_dir.parent)}: imports {name!r}")

    assert violations == [], "toolkit module(s) import a single domain module:\n" + "\n".join(
        violations
    )
