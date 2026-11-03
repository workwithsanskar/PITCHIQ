ALTER TABLE player_stat_records ADD COLUMN penalties_faced REAL CHECK (penalties_faced IS NULL OR penalties_faced >= 0);
ALTER TABLE player_stat_records ADD COLUMN penalties_against REAL CHECK (penalties_against IS NULL OR penalties_against >= 0);
ALTER TABLE player_stat_records ADD COLUMN penalties_saved REAL CHECK (penalties_saved IS NULL OR penalties_saved >= 0);
ALTER TABLE player_stat_records ADD COLUMN penalties_missed REAL CHECK (penalties_missed IS NULL OR penalties_missed >= 0);

-- Backfill the already imported supplied release from the immutable raw payload.
-- Only simple non-negative decimal strings are accepted; other raw values remain null.
UPDATE player_stat_records
SET penalties_faced = CAST(json_extract(raw_metrics_json, '$.PKatt_stats_keeper') AS REAL)
WHERE json_type(raw_metrics_json, '$.PKatt_stats_keeper') = 'text'
  AND trim(json_extract(raw_metrics_json, '$.PKatt_stats_keeper')) <> ''
  AND trim(json_extract(raw_metrics_json, '$.PKatt_stats_keeper')) <> '.'
  AND trim(json_extract(raw_metrics_json, '$.PKatt_stats_keeper')) NOT GLOB '*[^0-9.]*'
  AND trim(json_extract(raw_metrics_json, '$.PKatt_stats_keeper')) NOT GLOB '*.*.*';

UPDATE player_stat_records
SET penalties_against = CAST(json_extract(raw_metrics_json, '$.PKA') AS REAL)
WHERE json_type(raw_metrics_json, '$.PKA') = 'text'
  AND trim(json_extract(raw_metrics_json, '$.PKA')) <> ''
  AND trim(json_extract(raw_metrics_json, '$.PKA')) <> '.'
  AND trim(json_extract(raw_metrics_json, '$.PKA')) NOT GLOB '*[^0-9.]*'
  AND trim(json_extract(raw_metrics_json, '$.PKA')) NOT GLOB '*.*.*';

UPDATE player_stat_records
SET penalties_saved = CAST(json_extract(raw_metrics_json, '$.PKsv') AS REAL)
WHERE json_type(raw_metrics_json, '$.PKsv') = 'text'
  AND trim(json_extract(raw_metrics_json, '$.PKsv')) <> ''
  AND trim(json_extract(raw_metrics_json, '$.PKsv')) <> '.'
  AND trim(json_extract(raw_metrics_json, '$.PKsv')) NOT GLOB '*[^0-9.]*'
  AND trim(json_extract(raw_metrics_json, '$.PKsv')) NOT GLOB '*.*.*';

UPDATE player_stat_records
SET penalties_missed = CAST(json_extract(raw_metrics_json, '$.PKm') AS REAL)
WHERE json_type(raw_metrics_json, '$.PKm') = 'text'
  AND trim(json_extract(raw_metrics_json, '$.PKm')) <> ''
  AND trim(json_extract(raw_metrics_json, '$.PKm')) <> '.'
  AND trim(json_extract(raw_metrics_json, '$.PKm')) NOT GLOB '*[^0-9.]*'
  AND trim(json_extract(raw_metrics_json, '$.PKm')) NOT GLOB '*.*.*';
