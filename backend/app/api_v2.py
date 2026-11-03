"""Database-backed, typed API for PITCHIQ v2."""
from __future__ import annotations

import csv
import io
import json
import math
import os
import sqlite3
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from .analytics.correlation import correlation_matrix, interpret_correlation
from .analytics.data_quality import quality_report
from .analytics.dataset import load_metric_frame, load_quality_frame
from .analytics.descriptive import grouped_summaries, summarize_frame
from .analytics.distributions import histogram as pandas_histogram
from .analytics.outliers import iqr_outliers
from .analytics.visualizations import render_missingness_png, render_png
from .database import DatabaseNotInitialized, connect
from .ingestion.legacy_csv import normalize_name
from .v2_schemas import (
    ComparePlayersRequest,
    DataLabQuery,
    DescriptiveRequest,
    IdentityReviewItem,
    IdentitySummary,
    OutlierRequest,
    PageClubs,
    PageCompetitions,
    PageMeta,
    PagePlayers,
    PlayerDetail,
    PlayerSummary,
    StatRecord,
    VisualizationRequest,
)

production = os.getenv("PITCHIQ_ENV", "development").lower() == "production"
v2_app = FastAPI(
    title="PITCHIQ API v2",
    version="2.0.0",
    description="Canonical, source-aware football analytics API. Unsupported metrics are omitted.",
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

METRIC_SQL = {
    "goals": "s.goals",
    "assists": "s.assists",
    "appearances": "s.appearances",
    "starts": "s.starts",
    "minutes": "s.minutes",
    "shots": "s.shots",
    "shots_on_target": "s.shots_on_target",
    "non_penalty_goals": "s.non_penalty_goals",
    "non_penalty_goal_contributions": "s.non_penalty_goal_contributions",
    "non_penalty_contributions_per90": "CASE WHEN s.minutes > 0 AND s.non_penalty_goals IS NOT NULL AND s.assists IS NOT NULL THEN 90.0 * (s.non_penalty_goals + s.assists) / s.minutes END",
    "penalties_scored": "s.penalties_scored",
    "penalties_attempted": "s.penalties_attempted",
    "yellow_cards": "s.yellow_cards",
    "red_cards": "s.red_cards",
    "second_yellow_cards": "s.second_yellow_cards",
    "fouls_committed": "s.fouls_committed",
    "fouls_drawn": "s.fouls_drawn",
    "own_goals": "s.own_goals",
    "goals_against": "s.goals_against",
    "goals_against_per90": "s.goals_against_per90",
    "shots_on_target_against": "s.shots_on_target_against",
    "saves": "s.saves",
    "save_percent": "s.save_percent",
    "wins": "s.wins",
    "draws": "s.draws",
    "losses": "s.losses",
    "clean_sheets": "s.clean_sheets",
    "clean_sheet_percent": "s.clean_sheet_percent",
    "penalties_faced": "s.penalties_faced",
    "penalties_against": "s.penalties_against",
    "penalties_saved": "s.penalties_saved",
    "penalties_missed": "s.penalties_missed",
    "shot_accuracy": "COALESCE(s.source_sot_percent, CASE WHEN s.shots > 0 AND s.shots_on_target IS NOT NULL THEN 100.0 * s.shots_on_target / s.shots END)",
    "goals_per90": "CASE WHEN s.minutes > 0 AND s.goals IS NOT NULL THEN 90.0 * s.goals / s.minutes END",
    "assists_per90": "CASE WHEN s.minutes > 0 AND s.assists IS NOT NULL THEN 90.0 * s.assists / s.minutes END",
    "contributions_per90": "CASE WHEN s.minutes > 0 AND s.goals IS NOT NULL AND s.assists IS NOT NULL THEN 90.0 * (s.goals + s.assists) / s.minutes END",
    "non_penalty_goals_per90": "CASE WHEN s.minutes > 0 AND s.non_penalty_goals IS NOT NULL THEN 90.0 * s.non_penalty_goals / s.minutes END",
    "crosses_per90": "CASE WHEN s.minutes > 0 AND s.crosses IS NOT NULL THEN 90.0 * s.crosses / s.minutes END",
    "tackles_won_per90": "CASE WHEN s.minutes > 0 AND s.tackles_won IS NOT NULL THEN 90.0 * s.tackles_won / s.minutes END",
    "interceptions_per90": "CASE WHEN s.minutes > 0 AND s.interceptions IS NOT NULL THEN 90.0 * s.interceptions / s.minutes END",
    "goals_per_appearance": "CASE WHEN s.appearances > 0 AND s.goals IS NOT NULL THEN 1.0 * s.goals / s.appearances END",
    "assists_per_appearance": "CASE WHEN s.appearances > 0 AND s.assists IS NOT NULL THEN 1.0 * s.assists / s.appearances END",
    "goals_per_shot": "CASE WHEN s.shots > 0 AND s.goals IS NOT NULL THEN 100.0 * s.goals / s.shots END",
    "shots_per_goal": "CASE WHEN s.goals > 0 AND s.shots IS NOT NULL THEN 1.0 * s.shots / s.goals END",
    "shots_per90": "CASE WHEN s.minutes > 0 AND s.shots IS NOT NULL THEN 90.0 * s.shots / s.minutes END",
    "shots_on_target_per90": "CASE WHEN s.minutes > 0 AND s.shots_on_target IS NOT NULL THEN 90.0 * s.shots_on_target / s.minutes END",
    "crosses": "s.crosses",
    "tackles_won": "s.tackles_won",
    "interceptions": "s.interceptions",
}
METRIC_UNITS = {
    "goals": "goals", "assists": "assists", "appearances": "matches", "starts": "matches",
    "minutes": "minutes", "shots": "shots", "shots_on_target": "shots",
    "shot_accuracy": "%", "goals_per90": "goals/90", "assists_per90": "assists/90",
    "contributions_per90": "contributions/90", "shots_per90": "shots/90",
    "non_penalty_goals": "goals", "non_penalty_goal_contributions": "contributions",
    "non_penalty_contributions_per90": "contributions/90",
    "penalties_scored": "goals", "penalties_attempted": "attempts", "yellow_cards": "cards",
    "red_cards": "cards", "second_yellow_cards": "cards", "fouls_committed": "fouls",
    "fouls_drawn": "fouls", "own_goals": "goals", "non_penalty_goals_per90": "goals/90",
    "goals_against": "goals", "goals_against_per90": "goals/90", "shots_on_target_against": "shots",
    "saves": "saves", "save_percent": "%", "wins": "matches", "draws": "matches", "losses": "matches",
    "clean_sheets": "matches", "clean_sheet_percent": "%", "penalties_faced": "attempts",
    "penalties_against": "goals", "penalties_saved": "saves", "penalties_missed": "attempts",
    "crosses_per90": "crosses/90", "tackles_won_per90": "tackles/90", "interceptions_per90": "interceptions/90",
    "goals_per_appearance": "goals/appearance", "assists_per_appearance": "assists/appearance",
    "goals_per_shot": "%", "shots_per_goal": "shots/goal",
    "shots_on_target_per90": "shots/90", "crosses": "crosses", "tackles_won": "tackles",
    "interceptions": "interceptions",
}
SORT_SQL = {
    "name": "canonical_name", "goals": "goals", "assists": "assists", "minutes": "minutes",
    "appearances": "appearances", "shots": "shots", "shots_on_target": "shots_on_target",
    "crosses": "crosses", "tackles_won": "tackles_won", "interceptions": "interceptions",
    "goals_per90": "goals_per90", "assists_per90": "assists_per90",
    "contributions_per90": "contributions_per90", "shot_accuracy": "shot_accuracy",
    "non_penalty_goals": "non_penalty_goals", "non_penalty_goal_contributions": "non_penalty_goal_contributions",
    "non_penalty_contributions_per90": "non_penalty_contributions_per90",
    "penalties_scored": "penalties_scored", "penalties_attempted": "penalties_attempted",
    "yellow_cards": "yellow_cards", "red_cards": "red_cards", "second_yellow_cards": "second_yellow_cards",
    "fouls_committed": "fouls_committed", "fouls_drawn": "fouls_drawn", "own_goals": "own_goals",
    "non_penalty_goals_per90": "non_penalty_goals_per90", "crosses_per90": "crosses_per90",
    "tackles_won_per90": "tackles_won_per90", "interceptions_per90": "interceptions_per90",
    "goals_per_appearance": "goals_per_appearance", "assists_per_appearance": "assists_per_appearance",
    "goals_per_shot": "goals_per_shot", "shots_per_goal": "shots_per_goal",
    "shots_per90": "shots_per90", "shots_on_target_per90": "shots_on_target_per90",
}
SUMMARY_CTE = """
WITH current_stats AS (
    SELECT s.*, c.canonical_name AS club_name, co.canonical_name AS competition_name,
           se.label AS season_label, sr.source_id, sr.release_name
    FROM player_stat_records s
    JOIN source_releases sr ON sr.id=s.source_release_id AND sr.is_current=1
    JOIN data_sources ds ON ds.id=sr.source_id AND ds.active_status='active' AND ds.is_default=1
    LEFT JOIN clubs c ON c.id=s.club_id
    LEFT JOIN competitions co ON co.id=s.competition_id
    JOIN seasons se ON se.id=s.season_id
), aggregated AS (
    SELECT p.id, p.canonical_name, p.nationality, p.primary_position, p.identity_status,
           COUNT(cs.id) AS record_count, COUNT(DISTINCT cs.club_id) AS club_count,
           COUNT(DISTINCT cs.competition_id) AS competition_count,
           GROUP_CONCAT(DISTINCT cs.season_label) AS seasons,
           CASE WHEN COUNT(cs.appearances)=COUNT(cs.id) THEN SUM(cs.appearances) END AS appearances,
           CASE WHEN COUNT(cs.starts)=COUNT(cs.id) THEN SUM(cs.starts) END AS starts,
           CASE WHEN COUNT(cs.minutes)=COUNT(cs.id) THEN SUM(cs.minutes) END AS minutes,
           CASE WHEN COUNT(cs.goals)=COUNT(cs.id) THEN SUM(cs.goals) END AS goals,
           CASE WHEN COUNT(cs.assists)=COUNT(cs.id) THEN SUM(cs.assists) END AS assists,
           CASE WHEN COUNT(cs.shots)=COUNT(cs.id) THEN SUM(cs.shots) END AS shots,
           CASE WHEN COUNT(cs.shots_on_target)=COUNT(cs.id) THEN SUM(cs.shots_on_target) END AS shots_on_target,
           CASE WHEN COUNT(cs.crosses)=COUNT(cs.id) THEN SUM(cs.crosses) END AS crosses,
           CASE WHEN COUNT(cs.tackles_won)=COUNT(cs.id) THEN SUM(cs.tackles_won) END AS tackles_won,
           CASE WHEN COUNT(cs.interceptions)=COUNT(cs.id) THEN SUM(cs.interceptions) END AS interceptions,
           CASE WHEN COUNT(cs.non_penalty_goals)=COUNT(cs.id) THEN SUM(cs.non_penalty_goals) END AS non_penalty_goals,
           CASE WHEN COUNT(cs.non_penalty_goal_contributions)=COUNT(cs.id) THEN SUM(cs.non_penalty_goal_contributions) END AS non_penalty_goal_contributions,
           CASE WHEN COUNT(cs.penalties_scored)=COUNT(cs.id) THEN SUM(cs.penalties_scored) END AS penalties_scored,
           CASE WHEN COUNT(cs.penalties_attempted)=COUNT(cs.id) THEN SUM(cs.penalties_attempted) END AS penalties_attempted,
           CASE WHEN COUNT(cs.yellow_cards)=COUNT(cs.id) THEN SUM(cs.yellow_cards) END AS yellow_cards,
           CASE WHEN COUNT(cs.red_cards)=COUNT(cs.id) THEN SUM(cs.red_cards) END AS red_cards,
           CASE WHEN COUNT(cs.second_yellow_cards)=COUNT(cs.id) THEN SUM(cs.second_yellow_cards) END AS second_yellow_cards,
           CASE WHEN COUNT(cs.fouls_committed)=COUNT(cs.id) THEN SUM(cs.fouls_committed) END AS fouls_committed,
           CASE WHEN COUNT(cs.fouls_drawn)=COUNT(cs.id) THEN SUM(cs.fouls_drawn) END AS fouls_drawn,
           CASE WHEN COUNT(cs.own_goals)=COUNT(cs.id) THEN SUM(cs.own_goals) END AS own_goals,
           CASE WHEN COUNT(cs.goals_against)=COUNT(cs.id) THEN SUM(cs.goals_against) END AS goals_against,
           CASE WHEN COUNT(cs.shots_on_target_against)=COUNT(cs.id) THEN SUM(cs.shots_on_target_against) END AS shots_on_target_against,
           CASE WHEN COUNT(cs.saves)=COUNT(cs.id) THEN SUM(cs.saves) END AS saves,
           CASE WHEN COUNT(cs.wins)=COUNT(cs.id) THEN SUM(cs.wins) END AS wins,
           CASE WHEN COUNT(cs.draws)=COUNT(cs.id) THEN SUM(cs.draws) END AS draws,
           CASE WHEN COUNT(cs.losses)=COUNT(cs.id) THEN SUM(cs.losses) END AS losses,
           CASE WHEN COUNT(cs.clean_sheets)=COUNT(cs.id) THEN SUM(cs.clean_sheets) END AS clean_sheets,
           CASE WHEN COUNT(cs.penalties_faced)=COUNT(cs.id) THEN SUM(cs.penalties_faced) END AS penalties_faced,
           CASE WHEN COUNT(cs.penalties_against)=COUNT(cs.id) THEN SUM(cs.penalties_against) END AS penalties_against,
           CASE WHEN COUNT(cs.penalties_saved)=COUNT(cs.id) THEN SUM(cs.penalties_saved) END AS penalties_saved,
           CASE WHEN COUNT(cs.penalties_missed)=COUNT(cs.id) THEN SUM(cs.penalties_missed) END AS penalties_missed,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.goals_against)=COUNT(cs.id) THEN 90.0*SUM(cs.goals_against)/SUM(cs.minutes) END AS goals_against_per90,
           CASE WHEN SUM(cs.shots_on_target_against)>0 AND COUNT(cs.shots_on_target_against)=COUNT(cs.id) AND COUNT(cs.saves)=COUNT(cs.id) THEN 100.0*SUM(cs.saves)/SUM(cs.shots_on_target_against) END AS save_percent,
           CASE WHEN COUNT(cs.id)=1 AND COUNT(cs.clean_sheet_percent)=1 THEN MAX(cs.clean_sheet_percent) END AS clean_sheet_percent,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.goals)=COUNT(cs.id) THEN 90.0*SUM(cs.goals)/SUM(cs.minutes) END AS goals_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.assists)=COUNT(cs.id) THEN 90.0*SUM(cs.assists)/SUM(cs.minutes) END AS assists_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.goals)=COUNT(cs.id) AND COUNT(cs.assists)=COUNT(cs.id) THEN 90.0*(SUM(cs.goals)+SUM(cs.assists))/SUM(cs.minutes) END AS contributions_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.non_penalty_goals)=COUNT(cs.id) THEN 90.0*SUM(cs.non_penalty_goals)/SUM(cs.minutes) END AS non_penalty_goals_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.non_penalty_goals)=COUNT(cs.id) AND COUNT(cs.assists)=COUNT(cs.id) THEN 90.0*(SUM(cs.non_penalty_goals)+SUM(cs.assists))/SUM(cs.minutes) END AS non_penalty_contributions_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.crosses)=COUNT(cs.id) THEN 90.0*SUM(cs.crosses)/SUM(cs.minutes) END AS crosses_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.tackles_won)=COUNT(cs.id) THEN 90.0*SUM(cs.tackles_won)/SUM(cs.minutes) END AS tackles_won_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.interceptions)=COUNT(cs.id) THEN 90.0*SUM(cs.interceptions)/SUM(cs.minutes) END AS interceptions_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.shots)=COUNT(cs.id) THEN 90.0*SUM(cs.shots)/SUM(cs.minutes) END AS shots_per90,
           CASE WHEN SUM(cs.minutes)>0 AND COUNT(cs.minutes)=COUNT(cs.id) AND COUNT(cs.shots_on_target)=COUNT(cs.id) THEN 90.0*SUM(cs.shots_on_target)/SUM(cs.minutes) END AS shots_on_target_per90,
           CASE WHEN SUM(cs.appearances)>0 AND COUNT(cs.appearances)=COUNT(cs.id) AND COUNT(cs.goals)=COUNT(cs.id) THEN 1.0*SUM(cs.goals)/SUM(cs.appearances) END AS goals_per_appearance,
           CASE WHEN SUM(cs.appearances)>0 AND COUNT(cs.appearances)=COUNT(cs.id) AND COUNT(cs.assists)=COUNT(cs.id) THEN 1.0*SUM(cs.assists)/SUM(cs.appearances) END AS assists_per_appearance,
           CASE WHEN SUM(cs.shots)>0 AND COUNT(cs.shots)=COUNT(cs.id) AND COUNT(cs.goals)=COUNT(cs.id) THEN 100.0*SUM(cs.goals)/SUM(cs.shots) END AS goals_per_shot,
           CASE WHEN SUM(cs.goals)>0 AND COUNT(cs.goals)=COUNT(cs.id) AND COUNT(cs.shots)=COUNT(cs.id) THEN 1.0*SUM(cs.shots)/SUM(cs.goals) END AS shots_per_goal,
           CASE WHEN SUM(cs.shots)>0 AND COUNT(cs.shots)=COUNT(cs.id) AND COUNT(cs.shots_on_target)=COUNT(cs.id) THEN 100.0*SUM(cs.shots_on_target)/SUM(cs.shots) END AS shot_accuracy
    FROM players p JOIN current_stats cs ON cs.player_id=p.id
    {where}
           GROUP BY p.id
)
"""


def _connection():
    try:
        connection = connect()
    except DatabaseNotInitialized as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone():
            raise HTTPException(status_code=503, detail="PITCHIQ v2 migrations have not been initialized")
        yield connection
    finally:
        connection.close()


@v2_app.exception_handler(HTTPException)
async def v2_http_error(_request: Request, exc: HTTPException):
    code = {404: "not_found", 409: "conflict", 422: "invalid_request", 503: "unavailable"}.get(exc.status_code, "request_error")
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail)}})


@v2_app.exception_handler(RequestValidationError)
async def v2_validation_error(_request: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(str(x) for x in item["loc"]), "message": item["msg"]} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Request validation failed", "fields": fields}})


@v2_app.exception_handler(Exception)
async def v2_unexpected_error(_request: Request, _exc: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "The request could not be completed."}})


def _filters(
    *, search: str | None = None, club_id: str | None = None, competition_id: str | None = None,
    season_id: str | None = None, position: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if search is not None and search.strip():
        normalized_search = normalize_name(search)
        if not normalized_search:
            # Punctuation-only text should not turn into a wildcard or an unfiltered
            # player list.
            clauses.append("0=1")
        else:
            needle = f"%{normalized_search}%"
            # Force the player-leading index on this correlated record lookup. The
            # club match must be on the same season/competition/position scope as the
            # returned player; otherwise, e.g. a past club can leak into another league.
            record_scope: list[str] = []
            record_values: list[Any] = []
            for column, value in (("sx.season_id", season_id), ("sx.competition_id", competition_id), ("sx.club_id", club_id)):
                if value:
                    record_scope.append(f"{column}=?")
                    record_values.append(value)
            if position:
                record_scope.append("instr(','||replace(lower(COALESCE(sx.position_raw,'')),' ','')||',', ','||lower(replace(?,' ',''))||',') > 0")
                record_values.append(position)
            record_scope_sql = " AND " + " AND ".join(record_scope) if record_scope else ""
            clauses.append(
                "(p.normalized_name LIKE ? ESCAPE char(92) "
                "OR EXISTS (SELECT 1 FROM player_aliases pa WHERE pa.player_id=p.id AND pa.normalized_alias LIKE ? ESCAPE char(92)) "
                "OR EXISTS (SELECT 1 FROM player_stat_records sx INDEXED BY ix_stat_player_season "
                "JOIN source_releases sr ON sr.id=sx.source_release_id AND sr.is_current=1 "
                "JOIN data_sources ds ON ds.id=sr.source_id AND ds.active_status='active' AND ds.is_default=1 "
                "JOIN clubs cx ON cx.id=sx.club_id WHERE sx.player_id=p.id "
                "AND (cx.normalized_name LIKE ? ESCAPE char(92) OR EXISTS (SELECT 1 FROM club_aliases ca "
                "WHERE ca.club_id=cx.id AND ca.normalized_alias LIKE ? ESCAPE char(92)))"
                f"{record_scope_sql}))"
            )
            values.extend((needle, needle, needle, needle, *record_values))
    if club_id:
        clauses.append("cs.club_id=?")
        values.append(club_id)
    if competition_id:
        clauses.append("cs.competition_id=?")
        values.append(competition_id)
    if season_id:
        clauses.append("cs.season_id=?")
        values.append(season_id)
    if position:
        clauses.append("instr(','||replace(lower(COALESCE(cs.position_raw,'')),' ','')||',', ','||lower(replace(?,' ',''))||',') > 0")
        values.append(position)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", values


def _summary_query(
    connection: sqlite3.Connection,
    *, search: str | None = None, club_id: str | None = None, competition_id: str | None = None,
    season_id: str | None = None, position: str | None = None, minimum_minutes: int = 0,
    sort_by: str = "name", order: str = "asc", limit: int = 50, offset: int = 0,
    player_id: str | None = None, require_value: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    where, params = _filters(search=search, club_id=club_id, competition_id=competition_id, season_id=season_id, position=position)
    if player_id:
        where = f"{where} AND p.id=?" if where else "WHERE p.id=?"
        params.append(player_id)
    cte = SUMMARY_CTE.format(where=where)
    eligible_clauses: list[str] = []
    eligibility_params: list[Any] = []
    if minimum_minutes > 0:
        eligible_clauses.append("minutes >= ?")
        eligibility_params.append(minimum_minutes)
    if require_value:
        eligible_clauses.append(f"{SORT_SQL[sort_by]} IS NOT NULL")
    eligibility = " WHERE " + " AND ".join(eligible_clauses) if eligible_clauses else ""
    count_sql = cte + " SELECT COUNT(*) FROM aggregated" + eligibility
    total = int(connection.execute(count_sql, [*params, *eligibility_params]).fetchone()[0])
    order_key = SORT_SQL[sort_by]
    direction = "DESC" if order == "desc" else "ASC"
    if require_value:
        ranked = (
            cte
            + f" SELECT * FROM (SELECT aggregated.*, 100.0 * PERCENT_RANK() OVER (ORDER BY {order_key} ASC) AS percentile, COUNT(*) OVER () AS cohort_size FROM aggregated{eligibility}) ranked"
            + f" ORDER BY {order_key} {direction} NULLS LAST, id ASC LIMIT ? OFFSET ?"
        )
        query_params = [*params, *eligibility_params, limit, offset]
    else:
        ranked = cte + f" SELECT * FROM aggregated{eligibility} ORDER BY {order_key} {direction} NULLS LAST, id ASC LIMIT ? OFFSET ?"
        query_params = [*params, *eligibility_params, limit, offset]
    rows = connection.execute(ranked, query_params).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["seasons"] = sorted(item["seasons"].split(",")) if item.get("seasons") else []
        items.append(item)
    return items, total


def _source_context(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """SELECT d.id AS source_id, d.provider_name, d.rights_status, d.license_name,
                  d.attribution_requirements, r.id AS release_id, r.release_name, r.file_name,
                  r.checksum, r.imported_at
           FROM data_sources d LEFT JOIN source_releases r ON r.source_id=d.id AND r.is_current=1
           WHERE d.is_default=1 AND d.active_status='active'"""
    ).fetchone()
    if not row:
        return {"status": "empty", "message": "No active default data source has been imported."}
    return dict(row)


def _page_meta(total: int, limit: int, offset: int) -> dict[str, int]:
    return {"total": total, "limit": limit, "offset": offset}


def _stat_query(
    connection: sqlite3.Connection,
    *, player_id: str | None = None, club_id: str | None = None,
    competition_id: str | None = None, season_id: str | None = None,
    position: str | None = None, minimum_minutes: int = 0,
    limit: int = 50, offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    clauses = ["r.is_current=1", "d.is_default=1", "d.active_status='active'"]
    params: list[Any] = []
    if minimum_minutes > 0:
        clauses.append("s.minutes >= ?")
        params.append(minimum_minutes)
    for column, value in (("s.player_id", player_id), ("s.club_id", club_id), ("s.competition_id", competition_id), ("s.season_id", season_id)):
        if value:
            clauses.append(f"{column}=?")
            params.append(value)
    if position:
        clauses.append("instr(','||replace(lower(COALESCE(s.position_raw,'')),' ','')||',', ','||lower(replace(?,' ',''))||',') > 0")
        params.append(position)
    where = " AND ".join(clauses)
    from_sql = """FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id
        JOIN data_sources d ON d.id=r.source_id JOIN seasons se ON se.id=s.season_id
        LEFT JOIN clubs c ON c.id=s.club_id LEFT JOIN competitions co ON co.id=s.competition_id
        LEFT JOIN players p ON p.id=s.player_id"""
    total = int(connection.execute(f"SELECT COUNT(*) {from_sql} WHERE {where}", params).fetchone()[0])
    rows = connection.execute(
        f"""SELECT s.id, s.player_id, s.club_id, c.canonical_name AS club,
                  s.competition_id, co.canonical_name AS competition, s.season_id, se.label AS season,
                  s.scope, s.position_raw, s.appearances, s.starts, s.minutes, s.goals, s.assists,
                  s.goal_contributions, s.non_penalty_goals, s.non_penalty_goal_contributions,
                  s.penalties_scored, s.penalties_attempted, s.yellow_cards, s.red_cards,
                  s.second_yellow_cards, s.fouls_committed, s.fouls_drawn, s.own_goals,
                  s.goals_against, s.goals_against_per90, s.shots_on_target_against, s.saves, s.save_percent,
                  s.wins, s.draws, s.losses, s.clean_sheets, s.clean_sheet_percent,
                  s.penalties_faced, s.penalties_against, s.penalties_saved, s.penalties_missed,
                  s.shots, s.shots_on_target, s.crosses, s.tackles_won, s.interceptions, s.source_sot_percent,
                  d.id AS source_id, d.provider_name AS source_name, r.release_name AS source_release
           {from_sql} WHERE {where} ORDER BY se.label DESC, co.canonical_name, c.canonical_name, p.canonical_name LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        minutes = item.get("minutes")
        goals = item.get("goals")
        assists = item.get("assists")
        shots = item.get("shots")
        sot = item.get("shots_on_target")
        item["shot_accuracy"] = item.get("source_sot_percent")
        if item["shot_accuracy"] is None and shots is not None and shots > 0 and sot is not None:
            item["shot_accuracy"] = 100.0 * sot / shots
        item["goals_per90"] = 90.0 * goals / minutes if minutes and goals is not None else None
        item["assists_per90"] = 90.0 * assists / minutes if minutes and assists is not None else None
        item["contributions_per90"] = 90.0 * (goals + assists) / minutes if minutes and goals is not None and assists is not None else None
        item["non_penalty_goals_per90"] = 90.0 * item["non_penalty_goals"] / minutes if minutes and item.get("non_penalty_goals") is not None else None
        item["non_penalty_contributions_per90"] = 90.0 * (item["non_penalty_goals"] + assists) / minutes if minutes and item.get("non_penalty_goals") is not None and assists is not None else None
        item["crosses_per90"] = 90.0 * item["crosses"] / minutes if minutes and item.get("crosses") is not None else None
        item["tackles_won_per90"] = 90.0 * item["tackles_won"] / minutes if minutes and item.get("tackles_won") is not None else None
        item["interceptions_per90"] = 90.0 * item["interceptions"] / minutes if minutes and item.get("interceptions") is not None else None
        item["shots_per90"] = 90.0 * shots / minutes if minutes and shots is not None else None
        item["shots_on_target_per90"] = 90.0 * sot / minutes if minutes and sot is not None else None
        item.pop("raw_metrics_json", None)
        result.append(item)
    return result, total


def _scope_sql(
    *, season_id: str | None = None, competition_id: str | None = None,
    club_id: str | None = None, position: str | None = None,
    minimum_minutes: int = 0,
) -> tuple[str, list[Any]]:
    clauses = ["r.is_current=1", "d.is_default=1", "d.active_status='active'"]
    params: list[Any] = []
    if minimum_minutes > 0:
        clauses.append("s.minutes >= ?")
        params.append(minimum_minutes)
    for column, value in (("s.season_id", season_id), ("s.competition_id", competition_id), ("s.club_id", club_id)):
        if value:
            clauses.append(f"{column}=?")
            params.append(value)
    if position:
        clauses.append("instr(','||replace(lower(COALESCE(s.position_raw,'')),' ','')||',', ','||lower(replace(?,' ',''))||',') > 0")
        params.append(position)
    return " AND ".join(clauses), params


def _analytics_frame(
    connection: sqlite3.Connection,
    metrics: list[str],
    *,
    season_id: str | None = None,
    competition_id: str | None = None,
    club_id: str | None = None,
    position: str | None = None,
    minimum_minutes: int = 0,
):
    unsupported = [metric for metric in metrics if metric not in METRIC_SQL]
    if unsupported:
        raise HTTPException(status_code=422, detail=f"Unsupported metrics: {', '.join(unsupported)}")
    where, params = _scope_sql(
        season_id=season_id, competition_id=competition_id, club_id=club_id,
        position=position, minimum_minutes=minimum_minutes,
    )
    return load_metric_frame(connection, metrics, METRIC_SQL, where, params)


def _metric_rows(connection: sqlite3.Connection, metric: str, *, season_id: str | None = None, competition_id: str | None = None, club_id: str | None = None, position: str | None = None, minimum_minutes: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
    if metric not in METRIC_SQL:
        raise HTTPException(status_code=422, detail=f"Unsupported metric: {metric}")
    where, params = _scope_sql(season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    expression = METRIC_SQL[metric]
    rows = connection.execute(
        f"""SELECT p.id AS player_id, p.canonical_name AS player_name, s.position_raw, s.minutes,
                  c.canonical_name AS club, co.canonical_name AS competition, se.label AS season,
                  {expression} AS value
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id
           JOIN data_sources d ON d.id=r.source_id JOIN players p ON p.id=s.player_id
           JOIN seasons se ON se.id=s.season_id LEFT JOIN clubs c ON c.id=s.club_id
           LEFT JOIN competitions co ON co.id=s.competition_id WHERE {where}
           AND ({expression}) IS NOT NULL ORDER BY value DESC, p.canonical_name LIMIT ?""",
        [*params, limit],
    ).fetchall()
    return [dict(row) for row in rows]


def _histogram(
    connection: sqlite3.Connection, metric: str, *, bins: int,
    season_id: str | None = None, competition_id: str | None = None,
    club_id: str | None = None, position: str | None = None,
    minimum_minutes: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
    if metric not in METRIC_SQL:
        raise HTTPException(status_code=422, detail=f"Unsupported metric: {metric}")
    where, params = _scope_sql(season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    expression = METRIC_SQL[metric]
    from_sql = "FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id JOIN data_sources d ON d.id=r.source_id"
    bounds = connection.execute(
        f"SELECT COUNT({expression}) AS n, MIN({expression}) AS min_value, MAX({expression}) AS max_value {from_sql} WHERE {where}",
        params,
    ).fetchone()
    count = int(bounds["n"] or 0)
    if not count:
        return 0, []
    minimum, maximum = float(bounds["min_value"]), float(bounds["max_value"])
    if minimum == maximum:
        return count, [{"from": minimum, "to": maximum, "count": count}]
    width = (maximum - minimum) / bins
    bucket = f"CASE WHEN {expression} >= ? THEN ? ELSE CAST(({expression} - ?) / ? AS INTEGER) END"
    grouped = connection.execute(
        f"""SELECT bucket, COUNT(*) AS count FROM (
               SELECT {bucket} AS bucket {from_sql} WHERE {where} AND ({expression}) IS NOT NULL
           ) GROUP BY bucket""",
        [maximum, bins - 1, minimum, width, *params],
    ).fetchall()
    by_bucket = {int(row["bucket"]): int(row["count"]) for row in grouped}
    return count, [
        {"from": minimum + index * width, "to": maximum if index == bins - 1 else minimum + (index + 1) * width, "count": by_bucket.get(index, 0)}
        for index in range(bins)
    ]


def _pearson_pair(
    connection: sqlite3.Connection, left: str, right: str, *,
    season_id: str | None = None, competition_id: str | None = None,
    club_id: str | None = None, position: str | None = None,
    minimum_minutes: int = 0,
) -> tuple[int, float | None]:
    if left not in METRIC_SQL or right not in METRIC_SQL:
        raise HTTPException(status_code=422, detail="Unsupported correlation metric")
    where, params = _scope_sql(season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    from_sql = "FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id JOIN data_sources d ON d.id=r.source_id"
    x_expr, y_expr = METRIC_SQL[left], METRIC_SQL[right]
    row = connection.execute(
        f"""WITH paired AS (
               SELECT {x_expr} AS x, {y_expr} AS y {from_sql} WHERE {where}
           )
           SELECT COUNT(*) AS n, SUM(x) AS sx, SUM(y) AS sy,
                  SUM(x*x) AS sxx, SUM(y*y) AS syy, SUM(x*y) AS sxy
           FROM paired WHERE x IS NOT NULL AND y IS NOT NULL""",
        params,
    ).fetchone()
    n = int(row["n"] or 0)
    if n < 3:
        return n, None
    covariance = float(row["sxy"]) - float(row["sx"]) * float(row["sy"]) / n
    variance_x = float(row["sxx"]) - float(row["sx"]) ** 2 / n
    variance_y = float(row["syy"]) - float(row["sy"]) ** 2 / n
    if variance_x <= 0 or variance_y <= 0:
        return n, None
    value = covariance / math.sqrt(variance_x * variance_y)
    return n, round(max(-1.0, min(1.0, value)), 4)


def _coverage(connection: sqlite3.Connection) -> dict[str, Any]:
    source = _source_context(connection)
    if not source.get("release_id"):
        return {"source_context": source, "player_count": 0, "record_count": 0, "clubs": [], "competitions": [], "seasons": [], "metrics": []}
    release_id = source["release_id"]
    counts = connection.execute(
        "SELECT COUNT(DISTINCT player_id) players, COUNT(*) records FROM player_stat_records WHERE source_release_id=?",
        (release_id,),
    ).fetchone()
    clubs = [dict(row) for row in connection.execute(
        "SELECT c.id, c.canonical_name AS name, COUNT(DISTINCT s.player_id) AS players, COUNT(s.id) AS records FROM clubs c JOIN player_stat_records s ON s.club_id=c.id WHERE s.source_release_id=? GROUP BY c.id ORDER BY name",
        (release_id,),
    )]
    competitions = [dict(row) for row in connection.execute(
        "SELECT co.id, co.canonical_name AS name, COUNT(DISTINCT s.player_id) AS players, COUNT(s.id) AS records FROM competitions co JOIN player_stat_records s ON s.competition_id=co.id WHERE s.source_release_id=? GROUP BY co.id ORDER BY name",
        (release_id,),
    )]
    seasons = [dict(row) for row in connection.execute(
        "SELECT se.id, se.label, COUNT(DISTINCT s.player_id) AS players, COUNT(s.id) AS records FROM seasons se JOIN player_stat_records s ON s.season_id=se.id WHERE s.source_release_id=? GROUP BY se.id ORDER BY se.label DESC",
        (release_id,),
    )]
    stat_columns = ["goals", "assists", "non_penalty_goals", "non_penalty_goal_contributions", "penalties_scored", "penalties_attempted", "appearances", "starts", "minutes", "shots", "shots_on_target", "source_sot_percent", "crosses", "tackles_won", "interceptions", "yellow_cards", "red_cards", "second_yellow_cards", "fouls_committed", "fouls_drawn", "own_goals", "goals_against", "goals_against_per90", "shots_on_target_against", "saves", "save_percent", "wins", "draws", "losses", "clean_sheets", "clean_sheet_percent", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed"]
    metrics = []
    for column in stat_columns:
        row = connection.execute(
            f"SELECT COUNT(*) total, COUNT({column}) available FROM player_stat_records WHERE source_release_id=?",
            (release_id,),
        ).fetchone()
        metrics.append({"metric": column, "available_records": row["available"], "total_records": row["total"], "status": "available" if row["available"] == row["total"] else "partial" if row["available"] else "unavailable"})
    return {"source_context": source, "player_count": counts["players"], "record_count": counts["records"], "clubs": clubs, "competitions": competitions, "seasons": seasons, "metrics": metrics}


@v2_app.get("/health")
def health(connection: sqlite3.Connection = Depends(_connection)):
    migrations = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    coverage = _coverage(connection)
    return {"status": "healthy", "database": "connected", "schema_version": migrations or 0, "source_loaded": bool(coverage["record_count"]), "records": coverage["record_count"]}


@v2_app.get("/meta")
def metadata(connection: sqlite3.Connection = Depends(_connection)):
    coverage = _coverage(connection)
    return {"product": "PITCHIQ", "api_version": "2.0.0", "capabilities": {"players": bool(coverage["record_count"]), "clubs": bool(coverage["clubs"]), "competitions": bool(coverage["competitions"]), "seasons": bool(coverage["seasons"]), "shooting": ["goals", "shots", "shots_on_target", "shot_accuracy"], "passing": [], "defensive": ["tackles_won", "interceptions"], "goalkeeping": ["goals_against", "shots_on_target_against", "saves", "save_percent", "clean_sheets"], "event_data": False}, "source_context": coverage["source_context"]}


@v2_app.get("/coverage")
def coverage(connection: sqlite3.Connection = Depends(_connection)):
    return _coverage(connection)


@v2_app.get("/sources")
def sources(connection: sqlite3.Connection = Depends(_connection)):
    rows = connection.execute(
        """SELECT d.id, d.provider_name, d.provider_type, d.source_url, d.license_name,
                  d.license_url, d.permitted_use, d.attribution_requirements,
                  d.redistribution_allowed, d.commercial_use_allowed, d.reviewed_at,
                  d.rights_status, d.active_status, d.is_default, r.release_name,
                  r.file_name, r.checksum, r.imported_at
           FROM data_sources d LEFT JOIN source_releases r ON r.source_id=d.id AND r.is_current=1
           WHERE d.active_status='active' ORDER BY d.is_default DESC, d.provider_name"""
    ).fetchall()
    return {"items": [dict(row) for row in rows], "note": "Unknown rights fields remain unknown; this endpoint does not grant redistribution permission."}


@v2_app.get("/identity/summary", response_model=IdentitySummary)
def identity_summary(connection: sqlite3.Connection = Depends(_connection)):
    source_local_keys = int(connection.execute("SELECT COUNT(*) FROM player_source_keys").fetchone()[0])
    verified_external_ids = int(connection.execute("SELECT COUNT(*) FROM player_external_ids WHERE verification_status='verified'").fetchone()[0])
    decisions = {row["status"]: int(row["count"]) for row in connection.execute(
        "SELECT status, COUNT(*) AS count FROM identity_match_decisions GROUP BY status"
    )}
    groups = connection.execute(
        "SELECT normalized_name, COUNT(*) AS candidate_count FROM players GROUP BY normalized_name HAVING COUNT(*) > 1 ORDER BY candidate_count DESC, normalized_name LIMIT 10"
    ).fetchall()
    ambiguity_examples = []
    for group in groups:
        candidates = connection.execute(
            "SELECT id, canonical_name, birth_year, nationality, identity_status FROM players WHERE normalized_name=? ORDER BY birth_year, nationality, id",
            (group["normalized_name"],),
        ).fetchall()
        ambiguity_examples.append({
            "normalized_name": group["normalized_name"],
            "candidate_count": group["candidate_count"],
            "candidates": [dict(candidate) for candidate in candidates],
        })
    ambiguous_groups = int(connection.execute(
        "SELECT COUNT(*) FROM (SELECT normalized_name FROM players GROUP BY normalized_name HAVING COUNT(*) > 1)"
    ).fetchone()[0])
    return {
        "source_local_keys": source_local_keys,
        "verified_external_ids": verified_external_ids,
        "decision_statuses": decisions,
        "ambiguous_name_groups": ambiguous_groups,
        "ambiguity_examples": ambiguity_examples,
        "note": "Identity decisions group records by supplied source-local keys only. Name collisions are candidates for review, never automatic merges. No verified global provider IDs are present.",
    }


@v2_app.get("/identity/review", response_model=list[IdentityReviewItem])
def identity_review(
    status: str = Query("needs_review", pattern="^(automatically_matched|manually_approved|unresolved|rejected|needs_review)$"),
    limit: int = Query(100, ge=1, le=500),
    connection: sqlite3.Connection = Depends(_connection),
):
    rows = connection.execute(
        """SELECT d.id, d.source_id, d.source_player_key, d.candidate_player_id,
                  p.canonical_name, d.status, d.evidence_json, d.method_version, d.reviewer, d.decided_at
           FROM identity_match_decisions d LEFT JOIN players p ON p.id=d.candidate_player_id
           WHERE d.status=? ORDER BY d.decided_at DESC, d.source_player_key LIMIT ?""",
        (status, limit),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json"))
        items.append(item)
    return items


@v2_app.get("/players", response_model=PagePlayers)
def players(
    search: str | None = Query(None, max_length=100), club_id: str | None = Query(None, max_length=80),
    competition_id: str | None = Query(None, max_length=80), season_id: str | None = Query(None, max_length=20),
    position: str | None = Query(None, max_length=30), minimum_minutes: int = Query(0, ge=0, le=100000),
    sort_by: str = Query("name"), order: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    connection: sqlite3.Connection = Depends(_connection),
):
    if sort_by not in SORT_SQL:
        raise HTTPException(status_code=422, detail=f"sort_by must be one of: {', '.join(sorted(SORT_SQL))}")
    items, total = _summary_query(connection, search=search, club_id=club_id, competition_id=competition_id, season_id=season_id, position=position, minimum_minutes=minimum_minutes, sort_by=sort_by, order=order, limit=limit, offset=offset)
    return {"items": items, "meta": _page_meta(total, limit, offset), "source_context": _source_context(connection)}


@v2_app.get("/players/{player_id}", response_model=PlayerDetail)
def player_detail(player_id: str, connection: sqlite3.Connection = Depends(_connection)):
    players, total = _summary_query(connection, player_id=player_id, limit=1)
    if not total:
        raise HTTPException(status_code=404, detail="Player not found")
    profile = connection.execute(
        "SELECT id, date_of_birth, birth_year, preferred_foot, height_cm FROM players WHERE id=?", (player_id,)
    ).fetchone()
    aliases = [row[0] for row in connection.execute("SELECT DISTINCT alias FROM player_aliases WHERE player_id=? ORDER BY alias", (player_id,))]
    return {**players[0], **dict(profile), "aliases": aliases, "source_context": _source_context(connection)}


@v2_app.get("/players/{player_id}/seasons")
def player_seasons(
    player_id: str, season_id: str | None = Query(None, max_length=20), competition_id: str | None = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    connection: sqlite3.Connection = Depends(_connection),
):
    if not connection.execute("SELECT 1 FROM players WHERE id=?", (player_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    items, total = _stat_query(connection, player_id=player_id, season_id=season_id, competition_id=competition_id, limit=limit, offset=offset)
    return {"items": items, "meta": _page_meta(total, limit, offset), "source_context": _source_context(connection)}


@v2_app.get("/players/{player_id}/career")
def player_career(player_id: str, connection: sqlite3.Connection = Depends(_connection)):
    if not connection.execute("SELECT 1 FROM players WHERE id=?", (player_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    rows = connection.execute(
        """SELECT se.id AS season_id, se.label AS season, COUNT(*) AS records,
                  COUNT(DISTINCT s.club_id) AS clubs, COUNT(DISTINCT s.competition_id) AS competitions,
                  SUM(s.appearances) AS appearances, SUM(s.starts) AS starts, SUM(s.minutes) AS minutes,
                  SUM(s.goals) AS goals, SUM(s.assists) AS assists
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1
           JOIN seasons se ON se.id=s.season_id WHERE s.player_id=? GROUP BY se.id ORDER BY se.label DESC""",
        (player_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "source_context": _source_context(connection)}


@v2_app.get("/players/{player_id}/clubs")
def player_clubs(player_id: str, connection: sqlite3.Connection = Depends(_connection)):
    if not connection.execute("SELECT 1 FROM players WHERE id=?", (player_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    rows = connection.execute(
        """SELECT DISTINCT c.id AS club_id, c.canonical_name AS club, se.id AS season_id, se.label AS season,
                  co.id AS competition_id, co.canonical_name AS competition
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1
           JOIN clubs c ON c.id=s.club_id JOIN competitions co ON co.id=s.competition_id
           JOIN seasons se ON se.id=s.season_id WHERE s.player_id=? ORDER BY se.label DESC, c.canonical_name, co.canonical_name""",
        (player_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "source_context": _source_context(connection)}


@v2_app.get("/players/{player_id}/competitions")
def player_competitions(player_id: str, connection: sqlite3.Connection = Depends(_connection)):
    if not connection.execute("SELECT 1 FROM players WHERE id=?", (player_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    rows = connection.execute(
        """SELECT DISTINCT co.id AS competition_id, co.canonical_name AS competition, se.id AS season_id,
                  se.label AS season, c.id AS club_id, c.canonical_name AS club
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1
           JOIN competitions co ON co.id=s.competition_id JOIN seasons se ON se.id=s.season_id
           LEFT JOIN clubs c ON c.id=s.club_id WHERE s.player_id=? ORDER BY se.label DESC, co.canonical_name""",
        (player_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "source_context": _source_context(connection)}


@v2_app.get("/clubs", response_model=PageClubs)
def clubs(
    search: str | None = Query(None, max_length=100), competition_id: str | None = Query(None, max_length=80),
    season_id: str | None = Query(None, max_length=20), limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0), connection: sqlite3.Connection = Depends(_connection),
):
    clauses = ["r.is_current=1", "d.is_default=1", "d.active_status='active'"]
    params: list[Any] = []
    if search:
        clauses.append("lower(c.normalized_name) LIKE ?")
        params.append(f"%{search.casefold()}%")
    if competition_id:
        clauses.append("s.competition_id=?")
        params.append(competition_id)
    if season_id:
        clauses.append("s.season_id=?")
        params.append(season_id)
    where = " AND ".join(clauses)
    base = "FROM clubs c JOIN player_stat_records s ON s.club_id=c.id JOIN source_releases r ON r.id=s.source_release_id JOIN data_sources d ON d.id=r.source_id"
    total = connection.execute(f"SELECT COUNT(DISTINCT c.id) {base} WHERE {where}", params).fetchone()[0]
    rows = connection.execute(
        f"""SELECT c.id, c.canonical_name, COUNT(DISTINCT s.player_id) AS players, COUNT(s.id) AS records,
                   SUM(s.goals) AS player_record_goals, SUM(s.assists) AS player_record_assists,
                   SUM(s.minutes) AS player_record_minutes,
                   GROUP_CONCAT(DISTINCT co.canonical_name) AS competitions,
                   GROUP_CONCAT(DISTINCT se.label) AS seasons
            {base} JOIN competitions co ON co.id=s.competition_id JOIN seasons se ON se.id=s.season_id
            WHERE {where} GROUP BY c.id ORDER BY player_record_goals DESC, c.canonical_name LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["competitions"] = item["competitions"].split(",") if item["competitions"] else []
        item["seasons"] = item["seasons"].split(",") if item["seasons"] else []
        item["methodology"] = "Sums of supplied player records; not official club totals."
        items.append(item)
    return {"items": items, "meta": _page_meta(total, limit, offset)}


@v2_app.get("/clubs/{club_id}")
def club_detail(club_id: str, connection: sqlite3.Connection = Depends(_connection)):
    row = connection.execute(
        "SELECT id, canonical_name, country FROM clubs WHERE id=?", (club_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Club not found")
    coverage = connection.execute(
        """SELECT COUNT(DISTINCT s.player_id) players, COUNT(s.id) records,
                  SUM(s.goals) player_record_goals, SUM(s.assists) player_record_assists,
                  GROUP_CONCAT(DISTINCT co.canonical_name) competitions,
                  GROUP_CONCAT(DISTINCT se.label) seasons
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1
           JOIN competitions co ON co.id=s.competition_id JOIN seasons se ON se.id=s.season_id WHERE s.club_id=?""",
        (club_id,),
    ).fetchone()
    return {**dict(row), **dict(coverage), "methodology": "Player-record aggregates only; not official club totals.", "source_context": _source_context(connection)}


@v2_app.get("/clubs/{club_id}/players", response_model=PagePlayers)
def club_players(club_id: str, season_id: str | None = Query(None, max_length=20), competition_id: str | None = Query(None, max_length=80), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), connection: sqlite3.Connection = Depends(_connection)):
    if not connection.execute("SELECT 1 FROM clubs WHERE id=?", (club_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Club not found")
    items, total = _summary_query(connection, club_id=club_id, season_id=season_id, competition_id=competition_id, limit=limit, offset=offset)
    return {"items": items, "meta": _page_meta(total, limit, offset), "source_context": _source_context(connection)}


@v2_app.get("/competitions", response_model=PageCompetitions)
def competitions(
    search: str | None = Query(None, max_length=100), season_id: str | None = Query(None, max_length=20),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    connection: sqlite3.Connection = Depends(_connection),
):
    clauses = ["r.is_current=1", "d.is_default=1", "d.active_status='active'"]
    params: list[Any] = []
    if search:
        clauses.append("lower(co.normalized_name) LIKE ?")
        params.append(f"%{search.casefold()}%")
    if season_id:
        clauses.append("s.season_id=?")
        params.append(season_id)
    where = " AND ".join(clauses)
    base = "FROM competitions co JOIN player_stat_records s ON s.competition_id=co.id JOIN source_releases r ON r.id=s.source_release_id JOIN data_sources d ON d.id=r.source_id"
    total = connection.execute(f"SELECT COUNT(DISTINCT co.id) {base} WHERE {where}", params).fetchone()[0]
    rows = connection.execute(
        f"""SELECT co.id, co.canonical_name, co.country, co.competition_type,
                   COUNT(DISTINCT s.player_id) AS players, COUNT(DISTINCT s.club_id) AS clubs,
                   COUNT(s.id) AS records, SUM(s.goals) AS player_record_goals,
                   SUM(s.assists) AS player_record_assists, GROUP_CONCAT(DISTINCT se.label) seasons
            {base} JOIN seasons se ON se.id=s.season_id WHERE {where}
            GROUP BY co.id ORDER BY co.canonical_name LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["seasons"] = item["seasons"].split(",") if item["seasons"] else []
        item["methodology"] = "Descriptive sums of supplied player records; not official competition tables."
        items.append(item)
    return {"items": items, "meta": _page_meta(total, limit, offset)}


@v2_app.get("/competitions/{competition_id}")
def competition_detail(competition_id: str, connection: sqlite3.Connection = Depends(_connection)):
    row = connection.execute("SELECT id, canonical_name, country, competition_type FROM competitions WHERE id=?", (competition_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Competition not found")
    editions = connection.execute(
        """SELECT DISTINCT se.id, se.label, COUNT(DISTINCT s.player_id) players, COUNT(DISTINCT s.club_id) clubs, COUNT(s.id) records
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1 JOIN seasons se ON se.id=s.season_id
           WHERE s.competition_id=? GROUP BY se.id ORDER BY se.label DESC""",
        (competition_id,),
    ).fetchall()
    return {**dict(row), "seasons": [dict(item) for item in editions], "methodology": "Available player-record coverage; not a complete official competition table.", "source_context": _source_context(connection)}


@v2_app.get("/competitions/{competition_id}/players", response_model=PagePlayers)
def competition_players(competition_id: str, season_id: str | None = Query(None, max_length=20), position: str | None = Query(None, max_length=30), minimum_minutes: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), connection: sqlite3.Connection = Depends(_connection)):
    if not connection.execute("SELECT 1 FROM competitions WHERE id=?", (competition_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Competition not found")
    items, total = _summary_query(connection, competition_id=competition_id, season_id=season_id, position=position, minimum_minutes=minimum_minutes, limit=limit, offset=offset)
    return {"items": items, "meta": _page_meta(total, limit, offset), "source_context": _source_context(connection)}


@v2_app.get("/seasons")
def seasons(connection: sqlite3.Connection = Depends(_connection)):
    rows = connection.execute(
        """SELECT se.id, se.label, se.start_date, se.end_date, se.season_type,
                  COUNT(DISTINCT s.player_id) players, COUNT(DISTINCT s.club_id) clubs,
                  COUNT(DISTINCT s.competition_id) competitions, COUNT(s.id) records
           FROM seasons se JOIN player_stat_records s ON s.season_id=se.id
           JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1
           GROUP BY se.id ORDER BY se.label DESC"""
    ).fetchall()
    return {"items": [dict(row) for row in rows], "source_context": _source_context(connection)}


@v2_app.get("/seasons/{season_id}")
def season_detail(season_id: str, connection: sqlite3.Connection = Depends(_connection)):
    row = connection.execute("SELECT * FROM seasons WHERE id=?", (season_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Season not found")
    coverage = connection.execute(
        """SELECT COUNT(DISTINCT s.player_id) players, COUNT(DISTINCT s.club_id) clubs,
                  COUNT(DISTINCT s.competition_id) competitions, COUNT(s.id) records
           FROM player_stat_records s JOIN source_releases r ON r.id=s.source_release_id AND r.is_current=1
           JOIN data_sources d ON d.id=r.source_id AND d.is_default=1 WHERE s.season_id=?""",
        (season_id,),
    ).fetchone()
    return {**dict(row), **dict(coverage), "source_context": _source_context(connection)}


@v2_app.post("/compare/players")
def compare_players(request: ComparePlayersRequest, connection: sqlite3.Connection = Depends(_connection)):
    available = []
    for player_id in request.player_ids:
        items, total = _summary_query(connection, player_id=player_id, season_id=request.season_id, competition_id=request.competition_id, minimum_minutes=request.minimum_minutes, limit=1)
        if not total:
            raise HTTPException(status_code=404, detail=f"No player record found for requested player {player_id} in the selected scope")
        item = items[0]
        records, _ = _stat_query(connection, player_id=player_id, season_id=request.season_id, competition_id=request.competition_id, limit=200)
        item["records"] = records
        available.append(item)
    return {
        "items": available,
        "scope": {"season_id": request.season_id, "competition_id": request.competition_id, "minimum_minutes": request.minimum_minutes},
        "methodology": "Canonical player aggregates over the selected source records. Cross-competition totals are not competition-adjusted; per-90 rates normalize minutes only.",
        "source_context": _source_context(connection),
    }


@v2_app.get("/leaderboards")
def leaderboards(
    metric: str = Query("goals_per90", max_length=40), season_id: str | None = Query(None, max_length=20),
    competition_id: str | None = Query(None, max_length=80), position: str | None = Query(None, max_length=30),
    minimum_minutes: int = Query(450, ge=0, le=100000), limit: int = Query(20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(_connection),
):
    if metric not in SORT_SQL or metric == "name":
        raise HTTPException(status_code=422, detail="Unsupported leaderboard metric")
    if not _source_context(connection).get("release_id"):
        return {"metric": metric, "unit": METRIC_UNITS[metric], "minimum_minutes": minimum_minutes, "eligible_count": 0, "items": []}
    items, total = _summary_query(connection, season_id=season_id, competition_id=competition_id, position=position, minimum_minutes=minimum_minutes, sort_by=metric if metric in SORT_SQL else "name", order="desc", limit=limit, require_value=True)
    return {"metric": metric, "unit": METRIC_UNITS[metric], "minimum_minutes": minimum_minutes, "eligible_count": total, "percentile_method": "SQLite PERCENT_RANK over eligible canonical players ordered ascending by metric; tied values share the first rank. Percentiles are cohort-relative, not universal ratings.", "items": items, "methodology": "Ranks eligible canonical players in the selected scope; per-90 normalizes minutes, not competition or role. Percentile cohort includes only players with a non-null metric who meet the active minimum-minutes filter."}


@v2_app.get("/analytics/overview")
def analytics_overview(connection: sqlite3.Connection = Depends(_connection)):
    coverage = _coverage(connection)
    if not coverage["record_count"]:
        return {**coverage, "goals": 0, "assists": 0, "minutes": 0, "methodology": "No imported records."}
    release_id = coverage["source_context"]["release_id"]
    sums = connection.execute(
        "SELECT SUM(goals) goals, SUM(assists) assists, SUM(minutes) minutes, SUM(shots) shots FROM player_stat_records WHERE source_release_id=?",
        (release_id,),
    ).fetchone()
    return {**coverage, **dict(sums), "methodology": "Totals describe supplied player records. They are not independently verified official team or competition totals."}


@v2_app.get("/analytics/positions")
def position_analytics(
    season_id: str | None = Query(None, max_length=20), competition_id: str | None = Query(None, max_length=80),
    club_id: str | None = Query(None, max_length=80), connection: sqlite3.Connection = Depends(_connection),
):
    frame = _analytics_frame(connection, ["goals", "assists", "minutes"], season_id=season_id, competition_id=competition_id, club_id=club_id)
    items: list[dict[str, Any]] = []
    for label, group in frame.groupby("position", dropna=False, sort=True):
        items.append({
            "listed_position": str(label), "players": int(group["player_id"].nunique()), "records": int(len(group)),
            "goals": float(group["goals"].sum(min_count=1)) if group["goals"].notna().any() else None,
            "assists": float(group["assists"].sum(min_count=1)) if group["assists"].notna().any() else None,
            "average_minutes": float(group["minutes"].mean()) if group["minutes"].notna().any() else None,
        })
    items.sort(key=lambda item: (-item["players"], item["listed_position"]))
    return {"items": items, "methodology": "Pandas groups records by the first-listed source position. Multi-position source strings remain on each record; this is not an exclusive role classification. Counts distinguish unique players from source records."}


@v2_app.get("/analytics/competitions")
def competition_analytics(season_id: str | None = Query(None, max_length=20), connection: sqlite3.Connection = Depends(_connection)):
    frame = _analytics_frame(connection, ["goals", "assists", "shots", "shots_on_target", "minutes"], season_id=season_id)
    frame = frame.loc[frame["competition_id"].notna()]
    groups = frame.groupby(["competition_id", "competition", "season_id", "season"], dropna=False, sort=True)
    items: list[dict[str, Any]] = []
    for (competition_key, competition, season_key, season), group in groups:
        players = int(group["player_id"].nunique())
        goals = float(group["goals"].sum(min_count=1)) if group["goals"].notna().any() else None
        assists = float(group["assists"].sum(min_count=1)) if group["assists"].notna().any() else None
        items.append({
            "competition_id": competition_key, "competition": competition, "season_id": season_key, "season": season,
            "players": players, "clubs": int(group["club_id"].nunique()), "records": int(len(group)),
            "goals": goals, "assists": assists,
            "shots": float(group["shots"].sum(min_count=1)) if group["shots"].notna().any() else None,
            "shots_on_target": float(group["shots_on_target"].sum(min_count=1)) if group["shots_on_target"].notna().any() else None,
            "average_minutes": float(group["minutes"].mean()) if group["minutes"].notna().any() else None,
            "goals_per_player": goals / players if goals is not None and players else None,
            "assists_per_player": assists / players if assists is not None and players else None,
        })
    return {"items": items, "methodology": "Pandas groupby over supplied player-stat records. Player count is distinct source-local players; record sums and averages describe the selected dataset, not official standings or complete competition totals. Goals/assists per player divide record sums by distinct players."}


@v2_app.get("/analytics/distribution")
def distribution(
    metric: str = Query(..., max_length=40), season_id: str | None = Query(None, max_length=20),
    competition_id: str | None = Query(None, max_length=80), club_id: str | None = Query(None, max_length=80),
    position: str | None = Query(None, max_length=30), minimum_minutes: int = Query(0, ge=0, le=100000),
    bins: int = Query(10, ge=2, le=30), connection: sqlite3.Connection = Depends(_connection),
):
    frame = _analytics_frame(connection, [metric], season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    bins_out, summary = pandas_histogram(frame[metric], bins=bins)
    count = int(summary["count"])
    return {
        "metric": metric, "unit": METRIC_UNITS[metric], "n": count, "bins": bins_out,
        "summary": summary,
        "methodology": "NumPy histogram over Pandas-filtered observed non-null values. Missing values are excluded rather than treated as zero. Summary percentiles use linear interpolation; standard deviation and variance use the sample convention (ddof=1).",
    }


@v2_app.get("/analytics/correlation")
def correlation(
    metrics: str = Query("goals,assists,minutes,shots,shots_on_target", max_length=250),
    season_id: str | None = Query(None, max_length=20), competition_id: str | None = Query(None, max_length=80),
    club_id: str | None = Query(None, max_length=80), position: str | None = Query(None, max_length=30),
    minimum_minutes: int = Query(0, ge=0, le=100000), method: Literal["pearson", "spearman"] = Query("pearson"),
    connection: sqlite3.Connection = Depends(_connection),
):
    labels = [item.strip() for item in metrics.split(",") if item.strip()]
    if not 2 <= len(labels) <= 8 or len(labels) != len(set(labels)) or any(label not in METRIC_SQL for label in labels):
        raise HTTPException(status_code=422, detail="Select between 2 and 8 unique supported metrics")
    frame = _analytics_frame(connection, labels, season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    return correlation_matrix(frame, labels, method)


@v2_app.post("/analytics/descriptive")
def descriptive_analytics(request: DescriptiveRequest, connection: sqlite3.Connection = Depends(_connection)):
    frame = _analytics_frame(connection, request.metrics, **request.model_dump(exclude={"metrics", "group_by"}))
    return {
        "metrics": request.metrics, "record_count": int(len(frame)),
        "summary": summarize_frame(frame, request.metrics),
        "groups": grouped_summaries(frame, request.metrics, request.group_by) if request.group_by else [],
        "group_by": request.group_by,
        "methodology": "Pandas summaries and NumPy calculations over filtered source records. Quartiles use linear interpolation; standard deviation and variance use the sample convention (ddof=1) and are unavailable for fewer than two observations. Missing values are excluded metric by metric, never filled with zero.",
    }


@v2_app.get("/analytics/outliers")
def outlier_analytics(
    metric: str = Query(..., max_length=40), season_id: str | None = Query(None, max_length=20),
    competition_id: str | None = Query(None, max_length=80), club_id: str | None = Query(None, max_length=80),
    position: str | None = Query(None, max_length=30), minimum_minutes: int = Query(0, ge=0, le=100000),
    multiplier: float = Query(1.5, ge=0.5, le=3.0), limit: int = Query(100, ge=1, le=500),
    connection: sqlite3.Connection = Depends(_connection),
):
    frame = _analytics_frame(connection, [metric], season_id=season_id, competition_id=competition_id, club_id=club_id, position=position, minimum_minutes=minimum_minutes)
    return iqr_outliers(frame, metric, multiplier=multiplier, limit=limit)


@v2_app.get("/analytics/quality")
def analytics_quality(connection: sqlite3.Connection = Depends(_connection)):
    frame, declared = load_quality_frame(connection)
    return quality_report(frame, declared)


@v2_app.get("/analytics/quality/visualization")
def analytics_quality_visualization(connection: sqlite3.Connection = Depends(_connection)):
    frame, _ = load_quality_frame(connection)
    png = render_missingness_png(frame)
    return StreamingResponse(io.BytesIO(png), media_type="image/png", headers={"Content-Disposition": 'attachment; filename="pitchiq_v2_missingness.png"', "Cache-Control": "no-store"})


@v2_app.post("/analytics/visualizations")
def analytics_visualization(request: VisualizationRequest, connection: sqlite3.Connection = Depends(_connection)):
    metric_count = len(request.metrics)
    if request.visualization == "scatter" and metric_count != 2:
        raise HTTPException(status_code=422, detail="scatter requires exactly two metrics")
    if request.visualization == "correlation_heatmap" and not 2 <= metric_count <= 8:
        raise HTTPException(status_code=422, detail="correlation_heatmap requires between two and eight metrics")
    if request.visualization not in {"scatter", "correlation_heatmap"} and metric_count != 1:
        raise HTTPException(status_code=422, detail=f"{request.visualization} requires exactly one metric")
    if request.group_by and request.group_by not in {"position", "competition", "club", "season"}:
        raise HTTPException(status_code=422, detail="Unsupported visualization grouping field")
    frame = _analytics_frame(connection, request.metrics, **request.model_dump(exclude={"metrics", "visualization", "group_by", "method"}))
    try:
        png = render_png(frame, kind=request.visualization, metrics=request.metrics, group_by=request.group_by, method=request.method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = f"pitchiq_{request.visualization}_{request.metrics[0]}.png"
    return StreamingResponse(io.BytesIO(png), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@v2_app.get("/data-lab/metrics")
def data_lab_metrics(connection: sqlite3.Connection = Depends(_connection)):
    rows = connection.execute("SELECT * FROM metric_definitions ORDER BY availability_status, display_name").fetchall()
    return {"items": [dict(row) for row in rows], "available_metrics": sorted(METRIC_SQL), "unsupported": ["xg", "xa", "passes_completed", "passes_attempted", "blocks", "clearances", "aerial_duels"]}


@v2_app.post("/data-lab/query")
def data_lab_query(request: DataLabQuery, connection: sqlite3.Connection = Depends(_connection)):
    unsupported = [metric for metric in request.metrics if metric not in METRIC_SQL]
    if unsupported:
        raise HTTPException(status_code=422, detail=f"Unsupported metrics: {', '.join(unsupported)}")
    if request.visualization in {"scatter", "correlation"} and len(request.metrics) != 2:
        raise HTTPException(status_code=422, detail=f"{request.visualization} requires exactly two metrics")
    if request.visualization == "histogram" and len(request.metrics) != 1:
        raise HTTPException(status_code=422, detail="histogram requires exactly one metric")
    scope = {"season_id": request.season_id, "competition_id": request.competition_id, "club_id": request.club_id, "position": request.position, "minimum_minutes": request.minimum_minutes}
    frame = _analytics_frame(connection, request.metrics, **scope)
    summary = summarize_frame(frame, request.metrics)
    shared = {"visualization": request.visualization, "metrics": request.metrics, "summary": summary, "units": [METRIC_UNITS[key] for key in request.metrics], "source_context": _source_context(connection)}
    if request.visualization == "histogram":
        bins, stats = pandas_histogram(frame[request.metrics[0]], bins=10)
        return {**shared, "n": stats["count"], "items": bins}
    if request.visualization == "correlation":
        result = correlation_matrix(frame, request.metrics, request.method)
        value = result["matrix"][0][1]
        n = result["pairwise_n"][0][1]
        unit = "Pearson r" if request.method == "pearson" else "Spearman rho"
        return {**shared, "value": value, "n": n, "unit": unit, "note": result["note"], "interpretation": interpret_correlation(value)}
    valid_mask = frame[request.metrics].notna().all(axis=1)
    valid = frame.loc[valid_mask].head(request.limit)
    total = int(valid_mask.sum())
    if request.visualization == "scatter":
        items = [{"player_id": row["player_id"], "player": row["player"], "club": row["club"], "competition": row["competition"], "x": float(row[request.metrics[0]]), "y": float(row[request.metrics[1]])} for row in valid.to_dict(orient="records")]
        return {**shared, "total": total, "items": items}
    items = [{"player_id": row["player_id"], "player": row["player"], "club": row["club"], "competition": row["competition"], "season": row["season"], "values": {metric: float(row[metric]) for metric in request.metrics}} for row in valid.to_dict(orient="records")]
    return {**shared, "total": total, "items": items}


def _csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@v2_app.get("/exports/players")
def export_players(
    search: str | None = Query(None, max_length=100), club_id: str | None = Query(None, max_length=80),
    competition_id: str | None = Query(None, max_length=80), season_id: str | None = Query(None, max_length=20),
    position: str | None = Query(None, max_length=30), minimum_minutes: int = Query(0, ge=0, le=100000),
    limit: int = Query(10000, ge=1, le=100000), connection: sqlite3.Connection = Depends(_connection),
):
    source_context = _source_context(connection)
    headers = ["player_id", "player", "identity_status", "nationality", "position", "record_count", "club_count", "competition_count", "seasons", "appearances", "starts", "minutes", "goals", "assists", "non_penalty_goals", "non_penalty_goal_contributions", "shots", "shots_on_target", "yellow_cards", "red_cards", "fouls_committed", "fouls_drawn", "crosses", "tackles_won", "interceptions", "goals_against", "goals_against_per90", "shots_on_target_against", "saves", "save_percent", "wins", "draws", "losses", "clean_sheets", "clean_sheet_percent", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed", "goals_per90", "assists_per90", "contributions_per90", "non_penalty_goals_per90", "non_penalty_contributions_per90", "shots_per90", "shots_on_target_per90", "crosses_per90", "tackles_won_per90", "interceptions_per90", "goals_per_appearance", "assists_per_appearance", "goals_per_shot", "shots_per_goal", "shot_accuracy", "source_name", "source_release", "source_rights_status"]
    def stream() -> Iterator[str]:
        header = io.StringIO(newline="")
        csv.writer(header).writerow(headers)
        yield header.getvalue()
        stream_connection = connect()
        try:
            for page_offset in range(0, limit, 500):
                items, _ = _summary_query(stream_connection, search=search, club_id=club_id, competition_id=competition_id, season_id=season_id, position=position, minimum_minutes=minimum_minutes, limit=min(500, limit - page_offset), offset=page_offset, sort_by="name")
                if not items:
                    break
                for item in items:
                    row = [_csv_cell(item.get(key)) for key in ["id", "canonical_name", "identity_status", "nationality", "primary_position", "record_count", "club_count", "competition_count"]]
                    row.extend([_csv_cell(";".join(item.get("seasons", [])))])
                    row.extend(_csv_cell(item.get(key)) for key in ["appearances", "starts", "minutes", "goals", "assists", "non_penalty_goals", "non_penalty_goal_contributions", "shots", "shots_on_target", "yellow_cards", "red_cards", "fouls_committed", "fouls_drawn", "crosses", "tackles_won", "interceptions", "goals_against", "goals_against_per90", "shots_on_target_against", "saves", "save_percent", "wins", "draws", "losses", "clean_sheets", "clean_sheet_percent", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed", "goals_per90", "assists_per90", "contributions_per90", "non_penalty_goals_per90", "non_penalty_contributions_per90", "shots_per90", "shots_on_target_per90", "crosses_per90", "tackles_won_per90", "interceptions_per90", "goals_per_appearance", "assists_per_appearance", "goals_per_shot", "shots_per_goal", "shot_accuracy"])
                    row.extend(_csv_cell(source_context.get(key)) for key in ["provider_name", "release_name", "rights_status"])
                    output = io.StringIO(newline="")
                    csv.writer(output).writerow(row)
                    yield output.getvalue()
        finally:
            stream_connection.close()
    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=pitchiq_v2_players.csv", "X-Content-Type-Options": "nosniff"})


@v2_app.post("/exports/comparison")
def export_comparison(request: ComparePlayersRequest, connection: sqlite3.Connection = Depends(_connection)):
    compared = compare_players(request, connection)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["player_id", "player", "position", "records", "clubs", "competitions", "seasons", "minutes", "appearances", "starts", "goals", "non_penalty_goals", "non_penalty_goal_contributions", "assists", "shots", "shots_on_target", "yellow_cards", "red_cards", "fouls_committed", "crosses", "tackles_won", "interceptions", "goals_against", "goals_against_per90", "shots_on_target_against", "saves", "save_percent", "wins", "draws", "losses", "clean_sheets", "clean_sheet_percent", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed", "goals_per90", "assists_per90", "contributions_per90", "non_penalty_goals_per90", "non_penalty_contributions_per90", "shots_per90", "shots_on_target_per90", "tackles_won_per90", "interceptions_per90", "goals_per_appearance", "assists_per_appearance", "goals_per_shot", "shots_per_goal", "shot_accuracy", "season_scope", "competition_scope", "minimum_minutes", "source_name", "source_release", "source_rights_status"])
    for item in compared["items"]:
        writer.writerow([_csv_cell(item.get(key)) for key in ["id", "canonical_name", "primary_position", "record_count", "club_count", "competition_count"]] + [_csv_cell(";".join(item.get("seasons", [])))] + [_csv_cell(item.get(key)) for key in ["minutes", "appearances", "starts", "goals", "non_penalty_goals", "non_penalty_goal_contributions", "assists", "shots", "shots_on_target", "yellow_cards", "red_cards", "fouls_committed", "crosses", "tackles_won", "interceptions", "goals_against", "goals_against_per90", "shots_on_target_against", "saves", "save_percent", "wins", "draws", "losses", "clean_sheets", "clean_sheet_percent", "penalties_faced", "penalties_against", "penalties_saved", "penalties_missed", "goals_per90", "assists_per90", "contributions_per90", "non_penalty_goals_per90", "non_penalty_contributions_per90", "shots_per90", "shots_on_target_per90", "tackles_won_per90", "interceptions_per90", "goals_per_appearance", "assists_per_appearance", "goals_per_shot", "shots_per_goal", "shot_accuracy"]] + [_csv_cell(request.season_id), _csv_cell(request.competition_id), request.minimum_minutes, _csv_cell(compared["source_context"].get("provider_name")), _csv_cell(compared["source_context"].get("release_name")), _csv_cell(compared["source_context"].get("rights_status"))])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=pitchiq_v2_comparison.csv", "X-Content-Type-Options": "nosniff"})


@v2_app.get("/exports/leaderboards")
def export_leaderboards(metric: str = Query("goals_per90", max_length=40), season_id: str | None = Query(None, max_length=20), competition_id: str | None = Query(None, max_length=80), minimum_minutes: int = Query(450, ge=0, le=100000), limit: int = Query(100, ge=1, le=1000), connection: sqlite3.Connection = Depends(_connection)):
    if metric not in SORT_SQL or metric == "name":
        raise HTTPException(status_code=422, detail="Unsupported leaderboard metric")
    items, _ = _summary_query(connection, season_id=season_id, competition_id=competition_id, minimum_minutes=minimum_minutes, sort_by=metric, order="desc", limit=limit, require_value=True)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    source_context = _source_context(connection)
    writer.writerow(["rank", "player_id", "player", "position", "minutes", metric, "unit", "percentile", "cohort_size", "season_scope", "competition_scope", "minimum_minutes", "source_name", "source_release", "source_rights_status"])
    for rank, item in enumerate(items, start=1):
        writer.writerow([rank, item["id"], _csv_cell(item["canonical_name"]), _csv_cell(item["primary_position"]), item["minutes"], item.get(metric), METRIC_UNITS[metric], item.get("percentile"), item.get("cohort_size"), _csv_cell(season_id), _csv_cell(competition_id), minimum_minutes, _csv_cell(source_context.get("provider_name")), _csv_cell(source_context.get("release_name")), _csv_cell(source_context.get("rights_status"))])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=pitchiq_v2_leaderboard.csv", "X-Content-Type-Options": "nosniff"})


@v2_app.post("/exports/data-lab")
def export_data_lab(request: DataLabQuery, connection: sqlite3.Connection = Depends(_connection)):
    result = data_lab_query(request, connection)
    visualization = result["visualization"]
    source = result.get("source_context", _source_context(connection))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    metric_units = [METRIC_UNITS[key] for key in request.metrics]
    metadata = [_csv_cell(source.get("provider_name")), _csv_cell(source.get("release_name")), _csv_cell(source.get("rights_status")), _csv_cell(request.season_id), _csv_cell(request.competition_id), _csv_cell(request.club_id), _csv_cell(request.position), request.minimum_minutes]
    if visualization == "histogram":
        writer.writerow(["metric", "unit", "bin_from", "bin_to", "record_count", "source_name", "source_release", "source_rights_status", "season_scope", "competition_scope", "club_scope", "position_scope", "minimum_minutes", "observed_records", "returned_bins"])
        for item in result["items"]:
            writer.writerow([request.metrics[0], metric_units[0], item["from"], item["to"], item["count"], *metadata, result["n"], len(result["items"])])
    elif visualization == "correlation":
        writer.writerow(["metric_x", "unit_x", "metric_y", "unit_y", "pearson_r", "paired_records", "interpretation", "source_name", "source_release", "source_rights_status", "season_scope", "competition_scope", "club_scope", "position_scope", "minimum_minutes"])
        writer.writerow([request.metrics[0], metric_units[0], request.metrics[1], metric_units[1], result["value"], result["n"], result["note"], *metadata])
    elif visualization == "scatter":
        writer.writerow(["player_id", "player", "club", "competition", "x", "x_unit", "y", "y_unit", "source_name", "source_release", "source_rights_status", "season_scope", "competition_scope", "club_scope", "position_scope", "minimum_minutes", "matching_records_total", "records_exported"])
        for item in result["items"]:
            writer.writerow([_csv_cell(item.get(key)) for key in ["player_id", "player", "club", "competition"]] + [item["x"], metric_units[0], item["y"], metric_units[1], *metadata, result["total"], len(result["items"])])
    else:
        writer.writerow(["player_id", "player", "club", "competition", "season", *request.metrics, *[f"unit_{key}" for key in request.metrics], "source_name", "source_release", "source_rights_status", "season_scope", "competition_scope", "club_scope", "position_scope", "minimum_minutes", "matching_records_total", "records_exported"])
        for item in result["items"]:
            writer.writerow([_csv_cell(item.get(key)) for key in ["player_id", "player", "club", "competition", "season"]] + [item["values"].get(key) for key in request.metrics] + metric_units + metadata + [result["total"], len(result["items"])])
    filename = f"pitchiq_v2_data_lab_{visualization}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}", "X-Content-Type-Options": "nosniff", "X-PITCHIQ-Total": str(result.get("total", result.get("n", len(result.get("items", []))))), "X-PITCHIQ-Exported": str(len(result.get("items", [])))})


@v2_app.post("/exports/analytics-summary")
def export_analytics_summary(request: DescriptiveRequest, connection: sqlite3.Connection = Depends(_connection)):
    result = descriptive_analytics(request, connection)
    fields = ["count", "mean", "median", "standard_deviation", "variance", "minimum", "q1", "q2", "q3", "interquartile_range", "maximum"]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["group_by", "group", "metric", *fields, "source_name", "source_release", "source_rights_status", "season_scope", "competition_scope", "club_scope", "position_scope", "minimum_minutes"])
    source = _source_context(connection)
    provenance = [source.get("provider_name"), source.get("release_name"), source.get("rights_status"), request.season_id, request.competition_id, request.club_id, request.position, request.minimum_minutes]
    if result["groups"]:
        for group in result["groups"]:
            for summary in group["metrics"]:
                writer.writerow([request.group_by, _csv_cell(group["group"]), summary["metric"], *[summary.get(field) for field in fields], *[_csv_cell(value) for value in provenance]])
    else:
        for summary in result["summary"]:
            writer.writerow(["", "", summary["metric"], *[summary.get(field) for field in fields], *[_csv_cell(value) for value in provenance]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=pitchiq_v2_analytics_summary.csv", "X-Content-Type-Options": "nosniff"})


@v2_app.post("/exports/outliers")
def export_analytics_outliers(request: OutlierRequest, connection: sqlite3.Connection = Depends(_connection)):
    frame = _analytics_frame(connection, [request.metric], **request.model_dump(exclude={"metric", "multiplier", "limit"}))
    result = iqr_outliers(frame, request.metric, multiplier=request.multiplier, limit=request.limit)
    source = _source_context(connection)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["record_id", "player_id", "player", "position", "club", "competition", "season", request.metric, "distance_from_fence", "q1", "q3", "iqr", "lower_bound", "upper_bound", "multiplier", "outlier_count", "source_name", "source_release", "source_rights_status"])
    for item in result["items"]:
        writer.writerow([item.get("record_id"), item.get("player_id"), _csv_cell(item.get("player")), _csv_cell(item.get("position_raw")), _csv_cell(item.get("club")), _csv_cell(item.get("competition")), _csv_cell(item.get("season")), item.get(request.metric), item.get("distance_from_fence"), result["q1"], result["q3"], result["iqr"], result["lower_bound"], result["upper_bound"], request.multiplier, result["outlier_count"], _csv_cell(source.get("provider_name")), _csv_cell(source.get("release_name")), _csv_cell(source.get("rights_status"))])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=pitchiq_v2_potential_outliers.csv", "X-Content-Type-Options": "nosniff", "X-PITCHIQ-Outlier-Count": str(result["outlier_count"]), "X-PITCHIQ-Exported": str(len(result["items"]))})
