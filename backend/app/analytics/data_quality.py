from __future__ import annotations

from typing import Any

import pandas as pd


IDENTIFIER_COLUMNS = {"id", "player_id", "club_id", "competition_id", "season_id", "source_release_id", "source_record_key"}
COUNT_COLUMNS = {
    "appearances", "starts", "minutes", "goals", "assists", "goal_contributions", "non_penalty_goals",
    "non_penalty_goal_contributions", "penalties_scored", "penalties_attempted", "yellow_cards", "red_cards",
    "second_yellow_cards", "fouls_committed", "fouls_drawn", "own_goals", "shots", "shots_on_target",
    "crosses", "tackles_won", "interceptions", "goals_against", "shots_on_target_against", "saves", "wins",
    "draws", "losses", "clean_sheets", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed",
}


def quality_report(frame: pd.DataFrame, declared_columns: list[dict[str, Any]]) -> dict[str, Any]:
    total_rows, total_columns = frame.shape
    types = {str(column["name"]): str(column["type"] or "unknown") for column in declared_columns}
    columns: list[dict[str, Any]] = []
    for name in frame.columns:
        missing = int(frame[name].isna().sum())
        columns.append({
            "column": name,
            "declared_type": types.get(name, "unknown"),
            "dtype": str(frame[name].dtype),
            "missing_count": missing,
            "missing_percent": round(100 * missing / total_rows, 2) if total_rows else None,
            "unique_values": int(frame[name].nunique(dropna=True)),
        })
    numeric_columns = [name for name in frame.columns if name not in IDENTIFIER_COLUMNS and pd.api.types.is_numeric_dtype(frame[name])]
    categorical_columns = [name for name in frame.columns if name not in IDENTIFIER_COLUMNS and name not in numeric_columns]
    quality_fields = [name for name in frame.columns if name not in {"id", "created_at", "raw_metrics_json"}]
    cell_count = total_rows * len(quality_fields)
    observed = int(frame[quality_fields].notna().sum().sum()) if quality_fields else 0
    negative_count_values = int(sum((frame[column] < 0).sum() for column in COUNT_COLUMNS if column in frame.columns))
    key_dupes = int(frame.duplicated(subset=["source_release_id", "source_record_key"], keep=False).sum())
    duplicate_content_columns = [name for name in quality_fields if name not in {"source_record_key"}]
    duplicate_content = int(frame.duplicated(subset=duplicate_content_columns, keep=False).sum()) if duplicate_content_columns else 0
    return {
        "total_records": int(total_rows),
        "total_columns": int(total_columns),
        "missing_cells": int(sum(item["missing_count"] for item in columns)),
        "completeness_percent": round(100 * observed / cell_count, 2) if cell_count else None,
        "duplicate_source_key_records": key_dupes,
        "duplicate_content_records": duplicate_content,
        "potential_invalid_values": {
            "negative_count_metric_cells": negative_count_values,
            "negative_minutes_records": int((frame["minutes"] < 0).sum()) if "minutes" in frame else 0,
            "age_outside_0_100_records": int(((frame["age"] < 0) | (frame["age"] > 100)).sum()) if "age" in frame else 0,
            "missing_player_reference_records": int(frame["player_id"].isna().sum()) if "player_id" in frame else 0,
        },
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "columns": columns,
        "methodology": "Missing values are reported, not imputed. Duplicate content checks omit internal ID, import timestamp, raw payload, and source row key; repeated similar records may be legitimate and require source review. Potential invalid values are checks, not automatic corrections.",
    }

