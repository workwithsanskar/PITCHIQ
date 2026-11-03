CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE data_sources (
    id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    source_url TEXT,
    license_name TEXT,
    license_url TEXT,
    permitted_use TEXT,
    attribution_requirements TEXT,
    redistribution_allowed INTEGER CHECK (redistribution_allowed IN (0, 1) OR redistribution_allowed IS NULL),
    commercial_use_allowed INTEGER CHECK (commercial_use_allowed IN (0, 1) OR commercial_use_allowed IS NULL),
    reviewed_at TEXT,
    rights_status TEXT NOT NULL DEFAULT 'unverified' CHECK (rights_status IN ('approved', 'restricted', 'unverified')),
    active_status TEXT NOT NULL DEFAULT 'active' CHECK (active_status IN ('active', 'inactive')),
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX ux_data_sources_default ON data_sources(is_default) WHERE is_default = 1;

CREATE TABLE source_releases (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    release_name TEXT NOT NULL,
    release_date TEXT,
    checksum TEXT NOT NULL,
    file_name TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    schema_version TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    UNIQUE (source_id, checksum)
);
CREATE UNIQUE INDEX ux_source_release_current ON source_releases(source_id) WHERE is_current = 1;

CREATE TABLE import_jobs (
    id TEXT PRIMARY KEY,
    source_release_id TEXT NOT NULL REFERENCES source_releases(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'completed_with_rejections', 'failed', 'unchanged')),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at TEXT,
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    rows_inserted INTEGER NOT NULL DEFAULT 0 CHECK (rows_inserted >= 0),
    rows_updated INTEGER NOT NULL DEFAULT 0 CHECK (rows_updated >= 0),
    rows_warning INTEGER NOT NULL DEFAULT 0 CHECK (rows_warning >= 0),
    rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    error_summary TEXT
);

CREATE TABLE seasons (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    season_type TEXT NOT NULL DEFAULT 'split_year',
    CHECK (start_date IS NULL OR date(start_date) IS NOT NULL),
    CHECK (end_date IS NULL OR date(end_date) IS NOT NULL),
    CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date)
);

CREATE TABLE clubs (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    country TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE competitions (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    country TEXT,
    competition_type TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE players (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    date_of_birth TEXT,
    birth_year INTEGER,
    nationality TEXT,
    primary_position TEXT,
    preferred_foot TEXT,
    height_cm REAL CHECK (height_cm IS NULL OR height_cm > 0),
    identity_status TEXT NOT NULL DEFAULT 'provisional' CHECK (identity_status IN ('verified', 'provisional', 'unresolved')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (date_of_birth IS NULL OR date(date_of_birth) IS NOT NULL),
    CHECK (birth_year IS NULL OR birth_year BETWEEN 1850 AND 2100)
);
CREATE INDEX ix_players_normalized_name ON players(normalized_name);

CREATE TABLE player_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (player_id, normalized_alias, source_id)
);
CREATE INDEX ix_player_aliases_search ON player_aliases(normalized_alias, source_id);

CREATE TABLE player_external_ids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_player_id TEXT NOT NULL,
    source_reference TEXT,
    verification_status TEXT NOT NULL CHECK (verification_status IN ('verified', 'unverified', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (provider, external_player_id)
);

CREATE TABLE player_source_keys (
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_player_key TEXT NOT NULL,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    key_status TEXT NOT NULL DEFAULT 'provisional' CHECK (key_status IN ('verified_source_key', 'provisional', 'needs_review')),
    PRIMARY KEY (source_id, source_player_key),
    UNIQUE (source_id, player_id)
);

CREATE TABLE club_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id TEXT NOT NULL REFERENCES clubs(id) ON UPDATE CASCADE ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    UNIQUE (club_id, source_id, normalized_alias)
);

CREATE TABLE competition_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id TEXT NOT NULL REFERENCES competitions(id) ON UPDATE CASCADE ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    UNIQUE (competition_id, source_id, normalized_alias)
);

CREATE TABLE player_club_spells (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    club_id TEXT NOT NULL REFERENCES clubs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    season_id TEXT NOT NULL REFERENCES seasons(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    start_date TEXT,
    end_date TEXT,
    UNIQUE (player_id, club_id, season_id, source_id),
    CHECK (start_date IS NULL OR date(start_date) IS NOT NULL),
    CHECK (end_date IS NULL OR date(end_date) IS NOT NULL)
);
CREATE INDEX ix_player_club_spells_player_season ON player_club_spells(player_id, season_id);

CREATE TABLE player_competition_appearances (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    club_id TEXT NOT NULL REFERENCES clubs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    competition_id TEXT NOT NULL REFERENCES competitions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    season_id TEXT NOT NULL REFERENCES seasons(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (player_id, club_id, competition_id, season_id, source_id)
);

CREATE TABLE player_stat_records (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL REFERENCES players(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    club_id TEXT REFERENCES clubs(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    competition_id TEXT REFERENCES competitions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    season_id TEXT NOT NULL REFERENCES seasons(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_release_id TEXT NOT NULL REFERENCES source_releases(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_record_key TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'club_competition',
    position_raw TEXT,
    age REAL CHECK (age IS NULL OR age BETWEEN 0 AND 120),
    appearances REAL CHECK (appearances IS NULL OR appearances >= 0),
    starts REAL CHECK (starts IS NULL OR starts >= 0),
    minutes REAL CHECK (minutes IS NULL OR minutes >= 0),
    goals REAL CHECK (goals IS NULL OR goals >= 0),
    assists REAL CHECK (assists IS NULL OR assists >= 0),
    goal_contributions REAL CHECK (goal_contributions IS NULL OR goal_contributions >= 0),
    non_penalty_goals REAL CHECK (non_penalty_goals IS NULL OR non_penalty_goals >= 0),
    non_penalty_goal_contributions REAL CHECK (non_penalty_goal_contributions IS NULL OR non_penalty_goal_contributions >= 0),
    penalties_scored REAL CHECK (penalties_scored IS NULL OR penalties_scored >= 0),
    penalties_attempted REAL CHECK (penalties_attempted IS NULL OR penalties_attempted >= 0),
    yellow_cards REAL CHECK (yellow_cards IS NULL OR yellow_cards >= 0),
    red_cards REAL CHECK (red_cards IS NULL OR red_cards >= 0),
    second_yellow_cards REAL CHECK (second_yellow_cards IS NULL OR second_yellow_cards >= 0),
    fouls_committed REAL CHECK (fouls_committed IS NULL OR fouls_committed >= 0),
    fouls_drawn REAL CHECK (fouls_drawn IS NULL OR fouls_drawn >= 0),
    own_goals REAL CHECK (own_goals IS NULL OR own_goals >= 0),
    shots REAL CHECK (shots IS NULL OR shots >= 0),
    shots_on_target REAL CHECK (shots_on_target IS NULL OR shots_on_target >= 0),
    source_sot_percent REAL CHECK (source_sot_percent IS NULL OR source_sot_percent BETWEEN 0 AND 100),
    crosses REAL CHECK (crosses IS NULL OR crosses >= 0),
    tackles_won REAL CHECK (tackles_won IS NULL OR tackles_won >= 0),
    interceptions REAL CHECK (interceptions IS NULL OR interceptions >= 0),
    goals_against REAL CHECK (goals_against IS NULL OR goals_against >= 0),
    goals_against_per90 REAL CHECK (goals_against_per90 IS NULL OR goals_against_per90 >= 0),
    shots_on_target_against REAL CHECK (shots_on_target_against IS NULL OR shots_on_target_against >= 0),
    saves REAL CHECK (saves IS NULL OR saves >= 0),
    save_percent REAL CHECK (save_percent IS NULL OR save_percent BETWEEN 0 AND 100),
    wins REAL CHECK (wins IS NULL OR wins >= 0),
    draws REAL CHECK (draws IS NULL OR draws >= 0),
    losses REAL CHECK (losses IS NULL OR losses >= 0),
    clean_sheets REAL CHECK (clean_sheets IS NULL OR clean_sheets >= 0),
    clean_sheet_percent REAL CHECK (clean_sheet_percent IS NULL OR clean_sheet_percent BETWEEN 0 AND 100),
    raw_metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_release_id, source_record_key)
);
CREATE INDEX ix_stat_player_season ON player_stat_records(player_id, season_id);
CREATE INDEX ix_stat_comp_season ON player_stat_records(competition_id, season_id);
CREATE INDEX ix_stat_club_season ON player_stat_records(club_id, season_id);
CREATE INDEX ix_stat_minutes ON player_stat_records(minutes);

CREATE TABLE source_records (
    id TEXT PRIMARY KEY,
    source_release_id TEXT NOT NULL REFERENCES source_releases(id) ON DELETE RESTRICT,
    source_record_key TEXT NOT NULL,
    source_row_number INTEGER NOT NULL CHECK (source_row_number > 0),
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('accepted', 'rejected', 'warning')),
    error_json TEXT,
    player_stat_record_id TEXT REFERENCES player_stat_records(id) ON DELETE SET NULL,
    UNIQUE (source_release_id, source_record_key),
    UNIQUE (source_release_id, source_row_number)
);

CREATE TABLE metric_definitions (
    metric_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    data_type TEXT NOT NULL,
    unit TEXT NOT NULL,
    formula TEXT,
    required_fields_json TEXT NOT NULL DEFAULT '[]',
    minimum_data_requirements TEXT,
    availability_status TEXT NOT NULL CHECK (availability_status IN ('available', 'partial', 'unavailable')),
    formula_version TEXT NOT NULL DEFAULT '1'
);

CREATE TABLE identity_match_decisions (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_player_key TEXT NOT NULL,
    candidate_player_id TEXT REFERENCES players(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('automatically_matched', 'manually_approved', 'unresolved', 'rejected', 'needs_review')),
    evidence_json TEXT NOT NULL DEFAULT '{}',
    method_version TEXT NOT NULL,
    reviewer TEXT,
    decided_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX ix_identity_decisions_status ON identity_match_decisions(status, source_id);
CREATE UNIQUE INDEX ux_identity_decision_source_key_method
    ON identity_match_decisions(source_id, source_player_key, method_version);
