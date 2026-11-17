"""Create/refresh the least-privilege Postgres roles (ADP-blp.7).

The API and Keycloak used to connect as the server administrator, so a SQL
injection or code execution in either gave administrator rights on every
database. This script, run with the administrator login from the
``adp-migrate`` job (overriding its command), gives each its own role:

* the **app role** may read and write rows in the application database and
  nothing else -- no DDL, no other database. Tables created later by a
  migration are covered by default privileges, so this does not need to be
  re-run after every migration;
* the **Keycloak role** owns the objects in the Keycloak database (Keycloak
  runs its own schema upgrades) and cannot connect to the application database.

The administrator login is kept for the migration job only.

Idempotent: re-running resets both passwords and re-asserts the grants.

Required env vars:
  ADP_DATABASE_URL           Administrator connection to the application database
                             (postgresql+asyncpg://... is accepted)
  ADP_DB_APP_PASSWORD        Password to set on the app role
  ADP_DB_KEYCLOAK_PASSWORD   Password to set on the Keycloak role
Optional:
  ADP_DB_APP_ROLE            default "adp_app"
  ADP_DB_KEYCLOAK_ROLE       default "adp_keycloak"
  ADP_DB_KEYCLOAK_DATABASE   default "keycloak"; empty = skip the Keycloak part
"""

from __future__ import annotations

import os
import sys
from typing import Any

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required env var {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def _connect(database: str | None = None) -> Any:
    url = make_url(_env("ADP_DATABASE_URL"))
    conn = psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=database or url.database,
        sslmode=os.environ.get("PGSSLMODE", "prefer"),
    )
    conn.autocommit = True
    return conn


def _ensure_role(cur: Any, role: str, password: str, *, member: bool = False) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(
        sql.SQL("{} ROLE {} LOGIN PASSWORD %s").format(sql.SQL(verb), sql.Identifier(role)),
        (password,),
    )
    if member:
        # The administrator is not a superuser on a managed server: to hand objects to a
        # role (ALTER ... OWNER TO) it must be a member of that role.
        cur.execute(sql.SQL("GRANT {} TO CURRENT_USER").format(sql.Identifier(role)))


def app_statements(app_role: str, database: str) -> list[sql.Composed]:
    """Grants for the app role, run while connected to the application database."""
    role = sql.Identifier(app_role)
    db = sql.Identifier(database)
    return [
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, role),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role),
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
        ).format(role),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role),
        # Tables and sequences a later migration creates (as the current, administrator role).
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(role),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(role),
    ]


def _grant_app(cur: Any, app_role: str, database: str) -> None:
    for statement in app_statements(app_role, database):
        cur.execute(statement)
    # The migration bookkeeping is the migration job's alone.
    cur.execute("SELECT to_regclass('public.alembic_version')")
    if cur.fetchone()[0]:
        cur.execute(
            sql.SQL("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {}").format(
                sql.Identifier(app_role)
            )
        )


def _grant_keycloak(cur: Any, keycloak_role: str, database: str) -> int:
    """Hand the Keycloak database's objects to the Keycloak role. Returns how many moved."""
    role = sql.Identifier(keycloak_role)
    db = sql.Identifier(database)
    cur.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db))
    cur.execute(sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(db, role))
    cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(role))
    # Tables first: a sequence owned by a table column follows its table. 'r' table,
    # 'p' partitioned table, 'v' view, 'm' materialised view, then 'S' free sequences.
    cur.execute(
        """
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
          AND pg_get_userbyid(c.relowner) <> %s
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.objid = c.oid AND d.deptype IN ('a', 'i') AND c.relkind = 'S'
          )
        ORDER BY (c.relkind = 'S'), c.relname
        """,
        (keycloak_role,),
    )
    moved = 0
    for name, kind in cur.fetchall():
        keyword = {"S": "SEQUENCE", "v": "VIEW", "m": "MATERIALIZED VIEW"}.get(kind, "TABLE")
        cur.execute(
            sql.SQL("ALTER {} public.{} OWNER TO {}").format(
                sql.SQL(keyword), sql.Identifier(name), role
            )
        )
        moved += 1
    return moved


def main() -> None:
    app_role = os.environ.get("ADP_DB_APP_ROLE", "adp_app")
    keycloak_role = os.environ.get("ADP_DB_KEYCLOAK_ROLE", "adp_keycloak")
    keycloak_db = os.environ.get("ADP_DB_KEYCLOAK_DATABASE", "keycloak")
    app_password = _env("ADP_DB_APP_PASSWORD")
    keycloak_password = _env("ADP_DB_KEYCLOAK_PASSWORD") if keycloak_db else ""

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            app_db = cur.fetchone()[0]
            _ensure_role(cur, app_role, app_password)
            _grant_app(cur, app_role, app_db)
            print(f"OK: role '{app_role}' may read and write rows in database '{app_db}'")
            if keycloak_db:
                _ensure_role(cur, keycloak_role, keycloak_password, member=True)
    finally:
        conn.close()

    if keycloak_db:
        conn = _connect(keycloak_db)
        try:
            with conn.cursor() as cur:
                moved = _grant_keycloak(cur, keycloak_role, keycloak_db)
            print(
                f"OK: role '{keycloak_role}' owns database '{keycloak_db}' objects "
                f"({moved} handed over this run)"
            )
        finally:
            conn.close()


if __name__ == "__main__":
    main()
