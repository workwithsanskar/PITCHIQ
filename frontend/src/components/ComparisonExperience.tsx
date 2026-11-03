import type { ComparisonResult, PlayerSummary } from '../v2Api';
import { Link } from 'react-router-dom';

type ComparedPlayer = ComparisonResult['items'][number];
type Metric = { label: string; key: keyof PlayerSummary; digits?: number; suffix?: string };
type MetricGroup = { label: string; metrics: Metric[]; open?: boolean };

const overviewMetrics: Metric[] = [
  { label: 'Appearances', key: 'appearances' },
  { label: 'Starts', key: 'starts' },
  { label: 'Minutes', key: 'minutes' },
  { label: 'Goals', key: 'goals' },
  { label: 'Assists', key: 'assists' },
  { label: 'Goals / 90', key: 'goals_per90', digits: 2 },
  { label: 'Assists / 90', key: 'assists_per90', digits: 2 },
];

const groups: MetricGroup[] = [
  { label: 'General', open: true, metrics: [
    { label: 'Appearances', key: 'appearances' }, { label: 'Starts', key: 'starts' }, { label: 'Minutes', key: 'minutes' },
  ] },
  { label: 'Attacking', open: true, metrics: [
    { label: 'Goals', key: 'goals' }, { label: 'Non-penalty goals', key: 'non_penalty_goals' },
    { label: 'Assists', key: 'assists' }, { label: 'Non-penalty goal contributions', key: 'non_penalty_goal_contributions' },
    { label: 'Penalties scored', key: 'penalties_scored' }, { label: 'Penalties attempted', key: 'penalties_attempted' },
    { label: 'Goals / 90', key: 'goals_per90', digits: 2 }, { label: 'Assists / 90', key: 'assists_per90', digits: 2 },
    { label: 'Goal contributions / 90', key: 'contributions_per90', digits: 2 },
    { label: 'Non-penalty goals / 90', key: 'non_penalty_goals_per90', digits: 2 },
    { label: 'Non-penalty contributions / 90', key: 'non_penalty_contributions_per90', digits: 2 },
  ] },
  { label: 'Shooting', metrics: [
    { label: 'Shots', key: 'shots' }, { label: 'Shots on target', key: 'shots_on_target' },
    { label: 'Shots / 90', key: 'shots_per90', digits: 2 }, { label: 'Shots on target / 90', key: 'shots_on_target_per90', digits: 2 },
    { label: 'Shooting accuracy', key: 'shot_accuracy', digits: 1, suffix: '%' },
    { label: 'Goal conversion', key: 'goals_per_shot', digits: 1, suffix: '%' },
  ] },
  { label: 'Crossing', metrics: [
    { label: 'Crosses', key: 'crosses' }, { label: 'Crosses / 90', key: 'crosses_per90', digits: 2 },
  ] },
  { label: 'Defensive', metrics: [
    { label: 'Tackles won', key: 'tackles_won' }, { label: 'Tackles won / 90', key: 'tackles_won_per90', digits: 2 },
    { label: 'Interceptions', key: 'interceptions' }, { label: 'Interceptions / 90', key: 'interceptions_per90', digits: 2 },
  ] },
  { label: 'Discipline', metrics: [
    { label: 'Yellow cards', key: 'yellow_cards' }, { label: 'Second yellow dismissals', key: 'second_yellow_cards' },
    { label: 'Red cards', key: 'red_cards' }, { label: 'Fouls committed', key: 'fouls_committed' },
    { label: 'Fouls drawn', key: 'fouls_drawn' }, { label: 'Own goals', key: 'own_goals' },
  ] },
  { label: 'Goalkeeping', metrics: [
    { label: 'Goals against', key: 'goals_against' }, { label: 'Goals against / 90', key: 'goals_against_per90', digits: 2 },
    { label: 'Shots on target faced', key: 'shots_on_target_against' }, { label: 'Saves', key: 'saves' },
    { label: 'Save percentage', key: 'save_percent', digits: 1, suffix: '%' }, { label: 'Wins', key: 'wins' },
    { label: 'Draws', key: 'draws' }, { label: 'Losses', key: 'losses' }, { label: 'Clean sheets', key: 'clean_sheets' },
    { label: 'Clean-sheet percentage', key: 'clean_sheet_percent', digits: 1, suffix: '%' },
    { label: 'Penalties faced', key: 'penalties_faced' }, { label: 'Penalty goals against', key: 'penalties_against' },
    { label: 'Penalties saved', key: 'penalties_saved' }, { label: 'Penalties missed', key: 'penalties_missed' },
  ] },
];

function metricValue(player: ComparedPlayer, key: keyof PlayerSummary): number | null {
  const value = player[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatMetric(value: number | null, metric: Metric): string {
  if (value === null) return '—';
  return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: metric.digits ?? 0 }).format(value)}${metric.suffix ?? ''}`;
}

function names(values: (string | null | undefined)[], many: string): string {
  const unique = [...new Set(values.filter((value): value is string => Boolean(value)))];
  if (unique.length === 0) return 'Unavailable';
  return unique.length === 1 ? unique[0] : `${unique.length} ${many}`;
}

function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0] ?? '').join('').toUpperCase();
}

function metricLeader(players: ComparedPlayer[], metric: Metric, samePosition: boolean): number | null {
  if (!samePosition || players.length < 2) return null;
  const values = players.map(player => metricValue(player, metric.key));
  const present = values.filter((value): value is number => value !== null);
  if (present.length < 2) return null;
  const highest = Math.max(...present);
  if (present.filter(value => value === highest).length !== 1) return null;
  return values.findIndex(value => value === highest);
}

function metricLabel(metric: Metric): string {
  return metric.suffix === '%' ? `${metric.label} (%)` : metric.label;
}

export function ComparisonExperience({
  result,
  scopeLabel,
  onExport,
}: {
  result: ComparisonResult;
  scopeLabel: string;
  onExport: () => void;
}) {
  const players = result.items;
  const samePosition = players.length > 1
    && players.every(player => player.primary_position)
    && new Set(players.map(player => player.primary_position)).size === 1;
  const visibleOverview = overviewMetrics.filter(metric => players.some(player => metricValue(player, metric.key) !== null));

  return <section className="v2-comparison-experience" aria-label="Player comparison results">
    <div className="v2-results-line v2-compare-results-line">
      <span>{players.length} players <i aria-hidden="true">·</i> {scopeLabel}</span>
      <button type="button" className="btn-outline export-link" onClick={onExport}>Export comparison</button>
    </div>

    <div className="v2-compare-profiles">
      {players.map(player => <article className="panel v2-compare-profile" key={player.id}>
        <div className="v2-compare-player-title">
          <span className="v2-compare-initials" aria-hidden="true">{initials(player.canonical_name)}</span>
          <div><h2><Link to={`/database/player/${encodeURIComponent(player.id)}`}>{player.canonical_name}</Link></h2>
            <span>{player.primary_position ?? 'Position unavailable'}</span></div>
        </div>
        <div className="v2-compare-context">
          <span>{names(player.records.map(record => record.club), 'clubs')}</span>
          <span>{names(player.records.map(record => record.competition), 'competitions')}</span>
          <span>{names(player.records.map(record => record.season), 'seasons')}</span>
        </div>
        <dl className="v2-compare-summary">
          <div><dt>Minutes</dt><dd>{formatMetric(metricValue(player, 'minutes'), { label: 'Minutes', key: 'minutes' })}</dd></div>
          <div><dt>Appearances</dt><dd>{formatMetric(metricValue(player, 'appearances'), { label: 'Appearances', key: 'appearances' })}</dd></div>
          <div><dt>Records</dt><dd>{formatMetric(player.record_count, { label: 'Records', key: 'record_count' })}</dd></div>
        </dl>
      </article>)}
    </div>

    <section className="panel v2-compare-visuals" aria-labelledby="v2-compare-overview-title">
      <div className="v2-compare-section-heading"><div><span className="eyebrow">QUICK COMPARISON</span><h2 id="v2-compare-overview-title">Compare the covered numbers.</h2></div>
        <span className="v2-compare-scale-note">Bars start at zero and scale to the highest selected value.</span></div>
      {visibleOverview.length > 0 ? <div className="v2-compare-metric-grid">
        {visibleOverview.map(metric => {
          const values = players.map(player => metricValue(player, metric.key));
          const maximum = Math.max(0, ...values.filter((value): value is number => value !== null));
          const leader = metricLeader(players, metric, samePosition);
          return <article className="v2-compare-metric" key={metric.key} aria-label={`${metric.label} comparison`}>
            <h3>{metric.label}</h3>
            <div className="v2-compare-bar-list">
              {players.map((player, index) => {
                const value = values[index];
                const width = value === null || maximum === 0 ? 0 : Math.max(0, Math.min(100, value / maximum * 100));
                return <div className={`v2-compare-bar-row${leader === index ? ' is-leader' : ''}`} key={player.id}>
                  <span className="v2-compare-bar-name" title={player.canonical_name}>{player.canonical_name}</span>
                  {value === null ? <span className="v2-compare-bar-missing">Unavailable</span> : <div className="v2-compare-track" role="meter" aria-label={`${player.canonical_name}: ${formatMetric(value, metric)}`} aria-valuemin={0} aria-valuemax={maximum || 1} aria-valuenow={value}>
                    <span style={{ width: `${width}%` }}/></div>}
                  <b>{formatMetric(value, metric)}</b>
                </div>;
              })}
            </div>
          </article>;
        })}
      </div> : <p className="v2-muted">No shared overview metrics are available for this selection.</p>}
      <p className="v2-compare-caveat">{samePosition
        ? 'A unique high value is accented only within this same-position selection. Ties remain neutral; no overall score is calculated.'
        : 'Positions differ or are unavailable, so metric bars stay neutral and are not treated as a ranking.'}</p>
    </section>

    <section className="v2-compare-details" aria-label="Detailed statistical comparison">
      <div className="v2-compare-section-heading"><div><span className="eyebrow">DETAILED STATISTICS</span><h2>Explore the record by category.</h2></div></div>
      {groups.map(group => {
        const available = group.metrics.filter(metric => players.some(player => metricValue(player, metric.key) !== null));
        if (!available.length) return null;
        return <details className="panel v2-compare-category" key={group.label} open={group.open}>
          <summary><span>{group.label}</span><small>{available.length} available metrics</small></summary>
          <div className="v2-compare-table-scroll" role="region" aria-label={`${group.label} comparison table`} tabIndex={0}>
            <table className="v2-compare-stats">
              <caption className="sr-only">{group.label} statistics for selected players</caption>
              <thead><tr><th scope="col">METRIC</th>{players.map(player => <th scope="col" key={player.id}><span>{player.canonical_name}</span><small>{player.primary_position ?? 'Position unavailable'}</small></th>)}</tr></thead>
              <tbody>{available.map(metric => {
                const leader = metricLeader(players, metric, samePosition);
                return <tr key={metric.key}><th scope="row">{metricLabel(metric)}</th>{players.map((player, index) => <td className={leader === index ? 'is-leader' : undefined} key={player.id}>{formatMetric(metricValue(player, metric.key), metric)}</td>)}</tr>;
              })}</tbody>
            </table>
          </div>
        </details>;
      })}
    </section>
    <p className="v2-compare-methodology">{result.methodology} Mixed-position comparisons can show different responsibilities; use position and source context when interpreting each metric.</p>
  </section>;
}
