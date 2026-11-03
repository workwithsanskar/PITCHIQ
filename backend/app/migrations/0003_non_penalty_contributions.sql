-- Corrects an earlier mapping error: source G+A-PK is a per-90 rate in this CSV,
-- not a total. Preserve the original source field in source_records.raw payloads and
-- store the count as non-penalty goals plus assists.
UPDATE player_stat_records
SET non_penalty_goal_contributions = CASE
    WHEN non_penalty_goals IS NOT NULL AND assists IS NOT NULL
    THEN non_penalty_goals + assists
    ELSE NULL
END;
