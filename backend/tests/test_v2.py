from __future__ import annotations

import csv
import io
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.database import DatabaseNotInitialized, UnsafeDatabaseError, connect, migrate
from app.ingestion.legacy_csv import import_csv, import_report, preview_csv, validate_csv

DATA = Path(__file__).resolve().parents[1] / "data"
STATS = DATA / "source_data_with_derived_metrics.csv"
MASTER = DATA / "player_master.csv"


@pytest.fixture()
def imported_database(tmp_path: Path) -> Path:
    database = tmp_path / "pitchiq-v2.sqlite3"
    assert migrate(database) == 3
    result = import_csv(STATS, MASTER, database)
    assert result["status"] == "completed"
    return database


def test_migration_enforces_foreign_keys_and_does_not_adopt_unknown_database(tmp_path: Path):
    database = tmp_path / "v2.sqlite3"
    assert migrate(database) == 3
    connection = connect(database)
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO player_aliases(player_id, alias, normalized_alias, source_id) VALUES ('missing', 'x', 'x', 'missing')"
        )
    connection.close()

    legacy = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(legacy)
    connection.execute("CREATE TABLE existing_data(value TEXT)")
    connection.commit()
    connection.close()
    before = legacy.read_bytes()
    with pytest.raises(UnsafeDatabaseError):
        migrate(legacy)
    assert legacy.read_bytes() == before


def test_database_missing_is_reported_without_creating_a_file(tmp_path: Path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(DatabaseNotInitialized):
        connect(missing)
    assert not missing.exists()


def test_import_reconciles_records_and_preserves_sparse_values(imported_database: Path):
    connection = connect(imported_database)
    assert connection.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 2690
    assert connection.execute("SELECT COUNT(*) FROM player_stat_records").fetchone()[0] == 2839
    assert connection.execute("SELECT COUNT(*) FROM clubs").fetchone()[0] == 96
    assert connection.execute("SELECT COUNT(*) FROM competitions").fetchone()[0] == 5
    assert connection.execute("SELECT COUNT(*) FROM identity_match_decisions WHERE status='automatically_matched'").fetchone()[0] == 2690
    assert connection.execute("SELECT COUNT(*) FROM source_records WHERE status='warning'").fetchone()[0] == 1
    # Source CS% is 200 for this row; preserve raw input but do not publish an impossible percentage.
    metric = connection.execute("SELECT clean_sheet_percent FROM player_stat_records WHERE source_record_key='2573'").fetchone()[0]
    raw = connection.execute("SELECT payload_json FROM source_records WHERE source_record_key='2573'").fetchone()[0]
    assert metric is None
    assert json.loads(raw)["CS%"] == "200.0"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("SELECT COUNT(*) FROM player_stat_records WHERE saves IS NOT NULL").fetchone()[0] == 194
    assert connection.execute("SELECT COUNT(*) FROM player_stat_records WHERE penalties_saved IS NOT NULL").fetchone()[0] == 194
    assert connection.execute("SELECT COUNT(*) FROM player_stat_records WHERE goals_against_per90 IS NOT NULL").fetchone()[0] == 194
    kane = connection.execute("SELECT non_penalty_goals, assists, non_penalty_goal_contributions, raw_metrics_json FROM player_stat_records s JOIN players p ON p.id=s.player_id WHERE p.canonical_name='Harry Kane'").fetchone()
    assert tuple(kane[:3]) == (26.0, 5.0, 31.0)
    assert json.loads(kane["raw_metrics_json"])["G+A-PK"] == "1.17"
    connection.close()


def test_import_is_idempotent_and_report_tracks_job(imported_database: Path):
    result = import_csv(STATS, MASTER, imported_database)
    assert result["status"] == "unchanged"
    report = import_report(result["job_id"], imported_database)
    assert report["job"]["rows_inserted"] == 0
    assert report["job"]["status"] == "unchanged"
    assert len(report["warnings"]) == 1


def test_v1_database_upgrade_backfills_only_valid_raw_goalkeeper_penalty_counts(tmp_path: Path):
    database = tmp_path / "legacy-v1.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript((Path(__file__).resolve().parents[1] / "app" / "migrations" / "0001_initial.sql").read_text())
    connection.execute("INSERT INTO schema_migrations(version, name) VALUES (1, 'initial')")
    connection.execute("INSERT INTO data_sources(id, provider_name, provider_type) VALUES ('source', 'Fixture', 'file')")
    connection.execute("INSERT INTO source_releases(id, source_id, release_name, checksum, file_name, schema_version) VALUES ('release', 'source', 'r1', 'sum', 'fixture.csv', 'v1')")
    connection.execute("INSERT INTO seasons(id, label) VALUES ('2025-2026', '2025–26')")
    connection.execute("INSERT INTO players(id, canonical_name, normalized_name) VALUES ('player', 'Keeper', 'keeper')")
    connection.execute("INSERT INTO player_stat_records(id, player_id, season_id, source_release_id, source_record_key, raw_metrics_json) VALUES ('stat', 'player', '2025-2026', 'release', 'row1', ?)", (json.dumps({"PKatt_stats_keeper": "2.0", "PKA": "1.0", "PKsv": "1.0", "PKm": "0.0"}),))
    connection.commit()
    connection.close()

    assert migrate(database) == 3
    connection = connect(database)
    assert tuple(connection.execute("SELECT penalties_faced, penalties_against, penalties_saved, penalties_missed FROM player_stat_records WHERE id='stat'").fetchone()) == (2.0, 1.0, 1.0, 0.0)
    connection.close()


def test_preview_reconciles_existing_v2_entities_without_writing(imported_database: Path):
    connection = connect(imported_database)
    before = connection.execute("SELECT COUNT(*) FROM player_stat_records").fetchone()[0]
    connection.close()
    result = preview_csv(STATS, MASTER, imported_database)
    preview = result["preview"]
    assert preview["database_comparison_available"] is True
    assert preview["existing_player_key_matches"] == 2690
    assert preview["new_player_keys"] == 0
    assert preview["new_clubs"] == 0
    assert preview["new_competitions"] == 0
    assert "G/SoT" in preview["unmapped_columns_retained_in_raw_payload"]
    assert "G+A-PK" not in preview["unmapped_columns_retained_in_raw_payload"]
    connection = connect(imported_database)
    assert connection.execute("SELECT COUNT(*) FROM player_stat_records").fetchone()[0] == before
    connection.close()


def test_validation_rejects_bad_rows_but_keeps_warning_rows(tmp_path: Path):
    frame = pd.read_csv(STATS, dtype="string").head(3)
    frame.loc[frame.index[0], "Gls"] = "-1"
    frame.loc[frame.index[0], "G+A-PK"] = "not-a-rate"
    frame.loc[frame.index[1], "CS%"] = "240"
    csv_path = tmp_path / "edge.csv"
    frame.to_csv(csv_path, index=False)
    result = validate_csv(csv_path, MASTER)
    assert result["valid_rows"] == 2
    assert result["rejected_rows"] == 1
    assert any("source_non_penalty_contributions_per90 is not numeric" in error for error in result["errors"][0]["errors"])
    assert any("clean_sheet_percent outside" in item["warning"] for item in result["warnings"])


def test_source_non_penalty_contribution_rate_is_validated_without_becoming_a_count():
    result = validate_csv(STATS, MASTER)
    assert result["valid_rows"] == 2839
    assert not any("G+A-PK differs" in item["warning"] for item in result["warnings"])


def test_failed_import_transaction_rolls_back_source_and_metric_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = tmp_path / "rollback.sqlite3"
    assert migrate(database) == 3
    from app.ingestion import legacy_csv

    def fail_after_source_registration(_connection):
        raise RuntimeError("injected import failure")

    monkeypatch.setattr(legacy_csv, "_insert_metrics", fail_after_source_registration)
    with pytest.raises(RuntimeError, match="injected import failure"):
        legacy_csv.import_csv(STATS, MASTER, database)

    connection = connect(database)
    assert connection.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM source_releases").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM metric_definitions").fetchone()[0] == 0
    connection.close()


def test_v2_routes_are_database_backed_paginated_and_source_aware(imported_database: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(imported_database))
    from app.main import app

    with TestClient(app) as client:
        health = client.get("/api/v2/health")
        assert health.status_code == 200
        assert health.json()["records"] == 2839
        players = client.get("/api/v2/players", params={"limit": 4, "sort_by": "goals", "order": "desc"})
        assert players.status_code == 200
        assert players.json()["meta"] == {"total": 2690, "limit": 4, "offset": 0}
        assert players.json()["items"][0]["goals"] >= players.json()["items"][1]["goals"]
        assert players.json()["source_context"]["rights_status"] == "unverified"
        kane = client.get("/api/v2/players", params={"search": "Harry Kane", "limit": 1}).json()["items"][0]
        assert kane["non_penalty_goal_contributions"] == 31
        assert kane["non_penalty_contributions_per90"] == pytest.approx(90 * 31 / 2377, abs=0.0001)
        club_search = client.get("/api/v2/players", params={"search": "Arsenal", "limit": 5})
        assert club_search.status_code == 200
        assert club_search.json()["meta"]["total"] > 0
        wildcard_search = client.get("/api/v2/players", params={"search": "%", "limit": 5})
        assert wildcard_search.status_code == 200
        assert wildcard_search.json()["meta"]["total"] == 0
        empty_search = client.get("/api/v2/players", params={"search": "", "limit": 5})
        assert empty_search.status_code == 200
        assert empty_search.json()["meta"]["total"] == 2690

        partial_search = client.get("/api/v2/players", params={"search": "  hArRy   kAnE  ", "limit": 5})
        assert partial_search.status_code == 200
        assert any(item["canonical_name"] == "Harry Kane" for item in partial_search.json()["items"])
        partial_name = client.get("/api/v2/players", params={"search": "  hArRy  ", "limit": 5})
        assert any(item["canonical_name"] == "Harry Kane" for item in partial_name.json()["items"])

        # A matching club must belong to the same selected record scope. Vitinha's
        # Genoa record is in Serie A; it must not leak into a Ligue 1 search.
        coverage = client.get("/api/v2/coverage").json()
        ligue_one = next(item["id"] for item in coverage["competitions"] if item["name"] == "fr Ligue 1")
        current_season = coverage["seasons"][0]["id"]
        wrong_scope = client.get("/api/v2/players", params={"search": "Genoa", "season_id": current_season, "competition_id": ligue_one})
        assert wrong_scope.status_code == 200
        assert all(item["canonical_name"] != "Vitinha" for item in wrong_scope.json()["items"])
        matching_scope = client.get("/api/v2/players", params={"search": "Paris Saint-Germain", "season_id": current_season, "competition_id": ligue_one})
        assert any(item["canonical_name"] == "Vitinha" for item in matching_scope.json()["items"])

        # Exercise alias-only search without changing the project's source dataset.
        connection = connect(imported_database)
        vitinha_id = connection.execute("SELECT id FROM players WHERE canonical_name='Vitinha'").fetchone()[0]
        source_id = connection.execute("SELECT id FROM data_sources WHERE is_default=1").fetchone()[0]
        connection.execute(
            "INSERT INTO player_aliases(player_id, alias, normalized_alias, source_id) VALUES (?, ?, ?, ?)",
            (vitinha_id, "Viti Test Alias", "viti test alias", source_id),
        )
        connection.commit()
        connection.close()
        alias_search = client.get("/api/v2/players", params={"search": "  VITI   TEST ", "limit": 5})
        assert any(item["canonical_name"] == "Vitinha" for item in alias_search.json()["items"])
        assert len({item["id"] for item in alias_search.json()["items"]}) == len(alias_search.json()["items"])

        filtered = client.get("/api/v2/players", params={
            "search": "Arsenal", "position": "DF", "club_id": next(item["id"] for item in coverage["clubs"] if item["name"] == "Arsenal"),
            "minimum_minutes": 450, "sort_by": "goals", "order": "desc", "limit": 2,
        })
        assert filtered.status_code == 200
        assert all(item["minutes"] >= 450 for item in filtered.json()["items"])
        assert [item["goals"] for item in filtered.json()["items"]] == sorted(
            [item["goals"] for item in filtered.json()["items"]], reverse=True
        )

        first_page = client.get("/api/v2/players", params={"search": "Aaron", "limit": 1, "offset": 0}).json()
        second_page = client.get("/api/v2/players", params={"search": "Aaron", "limit": 1, "offset": 1}).json()
        assert first_page["meta"]["total"] == second_page["meta"]["total"] > 1
        assert first_page["items"][0]["id"] != second_page["items"][0]["id"]

        ids = [item["id"] for item in players.json()["items"]]
        profile = client.get(f"/api/v2/players/{ids[0]}")
        assert profile.status_code == 200
        assert profile.json()["identity_status"] == "provisional"
        assert client.get(f"/api/v2/players/{ids[0]}/seasons").json()["meta"]["total"] >= 1
        assert client.get(f"/api/v2/players/{ids[0]}/career").status_code == 200
        assert client.get(f"/api/v2/players/{ids[0]}/clubs").status_code == 200

        comparison = client.post("/api/v2/compare/players", json={"player_ids": ids})
        assert comparison.status_code == 200
        assert len(comparison.json()["items"]) == 4
        invalid = client.post("/api/v2/compare/players", json={"player_ids": [ids[0], ids[0]]})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_request"

        coverage = client.get("/api/v2/coverage").json()
        assert coverage["player_count"] == 2690
        assert len(coverage["clubs"]) == 96
        assert len(coverage["competitions"]) == 5
        assert client.get("/api/v2/clubs", params={"limit": 2}).json()["meta"]["total"] == 96
        assert client.get("/api/v2/competitions", params={"limit": 2}).json()["meta"]["total"] == 5
        identity = client.get("/api/v2/identity/summary")
        assert identity.status_code == 200
        assert identity.json()["source_local_keys"] == 2690
        assert identity.json()["verified_external_ids"] == 0
        assert client.get("/api/v2/identity/review").json() == []
        season = client.get("/api/v2/seasons").json()["items"][0]
        assert season["records"] == 2839
        assert client.get(f"/api/v2/seasons/{season['id']}").status_code == 200

        distribution = client.get("/api/v2/analytics/distribution", params={"metric": "goals", "bins": 8}).json()
        assert distribution["n"] == 2839
        assert sum(item["count"] for item in distribution["bins"]) == 2839
        correlation = client.get("/api/v2/analytics/correlation").json()
        assert correlation["pairwise_n"][0][1] == 2839
        assert correlation["matrix"][0][0] == 1

        lab = client.post("/api/v2/data-lab/query", json={"visualization": "scatter", "metrics": ["goals", "assists"], "limit": 10})
        assert lab.status_code == 200
        assert len(lab.json()["items"]) <= 10
        unsupported = client.post("/api/v2/data-lab/query", json={"visualization": "table", "metrics": ["xg"]})
        assert unsupported.status_code == 422

        exported = client.get("/api/v2/exports/players", params={"limit": 20})
        assert exported.status_code == 200
        records = list(csv.reader(io.StringIO(exported.text)))
        assert len(records) == 21
        assert records[0][0] == "player_id"
        assert "source_release" in records[0]
        assert all(len(row) == len(records[0]) for row in records)
        assert "non_penalty_goal_contributions" in records[0]
        assert "non_penalty_contributions_per90" in records[0]
        kane_csv = client.get("/api/v2/exports/players", params={"search": "Harry Kane", "limit": 1})
        kane_rows = list(csv.DictReader(io.StringIO(kane_csv.text)))
        assert len(kane_rows) == 1
        assert float(kane_rows[0]["non_penalty_goal_contributions"]) == 31
        assert float(kane_rows[0]["non_penalty_contributions_per90"]) == pytest.approx(90 * 31 / 2377, abs=0.001)

        comparison_csv = client.post("/api/v2/exports/comparison", json={"player_ids": ids})
        comparison_rows = list(csv.reader(io.StringIO(comparison_csv.text)))
        assert comparison_csv.status_code == 200
        assert len(comparison_rows) == 5
        assert all(len(row) == len(comparison_rows[0]) for row in comparison_rows)

        data_lab_export = client.post("/api/v2/exports/data-lab", json={
            "visualization": "table", "metrics": ["goals", "assists"], "limit": 10,
        })
        assert data_lab_export.status_code == 200
        assert data_lab_export.headers["x-pitchiq-exported"] == "10"
        exported_rows = list(csv.reader(io.StringIO(data_lab_export.text)))
        assert "source_release" in exported_rows[0]
        assert len(exported_rows) == 11


def test_uninitialized_v2_api_returns_consistent_503_without_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    missing = tmp_path / "not-initialized.sqlite3"
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(missing))
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v2/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"
    assert not missing.exists()


def test_metric_registry_exposes_supported_rates_and_conversion_separately(imported_database: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(imported_database))
    from app.main import app

    with TestClient(app) as client:
        registry = client.get("/api/v2/data-lab/metrics").json()
        keys = {item["metric_key"] for item in registry["items"]}
        assert {"goals_per_appearance", "assists_per_appearance", "goals_per_shot", "shots_per_goal"} <= keys
        assert {"shots_per90", "shots_on_target_per90", "goals_against", "save_percent", "penalties_saved"} <= keys
        assert "goals_per_shot" in registry["available_metrics"]
        assert "save_percent" in registry["available_metrics"]

        result = client.post("/api/v2/data-lab/query", json={
            "visualization": "table",
            "metrics": ["goals_per_appearance", "goals_per_shot"],
            "minimum_minutes": 0,
            "limit": 1000,
        })
        assert result.status_code == 200
        assert result.json()["items"]
        first = result.json()["items"][0]
        assert first["values"]["goals_per_appearance"] >= 0
        assert first["values"]["goals_per_shot"] >= 0
        shots_per_goal = client.post("/api/v2/data-lab/query", json={"visualization": "table", "metrics": ["shots_per_goal"], "minimum_minutes": 0, "limit": 1})
        assert shots_per_goal.status_code == 200
        assert shots_per_goal.json()["items"][0]["values"]["shots_per_goal"] > 0

        leaderboard = client.get("/api/v2/leaderboards", params={"metric": "goals_per_shot", "minimum_minutes": 0, "limit": 10})
        assert leaderboard.status_code == 200
        assert leaderboard.json()["eligible_count"] >= len(leaderboard.json()["items"]) > 0
        assert all(item["goals_per_shot"] is not None for item in leaderboard.json()["items"])
        assert all(item["cohort_size"] == leaderboard.json()["eligible_count"] for item in leaderboard.json()["items"])
        assert all(0 <= item["percentile"] <= 100 for item in leaderboard.json()["items"])
        shots_leaderboard = client.get("/api/v2/leaderboards", params={"metric": "shots_per90", "minimum_minutes": 0, "limit": 5})
        assert shots_leaderboard.status_code == 200
        assert all(item["shots_per90"] is not None for item in shots_leaderboard.json()["items"])
        goalkeeper_saves = client.post("/api/v2/data-lab/query", json={"visualization": "table", "metrics": ["saves"], "position": "GK", "limit": 200})
        goalkeeper_save_rates = client.post("/api/v2/data-lab/query", json={"visualization": "table", "metrics": ["save_percent"], "position": "GK", "limit": 200})
        assert goalkeeper_saves.status_code == goalkeeper_save_rates.status_code == 200
        assert len(goalkeeper_saves.json()["items"]) == 194
        assert all(item["values"]["saves"] is not None for item in goalkeeper_saves.json()["items"])
        assert len(goalkeeper_save_rates.json()["items"]) == 190
        leaderboard_csv = client.get("/api/v2/exports/leaderboards", params={"metric": "goals_per_shot", "minimum_minutes": 0, "limit": 5})
        assert leaderboard_csv.status_code == 200
        assert "percentile" in next(csv.reader(io.StringIO(leaderboard_csv.text)))


def test_nullable_minutes_remain_visible_and_do_not_create_per90_rates(imported_database: Path, monkeypatch: pytest.MonkeyPatch):
    connection = connect(imported_database)
    row = connection.execute("SELECT id, player_id FROM player_stat_records ORDER BY id LIMIT 1").fetchone()
    connection.execute("UPDATE player_stat_records SET minutes=NULL WHERE id=?", (row["id"],))
    connection.commit()
    connection.close()
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(imported_database))
    from app.main import app

    with TestClient(app) as client:
        profile = client.get(f"/api/v2/players/{row['player_id']}")
        assert profile.status_code == 200
        assert profile.json()["minutes"] is None
        assert profile.json()["goals_per90"] is None
        history = client.get(f"/api/v2/players/{row['player_id']}/seasons")
        assert history.status_code == 200
        assert history.json()["meta"]["total"] == 1
        assert history.json()["items"][0]["minutes"] is None


def test_csv_exports_escape_formula_like_player_names(imported_database: Path, monkeypatch: pytest.MonkeyPatch):
    connection = connect(imported_database)
    row = connection.execute("SELECT id FROM players ORDER BY id LIMIT 1").fetchone()
    connection.execute("UPDATE players SET canonical_name='=2+2', normalized_name='2 2' WHERE id=?", (row["id"],))
    connection.commit()
    connection.close()
    monkeypatch.setenv("PITCHIQ_DATABASE_PATH", str(imported_database))
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v2/exports/players", params={"search": "2+2", "limit": 20})
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text)))
    assert any(row[1] == "'=2+2" for row in rows[1:])
