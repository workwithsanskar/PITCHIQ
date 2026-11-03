-- PITCHIQ starter player database schema (SQLite)
-- players: one identity record per name + nationality + birth year key
-- player_season_stats: one record per player-club-competition-season spell
-- Do not interpret primary_club_by_minutes_in_season as a current club.

CREATE TABLE players (
  player_id TEXT PRIMARY KEY,
  player_name TEXT NOT NULL,
  nation_raw TEXT,
  position_raw TEXT,
  age_at_dataset_season REAL,
  birth_year REAL,
  primary_club_by_minutes_in_season TEXT,
  primary_competition_by_minutes_in_season TEXT,
  season_record_count INTEGER NOT NULL,
  identity_source TEXT,
  profile_image_url TEXT,
  date_of_birth TEXT,
  preferred_foot TEXT,
  height_cm REAL,
  market_value REAL,
  external_provider_id TEXT
);

CREATE TABLE player_season_stats (
  player_id TEXT NOT NULL,
  season TEXT NOT NULL,
  club TEXT,
  competition TEXT,
  position_raw TEXT,
  matches_played INTEGER,
  starts INTEGER,
  minutes INTEGER,
  nineties REAL,
  goals INTEGER,
  assists INTEGER,
  goals_per90 REAL,
  assists_per90 REAL,
  minutes_450_eligible INTEGER,
  source_dataset TEXT,
  FOREIGN KEY(player_id) REFERENCES players(player_id)
);
