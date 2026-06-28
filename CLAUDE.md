# ADP Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-06-27

## Active Technologies
- Python 3.11+ + SQLAlchemy 2.x (async ORM), asyncpg (PostgreSQL async driver), Alembic (migrations), testcontainers-python (PostgreSQL container for integration tests), pydantic-settings (database URL config) (002-design-store)
- PostgreSQL 15+ — primary persistence; JSONB for `ArchitectureDescription` content with indexed paths for traceability queries (002-design-store)

- Python 3.11+ + Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests) (001-canonical-data-model)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 002-design-store: Added Python 3.11+ + SQLAlchemy 2.x (async ORM), asyncpg (PostgreSQL async driver), Alembic (migrations), testcontainers-python (PostgreSQL container for integration tests), pydantic-settings (database URL config)

- 001-canonical-data-model: Added Python 3.11+ + Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
