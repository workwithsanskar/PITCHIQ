from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


def load_metric_frame(
    connection: sqlite3.Connection,
    metrics: Sequence[str],
    metric_sql: Mapping[str, str],
    where: str,
    params: Sequence[Any],
) -> pd.DataFrame:
    """Load only approved metric expressions from the current, filtered release."""
    if any(metric not in metric_sql for metric in metrics):
        raise ValueError("Unsupported metric requested for analytics frame")
    selected = ", ".join(f"({metric_sql[key]}) AS \"{key}\"" for key in metrics)
    if selected:
        selected = ", " + selected
    sql = f"""SELECT s.id AS record_id, p.id AS player_id, p.canonical_name AS player,
                     s.position_raw, s.club_id, s.competition_id, s.season_id,
                     c.canonical_name AS club, co.canonical_name AS competition,
                     se.label AS season{selected}
              FROM player_stat_records s
              JOIN source_releases r ON r.id=s.source_release_id
              JOIN data_sources d ON d.id=r.source_id
              JOIN players p ON p.id=s.player_id
              JOIN seasons se ON se.id=s.season_id
              LEFT JOIN clubs c ON c.id=s.club_id
              LEFT JOIN competitions co ON co.id=s.competition_id
              WHERE {where}
              ORDER BY p.canonical_name, se.label, co.canonical_name, c.canonical_name"""
    frame = pd.read_sql_query(sql, connection, params=list(params))
    for metric in metrics:
        frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    frame["position"] = (
        frame["position_raw"].fillna("").astype("string").str.split(",").str[0].str.strip().replace("", pd.NA).fillna("Unknown")
    )
    return frame


def load_quality_frame(connection: sqlite3.Connection) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load current-release stat records and declared SQLite column types."""
    columns = [dict(row) for row in connection.execute("PRAGMA table_info(player_stat_records)").fetchall()]
    frame = pd.read_sql_query(
        """SELECT s.* FROM player_stat_records s
           JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1 AND d.active_status='active'
           ORDER BY s.id""",
        connection,
    )
    return frame, columns

