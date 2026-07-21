"""SC-002: every adp.chat.tools TOOL_REGISTRY handler must be read-only.

Mirrors tests/unit/agents/test_toolkit_boundary.py's mechanical-enforcement
approach (ADP-SPEC-039 SC-005) -- rather than trusting a `get_`/`list_`
naming convention, this walks each handler's AST, resolves every store/
aggregate function it calls (including ones imported inline inside the
handler body, this codebase's established deferred-import pattern), and
inspects THOSE functions' own source for the exact SQLAlchemy Core write
idiom used throughout every store.py in this codebase
(`<table>.insert()`/`.update()`/`.delete()`). A handler later edited to call
a write function under a read-sounding name would still be caught here,
since the check follows the call graph rather than trusting the name.
"""

from __future__ import annotations

import ast
import importlib
import inspect

from adp.chat.tools import TOOL_REGISTRY

# Data-model.md's own read-only naming contract for a TOOL_REGISTRY handler.
_ALLOWED_NAME_PREFIXES = ("get_", "list_")
_ALLOWED_NAME_SUFFIXES = ("_summary", "_status")

_WRITE_IDIOMS = (".insert(", ".update(", ".delete(")


def _resolve_local_import_aliases(func) -> dict[str, str]:
    """Map each `import`/`from ... import ...` alias used inside `func`'s own
    body to the dotted module path it refers to (e.g. "bstore" ->
    "adp.business.store" for `from adp.business import store as bstore`)."""
    source = inspect.getsource(func)
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = alias.name
    return aliases


def _called_function_paths(func) -> set[str]:
    """Every `module_alias.function_name(...)` call inside `func`'s body,
    resolved to a dotted path via that function's own local import aliases."""
    aliases = _resolve_local_import_aliases(func)
    source = inspect.getsource(func)
    tree = ast.parse(source)
    paths: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            alias = node.func.value.id
            module_path = aliases.get(alias)
            if module_path:
                paths.add(f"{module_path}.{node.func.attr}")
    return paths


def _load_function(dotted_path: str):
    module_path, _, func_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def test_every_tool_registry_handler_name_is_read_only_by_convention():
    for tool in TOOL_REGISTRY:
        name = tool.handler.__name__
        assert name.startswith(_ALLOWED_NAME_PREFIXES) or name.endswith(
            _ALLOWED_NAME_SUFFIXES
        ), f"{tool.name!r} handler {name!r} doesn't match the read-only naming contract"


def test_no_tool_registry_handler_directly_issues_a_write():
    violations = []
    for tool in TOOL_REGISTRY:
        source = inspect.getsource(tool.handler)
        for idiom in _WRITE_IDIOMS:
            if idiom in source:
                violations.append(f"{tool.name}: handler itself contains {idiom!r}")
    assert violations == [], "\n".join(violations)


def test_no_tool_registry_handler_calls_a_write_issuing_function():
    """The call-graph check data-model.md requires: follow every call the
    handler makes into another module's function and inspect THAT function's
    source, not just the handler's own body or its name."""
    violations = []
    for tool in TOOL_REGISTRY:
        for dotted_path in _called_function_paths(tool.handler):
            called = _load_function(dotted_path)
            called_source = inspect.getsource(called)
            for idiom in _WRITE_IDIOMS:
                if idiom in called_source:
                    violations.append(
                        f"{tool.name}: calls {dotted_path} which contains {idiom!r}"
                    )
    assert violations == [], "\n".join(violations)
