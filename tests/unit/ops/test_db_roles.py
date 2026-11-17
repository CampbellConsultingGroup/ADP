"""The least-privilege database roles script (ADP-blp.7).

No database here: a recording cursor checks which statements are sent. The script is
exercised for real by infra/azure/deploy.sh.
"""

from __future__ import annotations

from typing import Any

from psycopg2 import sql

from adp.ops import db_roles


def _text(statement: Any) -> str:
    """Render a psycopg2 composable without a connection (identifiers double-quoted)."""
    if isinstance(statement, str):
        return " ".join(statement.split())
    if isinstance(statement, sql.Composed):
        return "".join(_text(part) for part in statement.seq)
    if isinstance(statement, sql.Identifier):
        return ".".join(f'"{s}"' for s in statement.strings)
    if isinstance(statement, sql.SQL):
        return statement.string
    raise TypeError(type(statement))


class _Cursor:
    def __init__(self, results: list[Any]) -> None:
        self.sent: list[tuple[str, Any]] = []
        self._results = list(results)
        self._current: Any = None

    def execute(self, statement: Any, params: Any = None) -> None:
        self.sent.append((_text(statement), params))
        if _text(statement).upper().startswith("SELECT"):
            self._current = self._results.pop(0)

    def fetchone(self) -> Any:
        return self._current

    def fetchall(self) -> Any:
        return self._current


def test_app_role_gets_rows_only_and_no_ddl() -> None:
    text = [_text(s) for s in db_roles.app_statements("adp_app", "adp")]

    rows_only = 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "adp_app"'
    assert rows_only in text
    assert 'REVOKE ALL ON DATABASE "adp" FROM PUBLIC' in text
    assert any(s.startswith("ALTER DEFAULT PRIVILEGES") and "ON TABLES" in s for s in text)
    joined = " ".join(text).upper()
    for forbidden in ("CREATE", "TRUNCATE", "REFERENCES", "TRIGGER", "ALL PRIVILEGES", "OWNER"):
        assert forbidden not in joined


def test_app_role_cannot_write_the_migration_bookkeeping() -> None:
    cur = _Cursor(results=[("alembic_version",)])
    db_roles._grant_app(cur, "adp_app", "adp")

    assert cur.sent[-1][0] == 'REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM "adp_app"'


def test_a_new_role_is_created_and_an_existing_one_only_gets_its_password_reset() -> None:
    new = _Cursor(results=[None])
    db_roles._ensure_role(new, "adp_app", "pw-1")
    assert new.sent[-1] == ('CREATE ROLE "adp_app" LOGIN PASSWORD %s', ("pw-1",))

    existing = _Cursor(results=[(1,)])
    db_roles._ensure_role(existing, "adp_keycloak", "pw-2", member=True)
    assert existing.sent[1] == ('ALTER ROLE "adp_keycloak" LOGIN PASSWORD %s', ("pw-2",))
    assert existing.sent[2][0] == 'GRANT "adp_keycloak" TO CURRENT_USER'


def test_keycloak_objects_are_handed_over_tables_before_sequences() -> None:
    cur = _Cursor(results=[[("realm", "r"), ("user_entity", "r"), ("hibernate_seq", "S")]])
    moved = db_roles._grant_keycloak(cur, "adp_keycloak", "keycloak")

    assert moved == 3
    owners = [s for s, _ in cur.sent if "OWNER TO" in s]
    assert owners == [
        'ALTER TABLE public."realm" OWNER TO "adp_keycloak"',
        'ALTER TABLE public."user_entity" OWNER TO "adp_keycloak"',
        'ALTER SEQUENCE public."hibernate_seq" OWNER TO "adp_keycloak"',
    ]
    assert ('REVOKE ALL ON DATABASE "keycloak" FROM PUBLIC', None) in cur.sent
