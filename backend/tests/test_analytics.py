from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics.correlation import correlation_matrix
from app.analytics.data_quality import quality_report
from app.analytics.descriptive import grouped_summaries, summarize_series
from app.analytics.distributions import histogram
from app.analytics.outliers import iqr_outliers
from app.analytics.visualizations import render_missingness_png, render_png
from app.database import connect
from app.ingestion.legacy_csv import import_csv


def test_descriptive_summary_uses_observed_values_and_sample_variance():
    summary = summarize_series(pd.Series([1.0, 2.0, None, 4.0]))
    assert summary["count"] == 3
    assert summary["mean"] == pytest.approx(7 / 3)
    assert summary["median"] == 2
    assert summary["variance"] == pytest.approx(7 / 3)
    assert summary["standard_deviation"] == pytest.approx(np.sqrt(7 / 3))
    assert (summary["q1"], summary["q2"], summary["q3"], summary["interquartile_range"]) == (1.5, 2.0, 3.0, 1.5)
    empty = summarize_series(pd.Series([None, np.nan]))
    assert empty["count"] == 0 and empty["mean"] is None and empty["variance"] is None
    singleton = summarize_series(pd.Series([8.0]))
    assert singleton["standard_deviation"] is None and singleton["variance"] is None


def test_grouped_summaries_count_distinct_players_and_preserve_null_metrics():
    frame = pd.DataFrame({
        "position": ["FW", "FW", "GK"], "player_id": ["p1", "p1", "p2"],
        "goals": [1.0, None, None],
    })
    groups = grouped_summaries(frame, ["goals"], "position")
    assert [(item["group"], item["player_count"], item["record_count"]) for item in groups] == [("FW", 1, 2), ("GK", 1, 1)]
    assert groups[1]["metrics"][0]["mean"] is None


def test_histogram_excludes_missing_and_handles_constant_values():
    bins, summary = histogram(pd.Series([2.0, 2.0, None]), bins=4)
    assert summary["count"] == 2
    assert sum(item["count"] for item in bins) == 2
    assert len(bins) == 4
    assert histogram(pd.Series([None]), bins=4) == ([], summarize_series(pd.Series([None])))


def test_correlations_support_pearson_spearman_pairwise_counts_and_constant_nulls():
    frame = pd.DataFrame({"x": [1, 2, 3, None], "reverse": [3, 2, 1, 4], "constant": [9, 9, 9, 9]})
    pearson = correlation_matrix(frame, ["x", "reverse", "constant"], "pearson")
    spearman = correlation_matrix(frame, ["x", "reverse"], "spearman")
    assert pearson["matrix"][0][1] == -1
    assert spearman["matrix"][0][1] == -1
    assert pearson["pairwise_n"][0][1] == 3
    assert pearson["matrix"][2][2] is None
    too_short = correlation_matrix(frame.head(2), ["x", "reverse"], "pearson")
    assert too_short["matrix"][0][1] is None


def test_iqr_flags_records_without_removing_them():
    frame = pd.DataFrame({
        "record_id": [f"r{i}" for i in range(5)], "player_id": [f"p{i}" for i in range(5)],
        "player": [f"Player {i}" for i in range(5)], "position_raw": ["FW"] * 5,
        "club": ["Club"] * 5, "competition": ["Comp"] * 5, "season": ["2025–26"] * 5,
        "goals": [1, 2, 3, 4, 100],
    })
    result = iqr_outliers(frame, "goals")
    assert result["outlier_count"] == 1
    assert result["items"][0]["player"] == "Player 4"
    assert len(frame) == 5
    assert "not presumed erroneous" in result["methodology"]


def test_quality_profile_reports_nulls_duplicates_and_invalids():
    frame = pd.DataFrame({
        "id": ["a", "b"], "source_release_id": ["r", "r"], "source_record_key": ["1", "1"],
        "player_id": ["p", "p"], "minutes": [10, -1], "goals": [None, 2], "age": [20, 121],
    })
    columns = [{"name": name, "type": "REAL"} for name in frame.columns]
    report = quality_report(frame, columns)
    assert report["total_records"] == 2
    assert report["duplicate_source_key_records"] == 2
    assert report["missing_cells"] == 1
    assert report["potential_invalid_values"]["negative_minutes_records"] == 1
    assert report["potential_invalid_values"]["age_outside_0_100_records"] == 1
    assert render_missingness_png(frame).startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("kind,metrics", [
    ("bar", ["x"]), ("histogram", ["x"]), ("scatter", ["x", "y"]),
    ("line", ["x"]), ("boxplot", ["x"]), ("correlation_heatmap", ["x", "y"]),
])
def test_visualization_engine_renders_png_for_supported_chart_types(kind: str, metrics: list[str]):
    frame = pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0], "y": [4.0, 2.0, 3.0, 1.0],
        "competition": ["A", "A", "B", "B"], "position": ["FW", "FW", "MF", "MF"],
    })
    image = render_png(frame, kind=kind, metrics=metrics, group_by="competition")
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 1000


@pytest.fixture()
def analytics_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "analytics-v2.sqlite3"
    from app.database import migrate

    migrate(database)
    import_csv(root / "data" / "source_data_with_derived_metrics.csv", root / "data" / "player_master.csv", database)
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(database))
    from app.main import app

    with TestClient(app) as client:
        yield client


def test_analytics_endpoints_descriptive_spearman_outliers_quality_and_png(analytics_client: TestClient):
    descriptive = analytics_client.post("/api/v2/analytics/descriptive", json={
        "metrics": ["goals", "minutes"], "group_by": "position", "minimum_minutes": 450,
    })
    assert descriptive.status_code == 200
    payload = descriptive.json()
    assert payload["record_count"] > 0
    assert payload["summary"][0]["count"] <= payload["record_count"]
    assert payload["groups"]
    assert payload["methodology"].find("Missing values are excluded") >= 0

    correlation = analytics_client.get("/api/v2/analytics/correlation", params={"metrics": "goals,assists,shots", "method": "spearman"})
    assert correlation.status_code == 200
    assert correlation.json()["method"] == "Spearman rank correlation"
    assert len(correlation.json()["matrix"]) == 3

    outliers = analytics_client.get("/api/v2/analytics/outliers", params={"metric": "goals", "limit": 5})
    assert outliers.status_code == 200
    assert outliers.json()["q1"] is not None
    assert len(outliers.json()["items"]) <= 5

    quality = analytics_client.get("/api/v2/analytics/quality")
    assert quality.status_code == 200
    assert quality.json()["total_records"] == 2839
    assert quality.json()["missing_cells"] > 0
    assert quality.json()["duplicate_source_key_records"] == 0
    quality_chart = analytics_client.get("/api/v2/analytics/quality/visualization")
    assert quality_chart.status_code == 200
    assert quality_chart.headers["content-type"].startswith("image/png")
    assert quality_chart.content.startswith(b"\x89PNG\r\n\x1a\n")

    image = analytics_client.post("/api/v2/analytics/visualizations", json={
        "visualization": "boxplot", "metrics": ["shot_accuracy"], "group_by": "position",
    })
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")

    unavailable = analytics_client.post("/api/v2/analytics/visualizations", json={
        "visualization": "histogram", "metrics": ["goals"], "club_id": "unknown-club",
    })
    assert unavailable.status_code == 422
    invalid_metric = analytics_client.post("/api/v2/analytics/descriptive", json={"metrics": ["xg"]})
    assert invalid_metric.status_code == 422
    invalid_multiplier = analytics_client.get("/api/v2/analytics/outliers", params={"metric": "goals", "multiplier": 10})
    assert invalid_multiplier.status_code == 422
    outlier_csv = analytics_client.post("/api/v2/exports/outliers", json={"metric": "goals", "limit": 10})
    assert outlier_csv.status_code == 200
    assert "distance_from_fence" in outlier_csv.text
    assert "outlier_count" in outlier_csv.text


def test_data_lab_returns_pandas_summary_and_supports_spearman(analytics_client: TestClient):
    response = analytics_client.post("/api/v2/data-lab/query", json={
        "visualization": "correlation", "metrics": ["goals", "assists"], "method": "spearman", "minimum_minutes": 450,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["unit"] == "Spearman rho"
    assert len(result["summary"]) == 2
    assert result["n"] > 2

    exported = analytics_client.post("/api/v2/exports/analytics-summary", json={
        "metrics": ["goals"], "group_by": "competition",
    })
    assert exported.status_code == 200
    assert "standard_deviation" in exported.text
    assert "competition" in exported.text
