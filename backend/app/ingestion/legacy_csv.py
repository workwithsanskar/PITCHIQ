"""Importer for the supplied PITCHIQ player-season CSV snapshot."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..database import connect, database_path

SOURCE_ID = "pitchiq-supplied-2025-26"
SOURCE_NAME = "PITCHIQ supplied 2025–26 player dataset"
SOURCE_VERSION = "legacy-csv-v1"
MAX_IMPORT_BYTES = 100 * 1024 * 1024
MAX_IMPORT_ROWS = 250_000
NAMESPACE = uuid.UUID("ea70ed29-05b4-48ef-bc1e-3dc5e5db8a85")

REQUIRED_ROW_FIELDS = {"Player", "Squad", "Comp", "season"}
NUMERIC_FIELDS = {
    "Age": "age",
    "MP": "appearances",
    "Starts": "starts",
    "Min": "minutes",
    "Gls": "goals",
    "Ast": "assists",
    "G+A": "goal_contributions",
    "G-PK": "non_penalty_goals",
    "PK": "penalties_scored",
    "PKatt": "penalties_attempted",
    "CrdY": "yellow_cards",
    "CrdR": "red_cards",
    "2CrdY": "second_yellow_cards",
    "Fls": "fouls_committed",
    "Fld": "fouls_drawn",
    "OG": "own_goals",
    "Sh": "shots",
    "SoT": "shots_on_target",
    "SoT%": "source_sot_percent",
    "Crs": "crosses",
    "TklW": "tackles_won",
    "Int": "interceptions",
    "GA": "goals_against",
    "GA90": "goals_against_per90",
    "SoTA": "shots_on_target_against",
    "Saves": "saves",
    "Save%": "save_percent",
    "W": "wins",
    "D": "draws",
    "L": "losses",
    "CS": "clean_sheets",
    "CS%": "clean_sheet_percent",
    "PKatt_stats_keeper": "penalties_faced",
    "PKA": "penalties_against",
    "PKsv": "penalties_saved",
    "PKm": "penalties_missed",
}
# The source's G+A-PK column is numeric but its units are per 90, so validate it
# without mapping the source value into the raw-count contribution column.
SOURCE_RATE_FIELDS = {"G+A-PK": "source_non_penalty_contributions_per90"}
COUNT_FIELDS = {
    "appearances", "starts", "minutes", "goals", "assists", "goal_contributions",
    "non_penalty_goals", "penalties_scored", "penalties_attempted", "shots",
    "non_penalty_goal_contributions", "yellow_cards", "red_cards", "second_yellow_cards",
    "fouls_committed", "fouls_drawn", "own_goals", "shots_on_target", "crosses", "tackles_won", "interceptions", "goals_against",
    "goals_against_per90", "shots_on_target_against", "saves", "wins", "draws",
    "losses", "clean_sheets",
    "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed",
}
STAT_COLUMNS = tuple(NUMERIC_FIELDS.values()) + (
    "non_penalty_goal_contributions", "position_raw", "raw_metrics_json"
)

METRICS = [
    ("goals", "Goals", "Observed player goals total.", "count", "goals", None, '["goals"]', "available", "1"),
    ("assists", "Assists", "Observed player assists total.", "count", "assists", None, '["assists"]', "available", "1"),
    ("non_penalty_goals", "Non-penalty goals", "Goals excluding penalties as supplied by the source.", "count", "goals", None, '["G-PK"]', "partial", "1"),
    ("non_penalty_goal_contributions", "Non-penalty goal contributions", "Non-penalty goals plus assists; derived from the source counts.", "count", "contributions", "non_penalty_goals + assists", '["G-PK", "Ast"]', "available", "1"),
    ("penalties_scored", "Penalties scored", "Penalty goals as supplied by the source.", "count", "goals", None, '["PK"]', "partial", "1"),
    ("penalties_attempted", "Penalties attempted", "Penalty attempts as supplied by the source.", "count", "attempts", None, '["PKatt"]', "partial", "1"),
    ("yellow_cards", "Yellow cards", "Source player-record yellow cards.", "count", "cards", None, '["CrdY"]', "available", "1"),
    ("red_cards", "Red cards", "Source player-record red cards.", "count", "cards", None, '["CrdR"]', "available", "1"),
    ("second_yellow_cards", "Second-yellow dismissals", "Source player-record second-yellow count.", "count", "cards", None, '["2CrdY"]', "partial", "1"),
    ("fouls_committed", "Fouls committed", "Source player-record fouls committed.", "count", "fouls", None, '["Fls"]', "partial", "1"),
    ("fouls_drawn", "Fouls drawn", "Source player-record fouls drawn.", "count", "fouls", None, '["Fld"]', "partial", "1"),
    ("own_goals", "Own goals", "Source player-record own goals.", "count", "goals", None, '["OG"]', "partial", "1"),
    ("appearances", "Appearances", "Source appearance count.", "count", "matches", None, '["appearances"]', "available", "1"),
    ("starts", "Starts", "Source starts count.", "count", "matches", None, '["starts"]', "available", "1"),
    ("minutes", "Minutes", "Observed minutes played.", "count", "minutes", None, '["minutes"]', "available", "1"),
    ("shots", "Shots", "Observed total shots.", "count", "shots", None, '["shots"]', "available", "1"),
    ("shots_on_target", "Shots on target", "Observed shots on target.", "count", "shots", None, '["shots_on_target"]', "available", "1"),
    ("shot_accuracy", "Shooting accuracy", "Shots on target divided by total shots, or source SoT% when present.", "percent", "%", "shots_on_target / shots * 100", '["shots_on_target", "shots"]', "partial", "1"),
    ("goals_per90", "Goals per 90", "Goals per 90 minutes.", "rate", "goals/90", "goals * 90 / minutes", '["goals", "minutes"]', "available", "1"),
    ("assists_per90", "Assists per 90", "Assists per 90 minutes.", "rate", "assists/90", "assists * 90 / minutes", '["assists", "minutes"]', "available", "1"),
    ("contributions_per90", "Goal contributions per 90", "Goals plus assists per 90 minutes.", "rate", "contributions/90", "(goals + assists) * 90 / minutes", '["goals", "assists", "minutes"]', "available", "1"),
    ("non_penalty_contributions_per90", "Non-penalty goal contributions per 90", "Non-penalty goals plus assists per 90 minutes.", "rate", "contributions/90", "(non_penalty_goals + assists) * 90 / minutes", '["G-PK", "Ast", "Min"]', "available", "1"),
    ("goals_per_appearance", "Goals per appearance", "Goals divided by appearances when both are observed and appearances are greater than zero.", "rate", "goals/appearance", "goals / appearances", '["goals", "appearances"]', "available", "1"),
    ("assists_per_appearance", "Assists per appearance", "Assists divided by appearances when both are observed and appearances are greater than zero.", "rate", "assists/appearance", "assists / appearances", '["assists", "appearances"]', "available", "1"),
    ("goals_per_shot", "Goal conversion", "Goals divided by shots as a percentage; this is distinct from shooting accuracy.", "percent", "%", "goals / shots * 100", '["goals", "shots"]', "partial", "1"),
    ("shots_per_goal", "Shots per goal", "Shots divided by goals when goals are greater than zero.", "rate", "shots/goal", "shots / goals", '["shots", "goals"]', "partial", "1"),
    ("shots_per90", "Shots per 90", "Shots per 90 minutes.", "rate", "shots/90", "shots * 90 / minutes", '["shots", "minutes"]', "available", "1"),
    ("shots_on_target_per90", "Shots on target per 90", "Shots on target per 90 minutes.", "rate", "shots/90", "shots_on_target * 90 / minutes", '["shots_on_target", "minutes"]', "available", "1"),
    ("non_penalty_goals_per90", "Non-penalty goals per 90", "Non-penalty goals per 90 minutes.", "rate", "goals/90", "non_penalty_goals * 90 / minutes", '["non_penalty_goals", "minutes"]', "partial", "1"),
    ("crosses_per90", "Crosses per 90", "Crosses per 90 minutes.", "rate", "crosses/90", "crosses * 90 / minutes", '["crosses", "minutes"]', "partial", "1"),
    ("tackles_won_per90", "Tackles won per 90", "Tackles won per 90 minutes; attempt count and success percentage are unavailable.", "rate", "tackles/90", "tackles_won * 90 / minutes", '["tackles_won", "minutes"]', "partial", "1"),
    ("interceptions_per90", "Interceptions per 90", "Interceptions per 90 minutes.", "rate", "interceptions/90", "interceptions * 90 / minutes", '["interceptions", "minutes"]', "partial", "1"),
    ("crosses", "Crosses", "Source crosses count; not a complete passing total.", "count", "crosses", None, '["Crs"]', "partial", "1"),
    ("tackles_won", "Tackles won", "Source tackles-won count; attempts/success rate unavailable.", "count", "tackles", None, '["TklW"]', "partial", "1"),
    ("interceptions", "Interceptions", "Source interceptions count.", "count", "interceptions", None, '["Int"]', "partial", "1"),
    ("goals_against", "Goals against", "Source goalkeeper player-record goals conceded; not a club total.", "count", "goals", None, '["GA"]', "partial", "1"),
    ("goals_against_per90", "Goals against per 90", "Source goalkeeper player-record goals against per 90 minutes.", "rate", "goals/90", "source GA90", '["GA90"]', "partial", "1"),
    ("shots_on_target_against", "Shots on target faced", "Source goalkeeper player-record shots on target faced.", "count", "shots", None, '["SoTA"]', "partial", "1"),
    ("saves", "Saves", "Source goalkeeper player-record saves; not a club total.", "count", "saves", None, '["Saves"]', "partial", "1"),
    ("save_percent", "Save percentage", "Source goalkeeper save percentage; not a team defensive rate.", "percent", "%", "source Save%", '["Save%"]', "partial", "1"),
    ("wins", "Goalkeeper wins", "Source goalkeeper player-record wins.", "count", "matches", None, '["W"]', "partial", "1"),
    ("draws", "Goalkeeper draws", "Source goalkeeper player-record draws.", "count", "matches", None, '["D"]', "partial", "1"),
    ("losses", "Goalkeeper losses", "Source goalkeeper player-record losses.", "count", "matches", None, '["L"]', "partial", "1"),
    ("clean_sheets", "Clean sheets", "Source goalkeeper player-record clean sheets.", "count", "matches", None, '["CS"]', "partial", "1"),
    ("clean_sheet_percent", "Clean-sheet percentage", "Source goalkeeper player-record clean-sheet percentage.", "percent", "%", "source CS%", '["CS%"]', "partial", "1"),
    ("penalties_faced", "Penalties faced", "Source goalkeeper player-record penalties faced.", "count", "attempts", None, '["PKatt_stats_keeper"]', "partial", "1"),
    ("penalties_against", "Penalty goals against", "Source goalkeeper player-record penalty goals conceded.", "count", "goals", None, '["PKA"]', "partial", "1"),
    ("penalties_saved", "Penalties saved", "Source goalkeeper player-record penalty saves.", "count", "saves", None, '["PKsv"]', "partial", "1"),
    ("penalties_missed", "Penalties missed", "Source goalkeeper player-record opponent penalty misses.", "count", "attempts", None, '["PKm"]', "partial", "1"),
    ("xg", "Expected goals", "Not present in the supplied dataset.", "rate", "goals", None, '["xG"]', "unavailable", "1"),
    ("xa", "Expected assists", "Not present in the supplied dataset.", "rate", "assists", None, '["xA"]', "unavailable", "1"),
    ("passes_completed", "Passes completed", "Not present in the supplied dataset.", "count", "passes", None, '["completed passes"]', "unavailable", "1"),
    ("passes_attempted", "Passes attempted", "Not present in the supplied dataset.", "count", "passes", None, '["attempted passes"]', "unavailable", "1"),
    ("blocks", "Blocks", "Not present in the supplied dataset.", "count", "actions", None, '["blocks"]', "unavailable", "1"),
    ("clearances", "Clearances", "Not present in the supplied dataset.", "count", "actions", None, '["clearances"]', "unavailable", "1"),
    ("aerial_duels", "Aerial duels", "Not present in the supplied dataset.", "count", "duels", None, '["aerial duels"]', "unavailable", "1"),
]


class ImportValidationError(ValueError):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


class NormalizedLegacyRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    source_player_key: str = Field(min_length=1, max_length=120)
    player_name: str = Field(min_length=1, max_length=200)
    club: str = Field(min_length=1, max_length=160)
    competition: str = Field(min_length=1, max_length=160)
    season_id: str = Field(pattern=r"^\d{4}-\d{4}$", max_length=9)
    source_record_key: str = Field(min_length=1, max_length=120)


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).split())


def stable_id(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


def file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cell(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, float) and value.is_integer():
            return int(value)
    return str(value).strip()


def _float(value: Any, field: str, errors: list[str]) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field} is not numeric")
        return None
    if not math.isfinite(parsed):
        errors.append(f"{field} is not finite")
        return None
    if field in COUNT_FIELDS and parsed < 0:
        errors.append(f"{field} cannot be negative")
        return None
    if field in {"source_sot_percent", "save_percent", "clean_sheet_percent"} and not 0 <= parsed <= 100:
        return None
    return parsed


def _season(label: Any) -> tuple[str | None, str | None]:
    if label is None or pd.isna(label):
        return None, None
    raw = str(label).strip().replace("/", "-").replace("–", "-").replace("—", "-")
    match = re.fullmatch(r"(\d{4})-(\d{2}|\d{4})", raw)
    if not match:
        return None, None
    start = int(match.group(1))
    end_token = match.group(2)
    end = int(end_token) if len(end_token) == 4 else (start // 100) * 100 + int(end_token)
    if end < start or end > start + 2:
        return None, None
    season_id = f"{start}-{end}"
    return season_id, f"{start}–{str(end)[-2:]}"


def _load_master(path: str | Path | None) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], list[str]]]:
    if not path:
        return {}, {}
    master = pd.read_csv(path, dtype="string")
    required = {"player_id", "player_name"}
    if not required.issubset(master.columns):
        raise ImportValidationError(f"Master file is missing required columns: {sorted(required - set(master.columns))}")
    by_id: dict[str, dict[str, Any]] = {}
    by_fingerprint: dict[tuple[str, str, str], list[str]] = {}
    for row in master.to_dict(orient="records"):
        key = _cell(row.get("player_id"))
        name = _cell(row.get("player_name"))
        if not key or not name:
            continue
        record = {column: _cell(value) for column, value in row.items()}
        by_id[str(key)] = record
        nation = normalize_name(str(record.get("nation_raw") or ""))
        birth = str(record.get("birth_year") or "")
        fingerprint = (normalize_name(str(name)), nation, birth)
        by_fingerprint.setdefault(fingerprint, []).append(str(key))
    return by_id, by_fingerprint


def inspect_csv(path: str | Path, master_path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path)
    if source.suffix.lower() != ".csv":
        raise ImportValidationError("Only CSV input is supported by the supplied legacy adapter")
    if source.stat().st_size > MAX_IMPORT_BYTES:
        raise ImportValidationError(f"CSV exceeds the configured {MAX_IMPORT_BYTES // (1024 * 1024)} MB import limit")
    try:
        frame = pd.read_csv(source, dtype="string", keep_default_na=True)
    except Exception as exc:
        raise ImportValidationError(f"Could not parse CSV: {exc}") from exc
    missing = sorted(REQUIRED_ROW_FIELDS - set(frame.columns))
    if len(frame) > MAX_IMPORT_ROWS:
        raise ImportValidationError(f"CSV exceeds the configured {MAX_IMPORT_ROWS} row import limit")
    if "player_id" not in frame.columns and "Rk" not in frame.columns and not master_path:
        missing.append("player_id or Rk/master identity mapping")
    return {
        "file_name": source.name,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "headers": list(frame.columns),
        "missing_required_columns": missing,
        "sha256": file_checksum(source),
        "master_file": Path(master_path).name if master_path else None,
    }


def validate_csv(path: str | Path, master_path: str | Path | None = None) -> dict[str, Any]:
    inspection = inspect_csv(path, master_path)
    if inspection["missing_required_columns"]:
        raise ImportValidationError(
            "CSV is missing required identity/context fields",
            [{"error": "missing columns", "columns": inspection["missing_required_columns"]}],
        )
    frame = pd.read_csv(path, dtype="string", keep_default_na=True)
    master, fingerprint_keys = _load_master(master_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    valid = 0
    identities: set[str] = set()
    duplicate_source_keys = 0
    seen_keys: set[str] = set()
    for index, row in enumerate(frame.to_dict(orient="records"), start=2):
        row_errors: list[str] = []
        name = _cell(row.get("Player"))
        club = _cell(row.get("Squad"))
        competition = _cell(row.get("Comp"))
        season_id, _ = _season(row.get("season"))
        record_key = str(_cell(row.get("Rk")) or f"row-{index}")
        source_key = _cell(row.get("player_id"))
        if not source_key and master_path:
            nation = normalize_name(str(_cell(row.get("Nation")) or ""))
            birth = str(_cell(row.get("Born")) or "")
            candidates = fingerprint_keys.get((normalize_name(str(name or "")), nation, birth), [])
            if len(candidates) == 1:
                source_key = candidates[0]
            elif len(candidates) > 1:
                row_errors.append("player identity is ambiguous in the master file")
            else:
                row_errors.append("player identity has no matching master key")
        if not source_key and _cell(row.get("Rk")):
            source_key = f"unmapped-row-{_cell(row.get('Rk'))}"
            row_errors.append("Rk is a row locator and cannot be used as canonical identity")
        if not source_key:
            row_errors.append("player_id is missing")
        if not name:
            row_errors.append("player name is missing")
        if not club:
            row_errors.append("club is missing")
        if not competition:
            row_errors.append("competition is missing")
        if not season_id:
            row_errors.append("season label is invalid or missing")
        if not row_errors:
            try:
                NormalizedLegacyRecord(
                    source_player_key=str(source_key),
                    player_name=str(name),
                    club=str(club),
                    competition=str(competition),
                    season_id=season_id or "",
                    source_record_key=record_key,
                )
            except ValidationError as exc:
                row_errors.extend(error["msg"] for error in exc.errors())
        if source_key:
            identities.add(str(source_key))
        if record_key in seen_keys:
            duplicate_source_keys += 1
            row_errors.append("duplicate source record key")
        seen_keys.add(record_key)
        numeric_values: dict[str, float | None] = {}
        for input_name, output_name in (*NUMERIC_FIELDS.items(), *SOURCE_RATE_FIELDS.items()):
            if input_name in row:
                raw_number = _cell(row.get(input_name))
                parsed_number = _float(raw_number, output_name, row_errors)
                if output_name in SOURCE_RATE_FIELDS.values() and parsed_number is not None and parsed_number < 0:
                    row_errors.append(f"{output_name} cannot be negative")
                if output_name in {"source_sot_percent", "save_percent", "clean_sheet_percent"} and raw_number is not None:
                    try:
                        raw_float = float(raw_number)
                    except (TypeError, ValueError):
                        raw_float = math.nan
                    if math.isfinite(raw_float) and not 0 <= raw_float <= 100:
                        warnings.append({"row": index, "warning": f"{output_name} outside 0–100; retained as null"})
                numeric_values[output_name] = parsed_number
        minutes = numeric_values.get("minutes")
        if minutes == 0:
            warnings.append({"row": index, "warning": "zero minutes; rate metrics will be unavailable"})
        shots, shots_on_target = numeric_values.get("shots"), numeric_values.get("shots_on_target")
        if shots is not None and shots_on_target is not None and shots_on_target > shots:
            row_errors.append("shots on target exceeds total shots")
        source_non_penalty_rate = numeric_values.get("source_non_penalty_contributions_per90")
        non_penalty_goals = numeric_values.get("non_penalty_goals")
        assists = numeric_values.get("assists")
        if source_non_penalty_rate is not None and non_penalty_goals is not None and assists is not None and minutes and minutes > 0:
            calculated_rate = 90.0 * (non_penalty_goals + assists) / minutes
            if abs(source_non_penalty_rate - calculated_rate) > 0.01:
                warnings.append({"row": index, "warning": "source G+A-PK differs from the calculated non-penalty contributions per 90 by more than rounding tolerance"})
        age = numeric_values.get("age")
        if age is not None and not 14 <= age <= 60:
            warnings.append({"row": index, "warning": "age outside expected range; profile age will be stored as null"})
        if row_errors:
            errors.append({"row": index, "source_record_key": record_key, "errors": row_errors})
        else:
            valid += 1
    return {
        **inspection,
        "valid_rows": valid,
        "rejected_rows": len(errors),
        "candidate_source_identities": len(identities),
        "duplicate_source_keys": duplicate_source_keys,
        "warnings": warnings,
        "errors": errors,
    }


def preview_csv(
    path: str | Path,
    master_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Describe source-local entities and possible identity collisions without writing data."""
    validation = validate_csv(path, master_path)
    frame = pd.read_csv(path, dtype="string", keep_default_na=True)
    _master, fingerprint_keys = _load_master(master_path)
    rejected_lines = {item["row"] for item in validation["errors"]}
    identity_issue_lines = {
        item["row"] for item in validation["errors"]
        if any("identity" in error or "player_id" in error for error in item["errors"])
    }
    source_key_counts: dict[str, int] = {}
    names_by_key: dict[str, str] = {}
    keys_by_name: dict[str, set[str]] = {}
    club_names: dict[str, str] = {}
    competition_names: dict[str, str] = {}
    for line, row in enumerate(frame.to_dict(orient="records"), start=2):
        if line in rejected_lines:
            continue
        name = _cell(row.get("Player"))
        source_key = _cell(row.get("player_id"))
        if not source_key and master_path:
            fingerprint = (
                normalize_name(str(name or "")),
                normalize_name(str(_cell(row.get("Nation")) or "")),
                str(_cell(row.get("Born")) or ""),
            )
            candidates = fingerprint_keys.get(fingerprint, [])
            if len(candidates) == 1:
                source_key = candidates[0]
        if source_key:
            key = str(source_key)
            source_key_counts[key] = source_key_counts.get(key, 0) + 1
            names_by_key[key] = str(name or "")
            normalized = normalize_name(str(name or ""))
            keys_by_name.setdefault(normalized, set()).add(key)
        club = _cell(row.get("Squad"))
        competition = _cell(row.get("Comp"))
        if club:
            club_names[normalize_name(str(club))] = str(club)
        if competition:
            competition_names[normalize_name(str(competition))] = str(competition)

    existing_player_keys: set[str] = set()
    existing_clubs: set[str] = set()
    existing_competitions: set[str] = set()
    existing_database_available = False
    try:
        connection = connect(db_path)
        try:
            has_migrations = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if has_migrations:
                existing_database_available = True
                existing_player_keys = {
                    row[0] for row in connection.execute(
                        "SELECT source_player_key FROM player_source_keys WHERE source_id=?", (SOURCE_ID,)
                    )
                }
                existing_clubs = {row[0] for row in connection.execute("SELECT normalized_name FROM clubs")}
                existing_competitions = {row[0] for row in connection.execute("SELECT normalized_name FROM competitions")}
        finally:
            connection.close()
    except (FileNotFoundError, RuntimeError, ValueError, sqlite3.Error):
        existing_database_available = False

    collisions = [
        {"normalized_name": name, "candidate_count": len(keys), "source_player_keys": sorted(keys)}
        for name, keys in sorted(keys_by_name.items()) if len(keys) > 1
    ]
    missing_values = {
        str(column): int(count)
        for column, count in frame.isna().sum().items() if int(count) > 0
    }
    known_source_columns = set(REQUIRED_ROW_FIELDS) | {"Rk", "player_id", "Nation", "Pos", "Born", "Age"} | set(NUMERIC_FIELDS) | set(SOURCE_RATE_FIELDS)
    rejected = validation["errors"]
    return {
        **validation,
        "preview": {
            "database_comparison_available": existing_database_available,
            "source_local_player_entities": len(source_key_counts),
            "source_keys_with_multiple_records": sum(count > 1 for count in source_key_counts.values()),
            "records_reusing_source_local_keys": sum(max(0, count - 1) for count in source_key_counts.values()),
            "existing_player_key_matches": sum(key in existing_player_keys for key in source_key_counts) if existing_database_available else None,
            "new_player_keys": sum(key not in existing_player_keys for key in source_key_counts) if existing_database_available else None,
            "new_clubs": sum(normalized not in existing_clubs for normalized in club_names) if existing_database_available else None,
            "new_competitions": sum(normalized not in existing_competitions for normalized in competition_names) if existing_database_available else None,
            "ambiguous_identity_records": len(identity_issue_lines),
            "same_name_distinct_source_keys": collisions,
            "missing_values_by_column": missing_values,
            "invalid_values": validation["errors"],
            "rejected_records": rejected,
            "unmapped_columns_retained_in_raw_payload": sorted(set(frame.columns) - known_source_columns),
            "identity_note": "Repeated supplied source keys group records within this source only. Same-name candidates remain separate; no provider identity is inferred.",
        },
    }


def _ensure_source(connection: sqlite3.Connection) -> None:
    connection.execute(
        """INSERT OR IGNORE INTO data_sources
           (id, provider_name, provider_type, source_url, license_name, license_url,
            permitted_use, attribution_requirements, redistribution_allowed,
            commercial_use_allowed, reviewed_at, rights_status, active_status, is_default)
           VALUES (?, ?, 'user_supplied_file', NULL, NULL, NULL,
            'Use supplied within the local project; external redistribution permissions are not documented.',
            NULL, NULL, NULL, NULL, 'unverified', 'active', 1)""",
        (SOURCE_ID, SOURCE_NAME),
    )


def _insert_metrics(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """INSERT INTO metric_definitions
           (metric_key, display_name, description, data_type, unit, formula,
            required_fields_json, minimum_data_requirements, availability_status, formula_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(metric_key) DO UPDATE SET
             display_name=excluded.display_name,
             description=excluded.description,
             data_type=excluded.data_type,
             unit=excluded.unit,
             formula=excluded.formula,
             required_fields_json=excluded.required_fields_json,
             minimum_data_requirements=excluded.minimum_data_requirements,
             availability_status=excluded.availability_status,
             formula_version=excluded.formula_version""",
        [(*metric[:7], None, *metric[7:]) for metric in METRICS],
    )


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def import_csv(
    path: str | Path,
    master_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    validation = validate_csv(path, master_path)
    if validation["valid_rows"] == 0:
        raise ImportValidationError("No valid statistical records remain after validation", validation["errors"])
    source_path = Path(path)
    frame = pd.read_csv(source_path, dtype="string", keep_default_na=True)
    master, fingerprint_keys = _load_master(master_path)
    checksum = validation["sha256"]
    release_id = stable_id(f"release:{SOURCE_ID}:{checksum}")
    job_id = str(uuid.uuid4())
    connection = connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        if not connection.execute("SELECT 1 FROM schema_migrations LIMIT 1").fetchone():
            raise RuntimeError("Database has no applied migrations; run `python -m app.ingestion.cli init` first")
        connection.execute("BEGIN IMMEDIATE")
        _ensure_source(connection)
        _insert_metrics(connection)
        old_release = connection.execute(
            "SELECT id FROM source_releases WHERE source_id=? AND checksum=?", (SOURCE_ID, checksum)
        ).fetchone()
        if old_release:
            connection.execute(
                "INSERT INTO import_jobs(id, source_release_id, status, completed_at, rows_read, rows_inserted, rows_updated, rows_warning, rows_rejected) VALUES (?, ?, 'unchanged', ?, ?, 0, 0, 0, 0)",
                (job_id, old_release["id"], now, len(frame)),
            )
            connection.commit()
            return {"job_id": job_id, "release_id": old_release["id"], "status": "unchanged", "rows_read": len(frame), "rows_inserted": 0, "rows_updated": 0, "rows_warning": 0, "rows_rejected": 0, "sha256": checksum}

        connection.execute("UPDATE source_releases SET is_current=0 WHERE source_id=?", (SOURCE_ID,))
        connection.execute(
            "INSERT INTO source_releases(id, source_id, release_name, release_date, checksum, file_name, schema_version, is_current) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (release_id, SOURCE_ID, source_path.stem, None, checksum, source_path.name, SOURCE_VERSION),
        )
        connection.execute(
            "INSERT INTO import_jobs(id, source_release_id, status, rows_read) VALUES (?, ?, 'running', ?)",
            (job_id, release_id, len(frame)),
        )

        inserted = 0
        rejected = 0
        warning_rows = 0
        valid_by_row = {item["row"]: item["errors"] for item in validation["errors"]}
        warnings_by_row: dict[int, list[str]] = {}
        for warning in validation["warnings"]:
            warnings_by_row.setdefault(warning["row"], []).append(warning["warning"])
        for row_number, row in enumerate(frame.to_dict(orient="records"), start=2):
            source_record_key = str(_cell(row.get("Rk")) or f"row-{row_number}")
            errors = list(valid_by_row.get(row_number, []))
            name = _cell(row.get("Player"))
            club_name = _cell(row.get("Squad"))
            competition_name = _cell(row.get("Comp"))
            season_id, season_label = _season(row.get("season"))
            source_player_key = _cell(row.get("player_id"))
            if not source_player_key and master_path:
                fingerprint = (
                    normalize_name(str(name or "")),
                    normalize_name(str(_cell(row.get("Nation")) or "")),
                    str(_cell(row.get("Born")) or ""),
                )
                candidates = fingerprint_keys.get(fingerprint, [])
                if len(candidates) == 1:
                    source_player_key = candidates[0]
            if not source_player_key:
                source_player_key = f"unresolved-row-{row_number}"

            raw_payload = {str(key): _cell(value) for key, value in row.items()}
            payload_json = json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":"))
            payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

            if errors:
                rejected += 1
                connection.execute(
                    "INSERT INTO source_records(id, source_release_id, source_record_key, source_row_number, payload_hash, payload_json, status, error_json) VALUES (?, ?, ?, ?, ?, ?, 'rejected', ?)",
                    (str(uuid.uuid4()), release_id, f"rejected:{row_number}:{source_record_key}", row_number, payload_hash, payload_json, json.dumps(errors)),
                )
                continue

            master_row = master.get(str(source_player_key), {})
            canonical_name = str(_cell(master_row.get("player_name")) or name)
            normalized_player = normalize_name(canonical_name)
            player_id = stable_id(f"player:{SOURCE_ID}:{source_player_key}")
            nation = _cell(master_row.get("nation_raw")) or _cell(row.get("Nation"))
            raw_position = _cell(row.get("Pos")) or _cell(master_row.get("position_raw"))
            birth_year_value = _safe_float(master_row.get("birth_year"))
            if birth_year_value is None:
                birth_year_value = _safe_float(row.get("Born"))
            birth_year = int(birth_year_value) if birth_year_value is not None and birth_year_value.is_integer() else None
            age = _safe_float(master_row.get("age_at_dataset_season"))
            if age is None:
                age = _safe_float(row.get("Age"))
            if age is not None and not 14 <= age <= 60:
                age = None

            connection.execute(
                """INSERT OR IGNORE INTO players(id, canonical_name, normalized_name, birth_year, nationality, primary_position, identity_status)
                   VALUES (?, ?, ?, ?, ?, ?, 'provisional')""",
                (player_id, canonical_name, normalized_player, birth_year, nation, raw_position),
            )
            key_row = connection.execute(
                "SELECT player_id FROM player_source_keys WHERE source_id=? AND source_player_key=?",
                (SOURCE_ID, str(source_player_key)),
            ).fetchone()
            if key_row and key_row["player_id"] != player_id:
                raise RuntimeError(f"Source identity key {source_player_key} maps to conflicting canonical players")
            connection.execute(
                "INSERT OR IGNORE INTO player_source_keys(source_id, source_player_key, player_id, key_status) VALUES (?, ?, ?, 'provisional')",
                (SOURCE_ID, str(source_player_key), player_id),
            )
            alias = canonical_name
            connection.execute(
                "INSERT OR IGNORE INTO player_aliases(player_id, alias, normalized_alias, source_id) VALUES (?, ?, ?, ?)",
                (player_id, alias, normalize_name(alias), SOURCE_ID),
            )

            club_id = stable_id(f"club:{SOURCE_ID}:{normalize_name(str(club_name))}")
            competition_id = stable_id(f"competition:{SOURCE_ID}:{normalize_name(str(competition_name))}")
            connection.execute(
                "INSERT OR IGNORE INTO clubs(id, canonical_name, normalized_name) VALUES (?, ?, ?)",
                (club_id, str(club_name), normalize_name(str(club_name))),
            )
            connection.execute(
                "INSERT OR IGNORE INTO competitions(id, canonical_name, normalized_name, competition_type) VALUES (?, ?, ?, 'league')",
                (competition_id, str(competition_name), normalize_name(str(competition_name))),
            )
            connection.execute(
                "INSERT OR IGNORE INTO club_aliases(club_id, source_id, alias, normalized_alias) VALUES (?, ?, ?, ?)",
                (club_id, SOURCE_ID, str(club_name), normalize_name(str(club_name))),
            )
            connection.execute(
                "INSERT OR IGNORE INTO competition_aliases(competition_id, source_id, alias, normalized_alias) VALUES (?, ?, ?, ?)",
                (competition_id, SOURCE_ID, str(competition_name), normalize_name(str(competition_name))),
            )
            connection.execute(
                "INSERT OR IGNORE INTO seasons(id, label, season_type) VALUES (?, ?, 'split_year')",
                (season_id, season_label),
            )
            spell_id = stable_id(f"spell:{SOURCE_ID}:{player_id}:{club_id}:{season_id}")
            connection.execute(
                "INSERT OR IGNORE INTO player_club_spells(id, player_id, club_id, season_id, source_id) VALUES (?, ?, ?, ?, ?)",
                (spell_id, player_id, club_id, season_id, SOURCE_ID),
            )
            appearance_id = stable_id(f"appearance:{SOURCE_ID}:{player_id}:{club_id}:{competition_id}:{season_id}")
            connection.execute(
                "INSERT OR IGNORE INTO player_competition_appearances(id, player_id, club_id, competition_id, season_id, source_id) VALUES (?, ?, ?, ?, ?, ?)",
                (appearance_id, player_id, club_id, competition_id, season_id, SOURCE_ID),
            )

            errors_for_metrics: list[str] = []
            values: dict[str, float | None] = {}
            for input_name, output_name in NUMERIC_FIELDS.items():
                if input_name in row:
                    values[output_name] = _float(_cell(row.get(input_name)), output_name, errors_for_metrics)
            if errors_for_metrics:
                raise RuntimeError(f"Validated row changed during import at CSV line {row_number}")
            non_penalty_goals = values.get("non_penalty_goals")
            assists = values.get("assists")
            values["non_penalty_goal_contributions"] = (
                non_penalty_goals + assists
                if non_penalty_goals is not None and assists is not None
                else None
            )
            values["position_raw"] = raw_position
            values["raw_metrics_json"] = payload_json
            stat_id = stable_id(f"stat:{release_id}:{source_record_key}")
            column_sql = ", ".join(STAT_COLUMNS)
            placeholders = ", ".join("?" for _ in STAT_COLUMNS)
            connection.execute(
                f"""INSERT INTO player_stat_records
                    (id, player_id, club_id, competition_id, season_id, source_release_id, source_record_key, scope, {column_sql})
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'club_competition', {placeholders})""",
                (stat_id, player_id, club_id, competition_id, season_id, release_id, source_record_key, *(values.get(column) for column in STAT_COLUMNS)),
            )
            connection.execute(
                "INSERT INTO source_records(id, source_release_id, source_record_key, source_row_number, payload_hash, payload_json, status, error_json, player_stat_record_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), release_id, source_record_key, row_number, payload_hash, payload_json,
                    "warning" if warnings_by_row.get(row_number) else "accepted",
                    json.dumps(warnings_by_row.get(row_number)) if warnings_by_row.get(row_number) else None,
                    stat_id,
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO identity_match_decisions(id, source_id, source_player_key, candidate_player_id, status, evidence_json, method_version) VALUES (?, ?, ?, ?, 'automatically_matched', ?, ?)",
                (str(uuid.uuid4()), SOURCE_ID, str(source_player_key), player_id, json.dumps({"basis": "same supplied dataset-local key", "scope": "this source release only", "provider_id_verified": False, "identity_status": "provisional"}), "legacy-key-v1"),
            )
            inserted += 1
            if warnings_by_row.get(row_number):
                warning_rows += 1

        connection.execute("UPDATE source_releases SET is_current=1 WHERE id=?", (release_id,))
        status = "completed_with_rejections" if rejected else "completed"
        summary = f"{rejected} rows rejected" if rejected else None
        connection.execute(
            "UPDATE import_jobs SET status=?, completed_at=?, rows_inserted=?, rows_warning=?, rows_rejected=?, error_summary=? WHERE id=?",
            (status, now, inserted, warning_rows, rejected, summary, job_id),
        )
        connection.commit()
        return {
            "job_id": job_id,
            "release_id": release_id,
            "status": status,
            "rows_read": len(frame),
            "rows_inserted": inserted,
            "rows_updated": 0,
            "rows_warning": warning_rows,
            "rows_rejected": rejected,
            "sha256": checksum,
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def import_report(job_id: str, db_path: str | Path | None = None) -> dict[str, Any]:
    connection = connect(db_path)
    try:
        job = connection.execute(
            """SELECT j.*, r.file_name, r.checksum, r.release_name, d.provider_name
               FROM import_jobs j JOIN source_releases r ON r.id=j.source_release_id
               JOIN data_sources d ON d.id=r.source_id WHERE j.id=?""",
            (job_id,),
        ).fetchone()
        if not job:
            raise KeyError(f"Import job not found: {job_id}")
        rejected = connection.execute(
            "SELECT source_row_number, source_record_key, error_json FROM source_records WHERE source_release_id=? AND status='rejected' ORDER BY source_row_number",
            (job["source_release_id"],),
        ).fetchall()
        warnings = connection.execute(
            "SELECT source_row_number, source_record_key, error_json FROM source_records WHERE source_release_id=? AND status='warning' ORDER BY source_row_number",
            (job["source_release_id"],),
        ).fetchall()
        return {"job": dict(job), "rejected_rows": [dict(row) for row in rejected], "warnings": [dict(row) for row in warnings]}
    finally:
        connection.close()
