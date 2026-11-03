import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_source_dataset_integrity_and_nulls():
    frame = main.load_data()
    assert len(frame) == 2839
    assert frame["Rk"].is_unique
    assert frame["Player"].notna().all()
    assert frame["GA"].isna().sum() > 0


def test_metric_formulas_and_invalid_minutes(tmp_path):
    path = tmp_path / "players.csv"
    pd.DataFrame({"Rk": [1, 2], "Player": ["A", "B"], "Squad": ["X", "X"], "Pos": ["FW", "FW"],
                  "Comp": ["C", "C"], "Age": [20, 20], "Min": [90, 0], "Gls": [2, 3], "Ast": [1, 1],
                  "Sh": [4, 0], "SoT": [2, 0], "SoT%": [50, None]}).to_csv(path, index=False)
    frame = main.load_data(path)
    assert frame.loc[0, "goals_per90"] == 2
    assert frame.loc[0, "assists_per90"] == 1
    assert frame.loc[0, "contributions_per90"] == 3
    assert frame.loc[0, "shot_accuracy"] == 50
    assert pd.isna(frame.loc[1, "goals_per90"])
    assert pd.isna(frame.loc[1, "shot_accuracy"])


def test_loader_preserves_missing_values_and_coerces_invalid_numbers(tmp_path):
    path = tmp_path / "players.csv"
    pd.DataFrame({"Rk": [1], "Player": [None], "Squad": [" "], "Pos": ["MF"], "Comp": ["C"],
                  "Age": [999], "Min": [-1], "Gls": ["bad"], "Ast": [None], "Sh": [3], "SoT": [1]}).to_csv(path, index=False)
    row = main.load_data(path).iloc[0]
    assert pd.isna(row.Player) and pd.isna(row.Squad)
    assert pd.isna(row.Age) and pd.isna(row.Min) and pd.isna(row.Gls)
    assert pd.isna(row.Ast)


def test_players_filter_sort_and_pagination():
    response = client.get("/api/players", params={"position": "FW", "competition": "eng Premier League", "min_minutes": 450, "sort_by": "Gls", "limit": 3})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 3
    assert payload["total"] >= 3
    assert all("FW" in row["Pos"] and row["Comp"] == "eng Premier League" and row["Min"] >= 450 for row in payload["items"])
    assert [row["Gls"] for row in payload["items"]] == sorted([row["Gls"] for row in payload["items"]], reverse=True)
    assert "G+A" in payload["items"][0]


def test_player_options_include_full_dataset_and_search_safely():
    all_options = client.get("/api/player-options")
    assert all_options.status_code == 200 and len(all_options.json()) == 2839
    assert set(all_options.json()[0]) == {"Rk", "Player", "Squad", "Pos", "Comp"}
    searched = client.get("/api/player-options", params={"search": "["})
    assert searched.status_code == 200 and searched.json() == []


@pytest.mark.parametrize("params", [{"limit": 501}, {"offset": -1}, {"min_minutes": -1}, {"order": "sideways"}, {"sort_by": "__class__"}])
def test_invalid_player_parameters_return_422(params):
    assert client.get("/api/players", params=params).status_code == 422


def test_compare_supports_distinct_stable_ids_and_validates():
    payload = client.get("/api/compare", params={"ids": "1,2,3,4"})
    assert payload.status_code == 200 and [p["Rk"] for p in payload.json()] == [1, 2, 3, 4]
    assert client.get("/api/compare", params={"ids": "1,1"}).status_code == 422
    assert client.get("/api/compare", params={"ids": "99999,99998"}).status_code == 404


def test_team_aggregation_excludes_goalkeeper_totals():
    payload = client.get("/api/teams").json()
    assert isinstance(payload, list) and "not official team totals" in payload[0]["methodology"]
    assert "saves" not in payload[0]
    assert len(payload) == 30


def test_teams_and_positions_keep_their_original_array_contracts():
    teams = client.get("/api/teams").json()
    positions = client.get("/api/analysis/positions").json()
    assert isinstance(teams, list) and isinstance(positions, list)
    assert "methodology" in positions[0] and "first listed" in positions[0]["methodology"]


def test_overview_filters_apply_consistently_to_kpis_teams_and_player_rows():
    filters = {"competition": "eng Premier League", "position": "FW", "min_minutes": 900}
    expected = main.filter_players(**filters)
    overview = client.get("/api/overview", params=filters)
    teams = client.get("/api/teams", params=filters)
    players = client.get("/api/players", params={**filters, "limit": 500})
    assert overview.status_code == teams.status_code == players.status_code == 200
    summary = overview.json()
    assert summary["records"] == len(expected)
    assert summary["players"] == expected["Player"].nunique()
    assert summary["goals"] == expected["Gls"].sum()
    assert summary["season"] == "2025 / 2026"
    assert sum(team["goals"] for team in teams.json()) == expected["Gls"].sum()
    assert all(item["Comp"] == filters["competition"] and item["Min"] >= filters["min_minutes"] and "FW" in item["Pos"] for item in players.json()["items"])


def test_correlation_nulls_and_methodology(monkeypatch):
    source = main.DF.copy()
    source["Age"] = 20  # A constant column has undefined correlation.
    monkeypatch.setattr(main, "DF", source)
    payload = client.get("/api/analysis/correlation").json()
    assert "Pearson" in payload["method"]
    assert "does not imply causation" in payload["note"]
    age_index = payload["labels"].index("Age")
    assert payload["matrix"][age_index][age_index] is None


def test_leaderboard_minimum_minutes_and_valid_values():
    payload = client.get("/api/leaderboards", params={"metric": "goals_per90", "min_minutes": 900}).json()
    assert payload["minimum_minutes"] == 900
    assert all(p["Min"] >= 900 and p["goals_per90"] is not None for p in payload["items"])


def test_competition_analysis_and_quality():
    payload = client.get("/api/analysis/competitions", params={"competition": "eng Premier League"}).json()
    assert len(payload["competitions"]) == 1
    assert "not official competition standings" in payload["methodology"]
    quality = client.get("/api/quality").json()
    assert quality["rows"] == 2839 and quality["duplicate_rows"] == 0


def test_csv_export_formula_safety(monkeypatch):
    monkeypatch.setattr(main, "DF", main.DF.copy())
    main.DF.loc[0, "Player"] = "=HYPERLINK(\"x\")"
    response = client.get("/api/export/players", params={"search": "HYPERLINK"})
    assert response.status_code == 200
    assert "'=HYPERLINK" in response.text
    assert response.headers["content-type"].startswith("text/csv")
