"""Table declarations across the stores, for tests (ADP-blp.26).

Each store module declares the tables it owns and, for tables owned elsewhere, a narrow copy
("mirror") with only the columns it reads. 27 tables are declared in more than one store. That
keeps the domain packages from importing each other, but it has two costs:

* A mirror can drift from the owner's declaration. ``find_drift`` reports that; a unit test fails
  on it.
* A test that needs several stores has to create their tables in the right order, excluding
  mirrors by hand (see the fixture rules in CLAUDE.md). ``create_schema`` does that correctly for
  any set of stores: it creates each table once, from its widest declaration.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Every module that declares tables on a store metadata. Importing a store's sibling modules
# matters: some tables (initiative links, org mappings, adoptions) are declared outside
# ``store.py`` but on its metadata, and only exist once that module is imported.
STORE_MODULES: tuple[str, ...] = (
    "adp.business.store",
    "adp.business.value_chains",
    "adp.application.store",
    "adp.application.app_capabilities",
    "adp.strategy.store",
    "adp.strategy.initiatives",
    "adp.compliance.store",
    "adp.organization.store",
    "adp.organization.cap_mappings",
    "adp.organization.regional",
    "adp.agentic.store",
    "adp.patterns.store",
    "adp.patterns.adoptions",
    "adp.patterns.snapshot_store",
    "adp.chat.store",
    "adp.diagrams.store",
    "adp.admin.service",
    "adp.admin.rubric_service",
)


def store_metadatas(modules: Iterable[str] = STORE_MODULES) -> dict[str, sa.MetaData]:
    """{first module that exposes it: metadata}, one entry per distinct MetaData object."""
    found: dict[int, tuple[str, sa.MetaData]] = {}
    for name in modules:
        metadata = getattr(importlib.import_module(name), "_metadata", None)
        if isinstance(metadata, sa.MetaData):
            found.setdefault(id(metadata), (name, metadata))
    return dict(found.values())


def declarations(
    modules: Iterable[str] = STORE_MODULES,
) -> dict[str, list[tuple[str, sa.Table]]]:
    """{table name: [(declaring module, Table), ...]} with the widest declaration first."""
    by_name: dict[str, list[tuple[str, sa.Table]]] = {}
    for module, metadata in store_metadatas(modules).items():
        for table in metadata.tables.values():
            by_name.setdefault(table.name, []).append((module, table))
    for tables in by_name.values():
        tables.sort(key=lambda item: -len(item[1].columns))
    return by_name


_POSTGRES = postgresql.dialect()


def _type_family(column: sa.Column[Any]) -> str:
    """What the column holds on PostgreSQL, coarsely: 'str', 'int', 'list', 'dict', 'datetime'.

    Compared on the production dialect because stores write the same column in different ways
    (``ARRAY(Text)`` with a JSON variant for SQLite, or JSON with an ARRAY variant for
    PostgreSQL). String(36) and Text both count as 'str'.
    """
    impl = column.type.dialect_impl(_POSTGRES)
    try:
        python_type: Any = impl.python_type
    except NotImplementedError:
        return type(impl).__name__.lower()
    return getattr(python_type, "__name__", str(python_type))


def find_drift(modules: Iterable[str] = STORE_MODULES) -> list[str]:
    """Every way a narrower declaration disagrees with the widest one for the same table."""
    problems: list[str] = []
    for name, tables in declarations(modules).items():
        owner_module, owner = tables[0]
        for module, mirror in tables[1:]:
            for column in mirror.columns:
                if column.name not in owner.columns:
                    problems.append(
                        f"{name}.{column.name}: declared in {module} but not in {owner_module}"
                    )
                    continue
                expected = _type_family(owner.columns[column.name])
                actual = _type_family(column)
                if actual != expected:
                    problems.append(
                        f"{name}.{column.name}: {module} says {actual}, "
                        f"{owner_module} says {expected}"
                    )
    return problems


def create_schema(sync_conn: sa.Connection, modules: Iterable[str] = STORE_MODULES) -> None:
    """Create every table the given store modules declare, once each, from its widest
    declaration. Use inside ``await conn.run_sync(create_schema)`` (or with a lambda to pass a
    subset of modules). Replaces hand-ordered ``_metadata.create_all`` calls with exclusions."""
    for tables in declarations(modules).values():
        _module, table = tables[0]
        table.create(sync_conn, checkfirst=True)
