"""CEL expression engine boundary for EA patterns (934, research D1).

Pattern selectors and constraints are CEL expressions. The concrete library is
Google's ``cel-expr-python`` (the cel-cpp reference runtime), chosen by the spike
recorded in ``specs/934-pattern-metamodel/research.md`` D1 because it is the only
candidate with a real compile-time checker (undeclared names, overload mismatches,
return types) and a built-in iteration budget.

Everything outside this module talks to the :class:`CelEngine` protocol, so the
library can be swapped (fallback: ``common-expression-language``) without touching
callers. No method here raises: failures come back as :class:`CelError` /
:class:`CelResult` values.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Protocol

from cel_expr_python import cel

_T = cel.Type

# Declared CEL environment shared by compile checks (934) and evaluation (936).
PATTERN_CEL_VARIABLES: Mapping[str, str] = {
    "it": "dyn",
    "bindings": "map<string, list<dyn>>",
    "scope": "map<string, list<dyn>>",
}
PATTERN_CEL_FUNCTIONS: Mapping[str, str] = {
    "role": "role(string) -> list<string>",
    "bound": "bound(map<string, dyn>, string) -> bool",
}

_VARIABLE_TYPES = {
    "it": _T.DYN,
    "bindings": _T.Map(_T.STRING, _T.List(_T.DYN)),
    "scope": _T.Map(_T.STRING, _T.List(_T.DYN)),
}
_ROLE_PARAMS = [_T.STRING]
_BOUND_PARAMS = [_T.Map(_T.STRING, _T.DYN), _T.STRING]
_FUNCTION_DECLS = [
    cel.FunctionDecl("role", [cel.Overload("role_string", _T.List(_T.STRING), _ROLE_PARAMS)]),
    cel.FunctionDecl("bound", [cel.Overload("bound_map_string", _T.BOOL, _BOUND_PARAMS)]),
]
_FUNCTION_PARAMS = {"role": _ROLE_PARAMS, "bound": _BOUND_PARAMS}

# Return types that are definitely not boolean. DYN (e.g. a bare ``it.name``) is
# accepted at compile time; a non-bool value then surfaces at evaluation (936).
_NON_BOOL_TYPES = frozenset(
    {
        "STRING",
        "INT",
        "UINT",
        "DOUBLE",
        "BYTES",
        "NULL",
        "LIST",
        "MAP",
        "TIMESTAMP",
        "DURATION",
        "TYPE",
    }
)
_POSITION = re.compile(r"<input>:(\d+):(\d+):")
_MAX_EXPR_LEN = 2000

ErrorKind = Literal["missing_key", "budget_exceeded", "type_error", "other"]


@dataclass(frozen=True)
class CelError:
    """A compile-time problem with an expression."""

    message: str
    line: int | None
    column: int | None
    code: Literal["compile", "not_bool"]


@dataclass(frozen=True)
class CelResult:
    """Outcome of one evaluation. Exactly one of ``value``/``error`` is meaningful."""

    value: Any | None
    error: ErrorKind | None
    message: str | None


class CelEngine(Protocol):
    def compile_check(self, expr: str) -> list[CelError]: ...

    def compile(self, expr: str) -> object: ...

    def evaluate(
        self,
        program: object,
        activation: Mapping[str, Any],
        functions: Mapping[str, Callable[..., Any]],
    ) -> CelResult: ...


def _clean_message(raw: str) -> str:
    # cel-cpp messages look like:
    #   "INVALID_ARGUMENT: ERROR: <input>:1:8: Syntax error: ...\n | src\n | ^ [..]"
    first = raw.splitlines()[0] if raw else raw
    first = re.sub(r"^[A-Z_]+: (ERROR: )?", "", first)
    return _POSITION.sub("", first).strip() or raw.strip()


def _classify(message: str) -> ErrorKind:
    if "NOT_FOUND" in message or "Key not found" in message or "No such key" in message:
        return "missing_key"
    if "Iteration budget exceeded" in message:
        return "budget_exceeded"
    if "No matching overloads" in message or "no matching overload" in message:
        return "type_error"
    return "other"


class GoogleCelEngine:
    """:class:`CelEngine` backed by ``cel-expr-python``."""

    def __init__(self) -> None:
        self._env = cel.NewEnv(variables=_VARIABLE_TYPES, functions=_FUNCTION_DECLS)

    def compile(self, expr: str) -> object:
        """Compile, raising ``ValueError`` on any problem.

        Internal: callers run :meth:`compile_check` first.
        """
        errors = self.compile_check(expr)
        if errors:
            raise ValueError(errors[0].message)
        return self._env.compile(expr)

    def compile_check(self, expr: str) -> list[CelError]:
        if not isinstance(expr, str) or not expr.strip():
            return [CelError("expression is empty", None, None, "compile")]
        if len(expr) > _MAX_EXPR_LEN:
            return [
                CelError(
                    f"expression longer than {_MAX_EXPR_LEN} characters", None, None, "compile"
                )
            ]
        try:
            program = self._env.compile(expr)
        except Exception as exc:  # noqa: BLE001 - cel-cpp raises RuntimeError for all compile issues
            raw = str(exc)
            m = _POSITION.search(raw)
            line, column = (int(m.group(1)), int(m.group(2))) if m else (None, None)
            return [CelError(_clean_message(raw), line, column, "compile")]
        try:
            return_type = program.return_type().name()
        except Exception:  # noqa: BLE001 - defensive: never raise from compile_check
            return []
        if return_type in _NON_BOOL_TYPES:
            return [
                CelError(
                    f"expression must be boolean, but its type is {return_type.lower()}",
                    None,
                    None,
                    "not_bool",
                )
            ]
        return []

    def evaluate(
        self,
        program: object,
        activation: Mapping[str, Any],
        functions: Mapping[str, Callable[..., Any]],
    ) -> CelResult:
        try:
            impls = [
                cel.Function(name, _FUNCTION_PARAMS[name], False, fn)
                for name, fn in functions.items()
                if name in _FUNCTION_PARAMS
            ]
            value = program.eval(data=dict(activation), functions=impls)  # type: ignore[attr-defined]
            if value.type().name() == "ERROR":
                message = str(value.plain_value())
                return CelResult(None, _classify(message), _clean_message(message))
            return CelResult(value.plain_value(), None, None)
        except Exception as exc:  # noqa: BLE001 - map every runtime failure to a result
            message = str(exc)
            return CelResult(None, _classify(message), _clean_message(message))


@lru_cache(maxsize=1)
def default_engine() -> GoogleCelEngine:
    """Process-wide engine (the CEL environment is immutable and safe to share)."""
    return GoogleCelEngine()
