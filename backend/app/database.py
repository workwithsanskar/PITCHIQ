"""Small SQLite boundary used by PITCHIQ v2; v1 remains CSV-backed."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_DB_PATH = ROOT / "data" / "pitchiq_v2.sqlite3"


class DatabaseNotInitialized(RuntimeError):
    pass


class UnsafeDatabaseError(RuntimeError):
    pass


def database_path(path: str | Path | None = None) -> Path:
    configured = path if path is not None else os.getenv("PITCHIQ_DATABASE_PATH")
    candidate = Path(configured).expanduser() if configured else DEFAULT_DB_PATH
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    return candidate


def connect(path: str | Path | None = None, *, create: bool = False) -> sqlite3.Connection:
    db_path = database_path(path)
    if not db_path.exists() and not create:
        raise DatabaseNotInitialized(
            "PITCHIQ v2 database is not initialized. Run the documented database init and CSV import commands."
        )
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise RuntimeError("SQLite foreign key enforcement could not be enabled")
    return connection


def migrate(path: str | Path | None = None) -> int:
    db_path = database_path(path)
    connection = connect(db_path, create=True)
    try:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if existing_tables and "schema_migrations" not in existing_tables:
            raise UnsafeDatabaseError(
                "Database contains tables but no PITCHIQ migration history; refusing to modify it. Choose a new path."
            )

        if "schema_migrations" in existing_tables:
            current = int(connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0])
        else:
            current = 0

        migrations: list[tuple[int, Path]] = []
        for item in MIGRATIONS_DIR.glob("*.sql"):
            match = re.match(r"^(\d+)_.*\.sql$", item.name)
            if match:
                migrations.append((int(match.group(1)), item))
        migrations.sort(key=lambda item: item[0])

        for version, migration_file in migrations:
            if version <= current:
                continue
            script = migration_file.read_text(encoding="utf-8")
            name = migration_file.stem.split("_", 1)[-1]
            statement = (
                "BEGIN IMMEDIATE;\n"
                + script
                + "\nINSERT INTO schema_migrations(version, name) VALUES ("
                + str(version)
                + ", '"
                + name.replace("'", "''")
                + "');\nCOMMIT;"
            )
            try:
                connection.executescript(statement)
            except sqlite3.Error:
                if connection.in_transaction:
                    connection.rollback()
                raise
            current = version
        return current
    finally:
        connection.close()


def assert_initialized(path: str | Path | None = None) -> None:
    connection = connect(path)
    try:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone():
            raise DatabaseNotInitialized("PITCHIQ v2 database migrations have not been applied")
        if not connection.execute("SELECT 1 FROM schema_migrations LIMIT 1").fetchone():
            raise DatabaseNotInitialized("PITCHIQ v2 database has no applied migrations")
    finally:
        connection.close()


def foreign_keys_enabled(connection: sqlite3.Connection) -> bool:
    return bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
