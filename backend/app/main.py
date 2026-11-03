"""PITCHIQ data API. Dataset-derived figures are descriptive player-record aggregates."""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "players_data_light-2025_2026.csv"
MINIMUM_MINUTES = 450
MAX_PAGE_SIZE = 500
NUMERIC_COLUMNS = ["Age", "MP", "Starts", "Min", "90s", "Gls", "Ast", "G+A", "G-PK", "PK", "PKatt", "CrdY", "CrdR", "Sh", "SoT", "SoT%", "TklW", "Int", "Crs", "GA", "Saves", "Save%"]
SORT_FIELDS = {"Player", "Gls", "Ast", "G+A", "Min", "Age", "Sh", "SoT", "SoT%", "goals_per90", "assists_per90", "contributions_per90", "shot_accuracy"}


def load_data(path: Path = CSV_PATH) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError("PITCHIQ dataset is unavailable")
    df = pd.read_csv(path)
    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("Player", "Squad", "Pos", "Comp"):
        if col not in df:
            df[col] = pd.Series(pd.NA, index=df.index, dtype="string")
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    # Reject impossible source values as unavailable; keep valid observed zeroes intact.
    if "Min" in df:
        df.loc[df["Min"] < 0, "Min"] = np.nan
    if "Age" in df:
        df.loc[~df["Age"].between(14, 60), "Age"] = np.nan
    for col in ("Gls", "Ast", "G+A", "Sh", "SoT", "TklW", "Int", "Crs", "Saves", "GA"):
        if col in df:
            df.loc[df[col] < 0, col] = np.nan
    if {"Gls", "Ast", "Min"}.issubset(df.columns):
        valid_minutes = df["Min"].gt(0)
        df["goals_per90"] = ((df["Gls"] * 90) / df["Min"]).where(valid_minutes & df["Gls"].notna())
        df["assists_per90"] = ((df["Ast"] * 90) / df["Min"]).where(valid_minutes & df["Ast"].notna())
        df["contributions_per90"] = (((df["Gls"] + df["Ast"]) * 90) / df["Min"]).where(valid_minutes & df["Gls"].notna() & df["Ast"].notna())
    else:
        for col in ("goals_per90", "assists_per90", "contributions_per90"):
            df[col] = np.nan
    # The source SoT% is retained as provided. Accuracy is calculated only when absent.
    if "SoT%" in df:
        df["shot_accuracy"] = df["SoT%"].where(df["SoT%"].between(0, 100))
    elif {"SoT", "Sh"}.issubset(df.columns):
        df["shot_accuracy"] = ((df["SoT"] / df["Sh"]) * 100).where(df["Sh"].gt(0) & df["SoT"].notna())
    else:
        df["shot_accuracy"] = np.nan
    # Keep rows and missing identities visible to quality reporting, not silently repaired.
    return df


DF = load_data()


def json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


def primary_position(value: Any) -> str:
    """Use the source's first-listed position for grouping; the full field remains available."""
    if pd.isna(value):
        return "Unknown"
    return str(value).split(",", 1)[0].strip() or "Unknown"


def filter_players(*, search: str | None = None, squad: str | None = None,
                   position: str | None = None, competition: str | None = None,
                   min_minutes: int = 0) -> pd.DataFrame:
    d = DF.copy()
    if search:
        needle = re.escape(search.strip())
        d = d[d["Player"].str.contains(needle, case=False, na=False, regex=True) |
              d["Squad"].str.contains(needle, case=False, na=False, regex=True)]
    if squad:
        d = d[d["Squad"] == squad]
    if position:
        d = d[d["Pos"].fillna("").str.split(",").map(lambda positions: position in [p.strip() for p in positions])]
    if competition:
        d = d[d["Comp"] == competition]
    return d[d["Min"].ge(min_minutes)]


class PlayerRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Rk: int
    Player: str | None
    Nation: str | None = None
    Pos: str | None
    Squad: str | None
    Comp: str | None
    Age: float | None = None
    MP: float | None = None
    Starts: float | None = None
    Min: float | None = None
    Gls: float | None = None
    Ast: float | None = None
    plus_minus: float | None = Field(default=None, alias="G+A")
    Sh: float | None = None
    SoT: float | None = None
    sot_percent: float | None = Field(default=None, alias="SoT%")
    goals_per90: float | None = None
    assists_per90: float | None = None
    contributions_per90: float | None = None
    shot_accuracy: float | None = None


class PlayerPage(BaseModel):
    total: int
    items: list[PlayerRecord]


class ErrorResponse(BaseModel):
    detail: str


origins = [origin.strip() for origin in os.getenv("PITCHIQ_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
production = os.getenv("PITCHIQ_ENV", "development").lower() == "production"
app = FastAPI(title="PITCHIQ API", version="2.0.0", description="Football player and team analytics",
              docs_url=None if production else "/docs", redoc_url=None if production else "/redoc", openapi_url=None if production else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Accept", "Content-Type"])


@app.get("/", response_model=dict)
def root():
    return {"name": "PITCHIQ API", "status": "online", "docs": None if production else "/docs"}


@app.get("/api/health", response_model=dict)
def health():
    return {"status": "healthy", "rows": len(DF), "columns": len(DF.columns)}


@app.get("/api/overview", response_model=dict)
def overview(squad: str | None = Query(None, max_length=100), competition: str | None = Query(None, max_length=100),
             position: str | None = Query(None, max_length=10), min_minutes: int = Query(0, ge=0, le=100000)):
    d = filter_players(squad=squad, competition=competition, position=position, min_minutes=min_minutes)
    season_match = re.search(r"(20\d{2})[_-](20\d{2})", CSV_PATH.stem)
    season = f"{season_match.group(1)} / {season_match.group(2)}" if season_match else "Current release"
    return {"players": int(d["Player"].nunique()), "records": int(len(d)), "teams": int(d["Squad"].nunique()),
            "competitions": int(d["Comp"].nunique()), "goals": int(d["Gls"].sum()), "assists": int(d["Ast"].sum()),
            "minutes": int(d["Min"].sum()), "shots": int(d["Sh"].sum()),
            "avg_age": round(float(d["Age"].mean()), 1) if d["Age"].notna().any() else None, "season": season,
            "methodology": "KPIs are calculated from the filtered supplied player records; squad sums are not official team totals."}


@app.get("/api/filters", response_model=dict)
def filters():
    return {"squads": sorted(DF["Squad"].dropna().unique().tolist()),
            "competitions": sorted(DF["Comp"].dropna().unique().tolist()),
            "positions": sorted({pos.strip() for value in DF["Pos"].dropna() for pos in value.split(",")})}


@app.get("/api/player-options")
def player_options(search: str | None = Query(None, max_length=100)):
    d = filter_players(search=search)
    return json_records(d[["Rk", "Player", "Squad", "Pos", "Comp"]])


@app.get("/api/players", response_model=PlayerPage, responses={422: {"model": ErrorResponse}})
def players(search: str | None = Query(None, max_length=100), squad: str | None = Query(None, max_length=100),
            position: str | None = Query(None, max_length=10), competition: str | None = Query(None, max_length=100),
            min_minutes: int = Query(0, ge=0, le=100000), sort_by: str = Query("Gls"),
            order: Literal["asc", "desc"] = "desc", limit: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
            offset: int = Query(0, ge=0)):
    if sort_by not in SORT_FIELDS:
        raise HTTPException(422, f"sort_by must be one of: {', '.join(sorted(SORT_FIELDS))}")
    d = filter_players(search=search, squad=squad, position=position, competition=competition, min_minutes=min_minutes)
    d = d.sort_values(sort_by, ascending=order == "asc", na_position="last", kind="stable")
    total = len(d)
    cols = ["Rk", "Player", "Nation", "Pos", "Squad", "Comp", "Age", "MP", "Starts", "Min", "Gls", "Ast", "G+A", "Sh", "SoT", "SoT%", "goals_per90", "assists_per90", "contributions_per90", "shot_accuracy"]
    return {"total": total, "items": json_records(d[[c for c in cols if c in d]].iloc[offset:offset + limit])}


@app.get("/api/players/{rank}")
def player_detail(rank: int):
    matches = DF[DF["Rk"] == rank]
    if matches.empty:
        raise HTTPException(404, "Player record not found")
    return json_records(matches.head(1))[0]


@app.get("/api/teams", response_model=list[dict[str, Any]])
def teams(squad: str | None = Query(None, max_length=100), competition: str | None = Query(None, max_length=100),
          position: str | None = Query(None, max_length=10), min_minutes: int = Query(0, ge=0, le=100000)):
    # These are sums of player-level records, not independently verified club totals.
    records = filter_players(squad=squad, competition=competition, position=position, min_minutes=min_minutes)
    d = records.groupby("Squad", dropna=False).agg(players=("Player", "nunique"), goals=("Gls", "sum"),
        assists=("Ast", "sum"), shots=("Sh", "sum"), minutes=("Min", "sum"), matches=("MP", "max")).reset_index()
    d = d.rename(columns={"Squad": "team"}).assign(goal_contributions=lambda x: x.goals + x.assists)
    d = d.sort_values("goals", ascending=False, kind="stable").head(30)
    method = "Player-record sums grouped by squad; not official team totals. Goalkeeper-only fields are excluded."
    return [{**row, "methodology": method} for row in json_records(d)]


@app.get("/api/compare")
def compare(ids: str = Query(..., max_length=100, description="Comma-separated unique Rk values, e.g. 1,2")):
    try:
        ranks = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError as exc:
        raise HTTPException(422, "Player IDs must be integers") from exc
    if not 1 <= len(ranks) <= 4 or len(set(ranks)) != len(ranks):
        raise HTTPException(422, "Select between 1 and 4 distinct player records")
    d = DF.set_index("Rk").reindex(ranks).dropna(how="all").reset_index()
    if len(d) != len(ranks):
        raise HTTPException(404, "One or more player records were not found")
    cols = ["Rk", "Player", "Squad", "Comp", "Pos", "Age", "Min", "Gls", "Ast", "G+A", "Sh", "SoT", "SoT%", "shot_accuracy", "goals_per90", "assists_per90", "contributions_per90", "TklW", "Int", "Crs"]
    return json_records(d[[c for c in cols if c in d]])


@app.get("/api/leaderboards")
def leaderboards(metric: Literal["goals_per90", "assists_per90", "contributions_per90", "shot_accuracy"] = "goals_per90",
                 min_minutes: int = Query(MINIMUM_MINUTES, ge=0, le=100000), limit: int = Query(20, ge=1, le=100),
                 competition: str | None = Query(None, max_length=100)):
    d = filter_players(competition=competition, min_minutes=min_minutes)
    d = d[d[metric].notna()].sort_values(metric, ascending=False, kind="stable").head(limit)
    cols = ["Rk", "Player", "Squad", "Comp", "Pos", "Min", "Gls", "Ast", "Sh", "SoT", "SoT%", metric]
    return {"metric": metric, "minimum_minutes": min_minutes, "methodology": "Per-90 values require valid positive minutes and source goals/assists. Shooting accuracy uses source SoT% when available. The minutes floor reduces small-sample distortion.", "items": json_records(d[cols])}


@app.get("/api/analysis/correlation")
def correlation():
    cols = [c for c in ["Age", "Min", "Gls", "Ast", "Sh", "SoT", "TklW", "Int", "Crs", "GA", "Saves"] if c in DF]
    corr = DF[cols].corr(method="pearson", min_periods=2).round(2)
    return {"labels": list(corr.columns), "matrix": corr.astype(object).where(pd.notna(corr), None).values.tolist(),
            "method": "Pearson correlation (linear association)", "note": "Correlation does not imply causation. No significance testing is performed; unavailable pairs remain null."}


@app.get("/api/analysis/positions")
def positions():
    d = DF.copy()
    d["primary_position"] = d["Pos"].map(primary_position)
    out = d.groupby("primary_position", dropna=False).agg(players=("Player", "nunique"), goals=("Gls", "sum"), assists=("Ast", "sum"), avg_minutes=("Min", "mean"), avg_goals=("Gls", "mean")).reset_index()
    method = "Each record is grouped by its first listed source position; full multi-position values remain on player records."
    return [{**row, "methodology": method} for row in json_records(out.sort_values("players", ascending=False))]


@app.get("/api/analysis/competitions")
def competitions(competition: str | None = Query(None, max_length=100)):
    d = DF if competition is None else DF[DF["Comp"] == competition]
    by_comp = d.groupby("Comp", dropna=False).agg(player_records=("Player", "size"), players=("Player", "nunique"), goals=("Gls", "sum"), assists=("Ast", "sum"), avg_minutes=("Min", "mean")).reset_index()
    position_counts = d.assign(position=d["Pos"].map(primary_position)).groupby(["Comp", "position"], dropna=False).size().rename("records").reset_index()
    top = d.sort_values("Gls", ascending=False).groupby("Comp", dropna=False).head(10)
    return {"methodology": "Descriptive aggregates over supplied player records; these are not official competition standings.",
            "competitions": json_records(by_comp), "positions": json_records(position_counts),
            "top_scorers": json_records(top[["Rk", "Player", "Squad", "Comp", "Pos", "Gls", "Ast", "Min"]])}


@app.get("/api/quality")
def quality():
    return {"rows": int(len(DF)), "columns": int(len(DF.columns)), "missing_cells": int(DF.isna().sum().sum()),
            "duplicate_rows": int(DF.duplicated().sum()), "duplicate_rk": int(DF["Rk"].duplicated().sum()),
            "missing_names": int(DF["Player"].isna().sum()), "missing_squads": int(DF["Squad"].isna().sum()),
            "missing_by_column": {k: int(v) for k, v in DF.isna().sum().sort_values(ascending=False).head(12).items()},
            "zero_minute_records": int(DF["Min"].eq(0).sum()), "dataset": CSV_PATH.name}


def csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@app.get("/api/export/players")
def export_players(search: str | None = Query(None, max_length=100), squad: str | None = Query(None, max_length=100),
                   position: str | None = Query(None, max_length=10), competition: str | None = Query(None, max_length=100),
                   min_minutes: int = Query(0, ge=0, le=100000)):
    d = filter_players(search=search, squad=squad, position=position, competition=competition, min_minutes=min_minutes).copy()
    for col in d.columns:
        if pd.api.types.is_object_dtype(d[col].dtype) or isinstance(d[col].dtype, pd.StringDtype):
            d[col] = d[col].map(csv_safe)
    buffer = io.StringIO(newline="")
    d.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=pitchiq_players.csv", "X-Content-Type-Options": "nosniff"})


from .api_v2 import v2_app

app.mount("/api/v2", v2_app)
