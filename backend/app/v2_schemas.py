"""Public Pydantic contracts for PITCHIQ v2 endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class V2Error(BaseModel):
    error: str
    code: str


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class PlayerSummary(BaseModel):
    id: str
    canonical_name: str
    nationality: str | None = None
    primary_position: str | None = None
    identity_status: str
    record_count: int
    club_count: int
    competition_count: int
    seasons: list[str]
    appearances: float | None = None
    starts: float | None = None
    minutes: float | None = None
    goals: float | None = None
    assists: float | None = None
    shots: float | None = None
    shots_on_target: float | None = None
    non_penalty_goals: float | None = None
    non_penalty_goal_contributions: float | None = None
    non_penalty_contributions_per90: float | None = None
    penalties_scored: float | None = None
    penalties_attempted: float | None = None
    yellow_cards: float | None = None
    red_cards: float | None = None
    second_yellow_cards: float | None = None
    fouls_committed: float | None = None
    fouls_drawn: float | None = None
    own_goals: float | None = None
    crosses: float | None = None
    tackles_won: float | None = None
    interceptions: float | None = None
    goals_against: float | None = None
    goals_against_per90: float | None = None
    shots_on_target_against: float | None = None
    saves: float | None = None
    save_percent: float | None = None
    wins: float | None = None
    draws: float | None = None
    losses: float | None = None
    clean_sheets: float | None = None
    clean_sheet_percent: float | None = None
    penalties_faced: float | None = None
    penalties_against: float | None = None
    penalties_saved: float | None = None
    penalties_missed: float | None = None
    goals_per90: float | None = None
    assists_per90: float | None = None
    contributions_per90: float | None = None
    non_penalty_goals_per90: float | None = None
    crosses_per90: float | None = None
    tackles_won_per90: float | None = None
    interceptions_per90: float | None = None
    shots_per90: float | None = None
    shots_on_target_per90: float | None = None
    goals_per_appearance: float | None = None
    assists_per_appearance: float | None = None
    goals_per_shot: float | None = None
    shots_per_goal: float | None = None
    shot_accuracy: float | None = None


class PlayerDetail(PlayerSummary):
    date_of_birth: str | None = None
    birth_year: int | None = None
    preferred_foot: str | None = None
    height_cm: float | None = None
    aliases: list[str] = Field(default_factory=list)
    source_context: dict[str, object] = Field(default_factory=dict)


class StatRecord(BaseModel):
    id: str
    player_id: str
    club_id: str | None = None
    club: str | None = None
    competition_id: str | None = None
    competition: str | None = None
    season_id: str
    season: str
    scope: str
    position_raw: str | None = None
    appearances: float | None = None
    starts: float | None = None
    minutes: float | None = None
    goals: float | None = None
    assists: float | None = None
    goal_contributions: float | None = None
    shots: float | None = None
    shots_on_target: float | None = None
    non_penalty_goals: float | None = None
    non_penalty_goal_contributions: float | None = None
    non_penalty_contributions_per90: float | None = None
    penalties_scored: float | None = None
    penalties_attempted: float | None = None
    yellow_cards: float | None = None
    red_cards: float | None = None
    second_yellow_cards: float | None = None
    fouls_committed: float | None = None
    fouls_drawn: float | None = None
    own_goals: float | None = None
    crosses: float | None = None
    tackles_won: float | None = None
    interceptions: float | None = None
    goals_against: float | None = None
    goals_against_per90: float | None = None
    shots_on_target_against: float | None = None
    saves: float | None = None
    save_percent: float | None = None
    wins: float | None = None
    draws: float | None = None
    losses: float | None = None
    clean_sheets: float | None = None
    clean_sheet_percent: float | None = None
    penalties_faced: float | None = None
    penalties_against: float | None = None
    penalties_saved: float | None = None
    penalties_missed: float | None = None
    source_sot_percent: float | None = None
    shot_accuracy: float | None = None
    goals_per90: float | None = None
    assists_per90: float | None = None
    contributions_per90: float | None = None
    shots_per90: float | None = None
    shots_on_target_per90: float | None = None
    source_id: str
    source_name: str
    source_release: str


class PagePlayers(BaseModel):
    items: list[PlayerSummary]
    meta: PageMeta
    source_context: dict[str, object]


class PageClubs(BaseModel):
    items: list[dict[str, object]]
    meta: PageMeta


class PageCompetitions(BaseModel):
    items: list[dict[str, object]]
    meta: PageMeta


class IdentityCandidate(BaseModel):
    id: str
    canonical_name: str
    birth_year: int | None = None
    nationality: str | None = None
    identity_status: str


class IdentityReviewItem(BaseModel):
    id: str
    source_id: str
    source_player_key: str
    candidate_player_id: str | None = None
    canonical_name: str | None = None
    status: str
    evidence: dict[str, object]
    method_version: str
    reviewer: str | None = None
    decided_at: str


class IdentitySummary(BaseModel):
    source_local_keys: int
    verified_external_ids: int
    decision_statuses: dict[str, int]
    ambiguous_name_groups: int
    ambiguity_examples: list[dict[str, object]]
    note: str


class ComparePlayersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_ids: list[str] = Field(min_length=1, max_length=4)
    season_id: str | None = None
    competition_id: str | None = None
    minimum_minutes: int = Field(default=0, ge=0, le=100000)

    @field_validator("player_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("player_ids must not contain blank values")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("player_ids must be unique")
        return cleaned


class DataLabQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visualization: Literal["table", "histogram", "scatter", "correlation"] = "table"
    metrics: list[str] = Field(min_length=1, max_length=2)
    method: Literal["pearson", "spearman"] = "pearson"
    season_id: str | None = None
    competition_id: str | None = None
    club_id: str | None = None
    position: str | None = Field(default=None, max_length=30)
    minimum_minutes: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=500, ge=1, le=1000)

    @field_validator("metrics")
    @classmethod
    def metric_keys(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("metrics must be unique")
        return cleaned


class AnalyticsScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season_id: str | None = Field(default=None, max_length=20)
    competition_id: str | None = Field(default=None, max_length=80)
    club_id: str | None = Field(default=None, max_length=80)
    position: str | None = Field(default=None, max_length=30)
    minimum_minutes: int = Field(default=0, ge=0, le=100000)


class DescriptiveRequest(AnalyticsScope):
    metrics: list[str] = Field(min_length=1, max_length=8)
    group_by: Literal["position", "competition", "club", "season"] | None = None

    @field_validator("metrics")
    @classmethod
    def unique_metric_keys(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("metrics must be non-empty and unique")
        return cleaned


class OutlierRequest(AnalyticsScope):
    metric: str = Field(min_length=1, max_length=40)
    multiplier: float = Field(default=1.5, ge=0.5, le=3.0)
    limit: int = Field(default=500, ge=1, le=5000)


class VisualizationRequest(DescriptiveRequest):
    visualization: Literal["bar", "histogram", "scatter", "line", "boxplot", "correlation_heatmap"]
    method: Literal["pearson", "spearman"] = "pearson"
