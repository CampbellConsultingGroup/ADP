"""Download a plain-SQL dump (INSERT-statement format, not COPY) from a URL
and execute it against ADP_DATABASE_URL via a synchronous psycopg2 connection.

Built for migrating data between environments (e.g. local dev -> Azure)
where the target Postgres has no public network access -- this runs from a
Container Apps Job already inside the VNet (same `adp-keycloak-admin` job
infrastructure, overriding --command), fetching the dump from a
time-limited SAS URL rather than requiring a direct network path from the
source environment.

Deliberately requires INSERT-format dumps (`pg_dump --inserts`), not the
default COPY-block format -- psycopg2 has no built-in COPY FROM STDIN
parser for arbitrary embedded SQL text, and the `psql` client binary isn't
installed in this project's container images (only libpq-dev, for asyncpg's
build). A COPY-format dump would silently fail partway through.

Required env vars:
  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
                     Standard libpq connection env vars -- deliberately NOT
                     a single DSN URL. Auto-generated passwords here can
                     contain URL-reserved characters (e.g. `/`) that break
                     naive DSN construction if not percent-encoded; discrete
                     env vars sidestep that entirely (psycopg2.connect()
                     reads them natively with no parsing on our part).
  DUMP_URL           HTTPS URL to fetch the .sql file from (e.g. a
                     time-limited Azure Blob SAS URL).
"""

from __future__ import annotations

import os
import sys

import httpx
import psycopg2


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required env var {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    for name in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        _env(name)  # validate presence; psycopg2.connect() reads them itself
    dump_url = _env("DUMP_URL")

    print(f"Fetching dump from {dump_url.split('?')[0]} ...")
    resp = httpx.get(dump_url, timeout=60.0)
    resp.raise_for_status()
    sql_text = resp.text
    print(f"Fetched {len(sql_text)} bytes.")

    # Strip psql-only meta-commands (e.g. `\restrict`/`\unrestrict`, a newer
    # pg_dump security marker) -- these aren't valid SQL and psycopg2 has no
    # psql-style command interpreter, unlike the psql client itself.
    sql_text = "\n".join(
        line for line in sql_text.splitlines() if not line.startswith("\\")
    )

    conn = psycopg2.connect()  # reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD
    try:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        print("OK: dump executed and committed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
