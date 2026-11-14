"""CelEngine adapter contract (934 contracts/python-api.md, research D1)."""

from __future__ import annotations

import pytest

from adp.patterns.cel import CelError, CelResult, default_engine


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    return default_engine()


@pytest.mark.parametrize(
    "expr",
    [
        "it.application_type in ['custom', 'saas', 'cots']",
        "it.time_classification in ['Invest', 'Tolerate']",
        "it.source.domain_ids.all(d, !(d in it.target.domain_ids))",
        "it.target.id in role('backbone') || it.source.id in role('backbone')",
        "bound(it, 'backbone')",
        "size(bindings['backbone']) == 1",
        "scope['integrations'].exists(i, i.source.id == it.id)",
        "it.name",  # DYN result: accepted at compile time (research D1 follow-up)
    ],
)
def test_compile_check_accepts(engine, expr: str) -> None:  # type: ignore[no-untyped-def]
    assert engine.compile_check(expr) == []


def test_syntax_error_has_position(engine) -> None:  # type: ignore[no-untyped-def]
    errs = engine.compile_check("it.x ==")
    assert len(errs) == 1
    assert isinstance(errs[0], CelError)
    assert errs[0].code == "compile"
    assert errs[0].line == 1
    assert errs[0].column == 8


def test_undeclared_variable_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    errs = engine.compile_check("undeclared_var == 1")
    assert [e.code for e in errs] == ["compile"]
    assert "undeclared" in errs[0].message


def test_overload_mismatch_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    assert [e.code for e in engine.compile_check("role(1) == []")] == ["compile"]


def test_definite_non_bool_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    errs = engine.compile_check("'abc'")
    assert [e.code for e in errs] == ["not_bool"]


def test_evaluate_with_role_and_bound(engine) -> None:  # type: ignore[no-untyped-def]
    bindings = {"backbone": ["bb"]}
    fns = {
        "role": lambda k: bindings.get(k, []),
        "bound": lambda e, k: e["id"] in bindings.get(k, []),
    }
    prog = engine.compile("it.target.id in role('backbone')")
    it = {"id": "i1", "source": {"id": "a"}, "target": {"id": "bb"}}
    assert engine.evaluate(prog, {"it": it}, fns) == CelResult(value=True, error=None, message=None)
    prog2 = engine.compile("bound(it, 'backbone')")
    assert engine.evaluate(prog2, {"it": {"id": "bb"}}, fns).value is True
    assert engine.evaluate(prog2, {"it": {"id": "zz"}}, fns).value is False


def test_missing_key_is_reported(engine) -> None:  # type: ignore[no-untyped-def]
    prog = engine.compile("it.missing == 1")
    res = engine.evaluate(prog, {"it": {"id": "a"}}, {})
    assert res.error == "missing_key"
    assert res.value is None


def test_budget_exceeded_is_reported(engine) -> None:  # type: ignore[no-untyped-def]
    big = "[" + ",".join(str(i) for i in range(200)) + "]"
    prog = engine.compile(f"{big}.all(x, {big}.all(y, x + y >= 0))")
    assert engine.evaluate(prog, {}, {}).error == "budget_exceeded"


def test_compile_raises_nothing_on_garbage(engine) -> None:  # type: ignore[no-untyped-def]
    for expr in ["", ")))", "\x00", "a" * 5000, "'unterminated"]:
        errs = engine.compile_check(expr)
        assert errs and all(e.code == "compile" for e in errs)


def test_default_engine_is_cached() -> None:
    assert default_engine() is default_engine()
