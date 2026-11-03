# PITCHIQ Player Database — Initial Data Assessment

## Source
- Input: `players_data_light-2025_2026.csv`
- Season label used: 2025-2026 (taken from filename)
- Records: 2,839
- Distinct player identity keys generated: 2,690
- Club-spell/stat rows: 2,839
- Competitions: 5
- Clubs: 96
- Nations: 115

## Competition distribution
Comp
es La Liga            611
it Serie A            609
fr Ligue 1            561
eng Premier League    551
de Bundesliga         507

## Key observations
- This is a five-competition dataset: Premier League, La Liga, Bundesliga, Serie A and Ligue 1.
- The 2,839 rows include multiple club spells for some players. Repeated player names should not be deleted as duplicates.
- 840 rows have fewer than 450 minutes; the 450-minute flag is a configurable convenience, not a universal ranking rule.
- Goalkeeper field `GA` is missing in 93.2% of rows, consistent with goalkeeper-only fields being blank for most outfield players.
- This source does not provide reliable profile images, full dates of birth, preferred foot, height, market value, or stable external provider IDs. Those fields are left NULL, not guessed.
- The current source does not cover MLS, Saudi Pro League, many other domestic leagues, or historical seasons.

## Database structure
- `players`: identity/master table, one row per generated identity key.
- `player_season_stats`: one row per player-club-competition-season spell.
- `competitions`: competition reference table.
- `clubs`: club-to-competition reference table.

## Derived metrics added
Goals, assists, shots, shots on target, tackles won, interceptions and crosses per 90 are recalculated from raw totals and minutes. Rows with zero minutes receive NULL per-90 values.

## Important identity limitation
The generated `player_id` is a deterministic local key based on player name, nationality and birth year. It is not an official global player identifier. Before merging additional providers, identity matching must use provider IDs where possible and otherwise use reviewed matching logic. Do not merge on player name alone.

## Recommended next-version enrichment
1. Add a source-attributed global player directory with stable provider IDs.
2. Add more competitions and seasons as player-season fact records.
3. Add profile fields (date of birth, nationality, position, height, preferred foot, image) only from verified sources.
4. Keep profile metadata and season statistics separate.
5. Store source, retrieval date, season, competition and license/attribution for every imported dataset.
6. Preserve NULL as unknown; never turn missing values into zero.
7. Add a reviewed alias table for accented names, alternate spellings and transfers.

## Source research notes
- FBref publishes broad competition/player-season coverage statistics; check its current terms and access rules before any automated ingestion.
- StatsBomb Open Data offers selected match/event/lineup data for public research and requires attribution when sharing derived work.
- football-data.org exposes competition and team resources; its published free plan does not include squad data, while squad access appears in paid tiers.
- This package contains only the supplied CSV and derived fields. No external player statistics or biographical facts have been fabricated or silently inserted.
