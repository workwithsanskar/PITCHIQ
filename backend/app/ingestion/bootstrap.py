"""Prepare the configured SQLite database before starting the API server."""
from __future__ import annotations

from pathlib import Path

from ..database import connect, database_path, migrate
from .legacy_csv import import_csv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CSV = BACKEND_ROOT / "data" / "source_data_with_derived_metrics.csv"
PLAYER_MASTER = BACKEND_ROOT / "data" / "player_master.csv"


def ensure_database() -> None:
    path = database_path()
    schema_version = migrate(path)

    connection = connect(path)
    try:
        record_count = int(connection.execute("SELECT COUNT(*) FROM player_stat_records").fetchone()[0])
    finally:
        connection.close()

    if record_count:
        print(f"PITCHIQ SQLite ready: schema {schema_version}, {record_count} player records.")
        return

    result = import_csv(SOURCE_CSV, PLAYER_MASTER, path)
    if result["rows_inserted"] < 1:
        raise RuntimeError("PITCHIQ SQLite import did not seed any player records")
    print(f"PITCHIQ SQLite initialized from the bundled dataset: {result['rows_inserted']} player records.")


if __name__ == "__main__":
    ensure_database()
