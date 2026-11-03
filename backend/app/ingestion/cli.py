"""Command-line inspection, validation and import for the local supplied CSV."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from ..database import DEFAULT_DB_PATH, ROOT, UnsafeDatabaseError, database_path, migrate
from .legacy_csv import ImportValidationError, import_csv, import_report, inspect_csv, preview_csv, validate_csv

DEFAULT_CSV = ROOT / "data" / "source_data_with_derived_metrics.csv"
DEFAULT_MASTER = ROOT / "data" / "player_master.csv"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pitchiq-ingest", description="Inspect and import supplied PITCHIQ football CSV data.")
    parser.add_argument("--database", default=str(DEFAULT_DB_PATH), help="v2 SQLite path; the starter database is never overwritten")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="apply versioned migrations to a new v2 database")
    backup = sub.add_parser("backup", help="create a consistent SQLite backup")
    backup.add_argument("--output", required=True, help="destination SQLite backup path")
    for command in ("inspect", "validate", "preview", "import"):
        child = sub.add_parser(command, help=f"{command.title()} the supplied CSV")
        child.add_argument("--file", default=str(DEFAULT_CSV), help="CSV file to inspect")
        child.add_argument("--master", default=str(DEFAULT_MASTER), help="player_master.csv used for source IDs and context")
        child.add_argument("--json", action="store_true", help="emit JSON")
    report = sub.add_parser("report", help="show a completed import report")
    report.add_argument("--job-id", required=True)
    report.add_argument("--json", action="store_true")
    return parser


def _emit(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    else:
        if isinstance(value, dict) and "errors" in value:
            for key, item in value.items():
                if key == "errors":
                    print(f"{key}: {len(item)}")
                    for row in item[:20]:
                        print(f"  row {row.get('row')}: {'; '.join(row.get('errors', []))}")
                elif key == "warnings":
                    print(f"{key}: {len(item)}")
                else:
                    print(f"{key}: {item}")
            return
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = database_path(args.database)
        if args.command == "init":
            version = migrate(path)
            _emit({"status": "initialized", "database": str(path), "schema_version": version}, True)
            return 0
        if args.command == "backup":
            if not path.exists():
                raise FileNotFoundError(f"database does not exist: {path}")
            target = Path(args.output).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            source_connection = sqlite3.connect(path)
            backup_connection = sqlite3.connect(target)
            try:
                source_connection.backup(backup_connection)
            finally:
                backup_connection.close()
                source_connection.close()
            _emit({"status": "backed_up", "database": str(path), "backup": str(target)}, True)
            return 0
        if args.command == "report":
            result = import_report(args.job_id, path)
            _emit(result, args.json)
            return 0
        if args.command == "inspect":
            result = inspect_csv(args.file, args.master)
        elif args.command == "validate":
            result = validate_csv(args.file, args.master)
        elif args.command == "preview":
            result = preview_csv(args.file, args.master, path)
        elif args.command == "import":
            result = import_csv(args.file, args.master, path)
            report = import_report(result["job_id"], path)
            report_dir = ROOT / "data" / "import-reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"{result['job_id']}.json"
            report_path.write_text(json.dumps({**result, **report}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            result["report_file"] = str(report_path)
        else:
            raise AssertionError(f"unhandled command: {args.command}")
        _emit(result, getattr(args, "json", False))
        if args.command in {"validate", "preview"} and result.get("rejected_rows", 0):
            return 2
        return 0
    except (ImportValidationError, UnsafeDatabaseError, FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, ImportValidationError) and exc.errors:
            _emit({"errors": exc.errors}, getattr(args, "json", False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

